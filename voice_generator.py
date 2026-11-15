import asyncio
import logging
import os
import re
import subprocess
import unicodedata
from pathlib import Path
from typing import List, Optional
import edge_tts
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VoiceGenerator")

class VoiceSynthesisError(Exception):
    """Raised when TTS generation or audio synthesis fails."""
    pass

class AlignmentValidationError(Exception):
    """Raised when word-level timestamp or transcript validation fails."""
    pass

class ScriptLanguageError(VoiceSynthesisError):
    """Raised when script language does not match the voice requirements."""
    pass

DEFAULT_HINDI_VOICE = "hi-IN-MadhurNeural"
ALTERNATE_HINDI_VOICE = "hi-IN-SwaraNeural"
SUPPORTED_HINDI_VOICES = [DEFAULT_HINDI_VOICE, ALTERNATE_HINDI_VOICE]

class VoiceGenerator:
    """
    Edge TTS voice generator with guaranteed word-level timestamp extraction.
    Configured for Hindi natural voices (hi-IN-MadhurNeural default, hi-IN-SwaraNeural alternate).
    Piper and gTTS are disabled per FACTS AI architectural governance.
    """
    def __init__(self, voice: Optional[str] = None):
        # Default to hi-IN-MadhurNeural, configurable via environment variable EDGE_VOICE
        self.voice = voice or os.getenv("EDGE_VOICE", DEFAULT_HINDI_VOICE)
        logger.info(f"Initialized VoiceGenerator with Edge-TTS voice: {self.voice}")

    def validate_script_language_before_tts(self, text: str, voice: Optional[str] = None):
        """
        Validates that script narration matches the voice requirements before dispatching to TTS.
        If a Hindi voice (hi-IN-*) is selected, rejects pure English narration and requires Devanagari.
        """
        active_voice = voice or self.voice
        if active_voice.startswith("hi-IN"):
            devanagari_chars = len(re.findall(r'[\u0900-\u097F]', text))
            if devanagari_chars == 0:
                raise ScriptLanguageError(
                    f"Pre-TTS language validation failed: English narration is not allowed for Hindi voice '{active_voice}'. "
                    f"Voice requires Hindi Devanagari narration, but text contains zero Devanagari characters: '{text}'"
                )
            latin_chars = len(re.findall(r'[a-zA-Z]', text))
            if latin_chars > devanagari_chars:
                raise ScriptLanguageError(
                    f"Pre-TTS language validation failed: English narration is not allowed for Hindi voice '{active_voice}'. "
                    f"Found {latin_chars} Latin vs {devanagari_chars} Devanagari characters: '{text}'"
                )

    def _clean_word_for_comparison(self, word: str) -> str:
        """
        Strips surrounding punctuation, whitespace, symbols, and format controls (ZWJ, ZWNJ) for phonetic comparison.
        Preserves alphanumeric characters and Unicode combining marks (such as Hindi matras: Mn, Mc).
        Safely normalizes internal ZWJ and ZWNJ to prevent typographical ligature mismatches.
        """
        chars = list(word.strip())
        # Strip leading punctuation (P), symbols (S), separators (Z), and format controls (ZWJ, ZWNJ)
        while chars and (unicodedata.category(chars[0]).startswith(("P", "S", "Z")) or chars[0] in ("\u200c", "\u200d")):
            chars.pop(0)
        # Strip trailing punctuation (P), symbols (S), separators (Z), and format controls (ZWJ, ZWNJ)
        while chars and (unicodedata.category(chars[-1]).startswith(("P", "S", "Z")) or chars[-1] in ("\u200c", "\u200d")):
            chars.pop(-1)
        cleaned = "".join(chars).lower()
        return cleaned.replace("\u200c", "").replace("\u200d", "")

    def _verify_transcript_integrity(self, transcript: str, word_boundaries: list):
        """
        Strict transcript integrity check:
        1. Compares original narration text against returned word boundary tokens.
        2. Detects missing, duplicated, reordered, substituted, or unexpected words.
        3. Never claims 100% alignment unless exact token sequence matches.
        """
        expected_raw = transcript.split()
        expected_tokens = [self._clean_word_for_comparison(w) for w in expected_raw]
        expected_tokens = [t for t in expected_tokens if t]

        extracted_raw = [w["word"] for w in word_boundaries]
        extracted_tokens = [self._clean_word_for_comparison(w) for w in extracted_raw]
        extracted_tokens = [t for t in extracted_tokens if t]

        # 1. Token count check (detects missing or duplicated words)
        if len(expected_tokens) != len(extracted_tokens):
            raise AlignmentValidationError(
                f"Transcript token count mismatch: expected {len(expected_tokens)} words ({expected_tokens}), "
                f"got {len(extracted_tokens)} aligned tokens ({extracted_tokens})."
            )

        # 2. Sequential token comparison (detects reordering, substitutions, or unexpected words)
        for idx in range(len(expected_tokens)):
            exp = expected_tokens[idx]
            ext = extracted_tokens[idx]
            if exp != ext:
                raise AlignmentValidationError(
                    f"Transcript token mismatch at index {idx}: expected '{exp}', got '{ext}'. "
                    f"Full expected: {expected_tokens}, full extracted: {extracted_tokens}"
                )

    def _validate_word_timestamps(self, word_boundaries: list, audio_duration: float):
        """
        Strict timestamp validation gate:
        1. Every word must have positive duration (end > start).
        2. No negative timestamps.
        3. Monotonically non-decreasing start times.
        4. Last word end time must not exceed measured audio duration (+150ms tolerance for audio padding).
        """
        for i, word in enumerate(word_boundaries):
            start = word["start"]
            end = word["end"]

            if start < 0 or end < 0:
                raise AlignmentValidationError(
                    f"Negative timestamp on word '{word['word']}': [{start}s -> {end}s]"
                )

            if end <= start:
                raise AlignmentValidationError(
                    f"Non-positive duration for word '{word['word']}': start={start}s, end={end}s"
                )

            if i > 0:
                prev_start = word_boundaries[i - 1]["start"]
                if start < prev_start:
                    raise AlignmentValidationError(
                        f"Non-monotonic timestamp jump at '{word['word']}': {start}s < previous {prev_start}s"
                    )

        last_word_end = word_boundaries[-1]["end"]
        if last_word_end > (audio_duration + 0.15):
            raise AlignmentValidationError(
                f"Word timestamps exceed measured audio duration: last word ends at {last_word_end}s, "
                f"measured duration is {audio_duration:.3f}s"
            )

    async def _generate_audio_with_timestamps(self, text: str, output_path: Path) -> dict:
        """
        Streams audio from Edge-TTS with WordBoundary enabled.
        Captures raw MP3 audio and exact word start/end timestamps.
        Converts 100ns tick offsets to float seconds.
        """
        communicate = edge_tts.Communicate(text, self.voice, boundary="WordBoundary")

        audio_buffer = bytearray()
        raw_boundaries = []

        try:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_buffer.extend(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    # Offset and duration are in 100ns units (ticks: 1 second = 10,000,000 ticks)
                    start_sec = chunk["offset"] / 10_000_000.0
                    dur_sec = chunk["duration"] / 10_000_000.0
                    raw_boundaries.append({
                        "word": chunk["text"],
                        "start": round(start_sec, 3),
                        "end": round(start_sec + dur_sec, 3),
                        "duration": round(dur_sec, 3)
                    })
        except Exception as e:
            err_msg = f"Edge TTS streaming failed: {e}"
            logger.error(err_msg)
            raise VoiceSynthesisError(err_msg) from e

        if not audio_buffer:
            raise VoiceSynthesisError("Edge TTS returned empty audio buffer.")

        if not raw_boundaries:
            raise AlignmentValidationError("Edge TTS returned zero word boundaries.")

        # Write audio to disk
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(audio_buffer)

        # Measure verified audio duration via ffprobe
        audio_duration = self.get_audio_duration(output_path)
        if audio_duration <= 0:
            raise VoiceSynthesisError(f"Invalid audio duration measured via ffprobe: {audio_duration}")

        # 1. Transcript-to-token integrity check (no dropped, duplicated, or reordered words)
        self._verify_transcript_integrity(text, raw_boundaries)

        # 2. Strict timestamp verification (monotonicity, bounds, positive duration)
        self._validate_word_timestamps(raw_boundaries, audio_duration)

        return {
            "audio_path": str(output_path),
            "duration": audio_duration,
            "word_boundaries": raw_boundaries
        }

    def generate_segment_audios(self, segments: list, temp_dir: Path, validate_language: bool = False) -> list:
        """
        Generates audio and word-level timestamps for all script segments.
        If any segment fails, raises VoiceSynthesisError and ABORTS pipeline.
        """
        updated_segments = []
        temp_dir.mkdir(parents=True, exist_ok=True)

        for idx, segment in enumerate(segments):
            text = segment.get("text", "").strip()
            if not text:
                raise VoiceSynthesisError(f"Segment {idx} contains empty narration text.")

            # Optional pre-TTS language validation gate
            if validate_language:
                self.validate_script_language_before_tts(text)

            audio_path = temp_dir / f"segment_{idx}.mp3"
            logger.info(f"Generating voice for segment {idx} ({len(text.split())} words, voice: {self.voice}) -> {audio_path.name}")

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    self._generate_audio_with_timestamps(text, audio_path)
                )
                updated_segments.append({
                    **segment,
                    "audio_path": result["audio_path"],
                    "duration": result["duration"],
                    "word_boundaries": result["word_boundaries"]
                })
                logger.info(
                    f"Segment {idx} voice generated successfully ({result['duration']:.2f}s, {len(result['word_boundaries'])} aligned words)"
                )
            except Exception as e:
                err_msg = f"Voice generation aborted at segment {idx}: {e}"
                logger.critical(f"FATAL: {err_msg}")
                raise VoiceSynthesisError(err_msg) from e
            finally:
                if not loop.is_closed():
                    loop.close()
                asyncio.set_event_loop(None)

        return updated_segments

    def get_audio_duration(self, file_path: Path) -> float:
        """Retrieves exact duration of an audio file using ffprobe."""
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(file_path)
            ]
            creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creation_flags,
                text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
            else:
                logger.error(f"ffprobe error reading {file_path}: {result.stderr}")
                return 0.0
        except Exception as e:
            logger.error(f"Failed to execute ffprobe on {file_path}: {e}")
            return 0.0

if __name__ == "__main__":
    pass
