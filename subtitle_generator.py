import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SubtitleGenerator")

class CaptionAlignmentError(Exception):
    """Raised when subtitles cannot be constructed or aligned reliably."""
    pass

class SubtitleGenerator:
    """
    Constructs frame-accurate SRT subtitles using verified word-level timestamps.
    Automatic timestamp repairs, extensions, clamping, and heuristic math are strictly prohibited.
    """
    def format_srt_time(self, seconds: float) -> str:
        """
        Formats seconds into standard SRT time format: HH:MM:SS,mmm.
        Correctly carries millisecond rounding over seconds, minutes, and hours.
        Rejects negative timestamps immediately. Never clamps 1000 to 999.
        """
        if seconds < 0:
            raise CaptionAlignmentError(f"Negative timestamp cannot be formatted into SRT: {seconds}s")

        # Total integer milliseconds rounded to nearest millisecond
        total_millis = int(round(seconds * 1000.0))

        millis = total_millis % 1000
        total_seconds = total_millis // 1000
        secs = total_seconds % 60
        total_minutes = total_seconds // 60
        mins = total_minutes % 60
        hrs = total_minutes // 60

        return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"

    def group_words_into_cues(self, word_boundaries: list, max_words_per_cue: int = 3) -> list:
        """
        Groups verified spoken word tokens into small, punchy phrases (2-3 words per cue)
        for vertical 9:16 Shorts display.
        Uses exact audio start of the first word and end of the last word.
        Strictly rejects non-positive or inverted durations without automatic repair.
        """
        if not word_boundaries:
            return []

        cues = []
        for i in range(0, len(word_boundaries), max_words_per_cue):
            group = word_boundaries[i : i + max_words_per_cue]
            chunk_text = " ".join(w["word"] for w in group)
            start_time = group[0]["start"]
            end_time = group[-1]["end"]

            # Strict Rejection: Never repair invalid timestamps
            if start_time < 0 or end_time < 0:
                raise CaptionAlignmentError(
                    f"Negative timestamp in cue '{chunk_text}': [{start_time}s -> {end_time}s]"
                )

            if end_time <= start_time:
                raise CaptionAlignmentError(
                    f"Invalid non-positive cue duration in '{chunk_text}': start={start_time}s, end={end_time}s"
                )

            cues.append({
                "text": chunk_text,
                "start": start_time,
                "end": end_time
            })

        return cues

    def generate_srt(self, segments: list, srt_output_path: Path) -> bool:
        """
        Generates a synchronized SRT subtitle file from segments containing verified word_boundaries.
        Validates continuous multi-segment timeline using measured audio durations.
        Immediately raises CaptionAlignmentError on any timing defect without repairing.
        """
        try:
            logger.info(f"Generating frame-accurate subtitles: {srt_output_path}")
            srt_output_path.parent.mkdir(parents=True, exist_ok=True)

            srt_index = 1
            segment_offset_time = 0.0
            all_cues = []

            for idx, segment in enumerate(segments):
                word_boundaries = segment.get("word_boundaries")
                duration = segment.get("duration", 0.0)

                if duration <= 0:
                    raise CaptionAlignmentError(f"Segment {idx} has invalid audio duration: {duration}s")

                if not word_boundaries or not isinstance(word_boundaries, list):
                    raise CaptionAlignmentError(
                        f"Segment {idx} is missing verified word_boundaries. Cannot generate accurate subtitles."
                    )

                # Verify last word doesn't exceed measured segment duration (+150ms tolerance for trailing audio padding)
                last_word_end = word_boundaries[-1]["end"]
                if last_word_end > (duration + 0.15):
                    raise CaptionAlignmentError(
                        f"Segment {idx} word boundaries exceed audio duration: last word ends at {last_word_end}s, audio duration is {duration}s"
                    )

                # Group words into high-retention cues
                cues = self.group_words_into_cues(word_boundaries, max_words_per_cue=3)
                if not cues:
                    raise CaptionAlignmentError(f"Segment {idx} yielded zero subtitle cues.")

                for cue in cues:
                    abs_start = segment_offset_time + cue["start"]
                    abs_end = segment_offset_time + cue["end"]

                    # Strict Rejection: Never repair or adjust invalid timestamps
                    if abs_start < 0 or abs_end < 0:
                        raise CaptionAlignmentError(
                            f"Cue {srt_index} has negative timestamp: [{abs_start}s -> {abs_end}s]"
                        )

                    if abs_end <= abs_start:
                        raise CaptionAlignmentError(
                            f"Cue {srt_index} has non-positive duration: start={abs_start}s, end={abs_end}s"
                        )

                    if all_cues and abs_start < all_cues[-1]["start"]:
                        raise CaptionAlignmentError(
                            f"Cue {srt_index} starts before previous cue: {abs_start}s < {all_cues[-1]['start']}s"
                        )

                    all_cues.append({
                        "index": srt_index,
                        "start": abs_start,
                        "end": abs_end,
                        "text": cue["text"].upper()
                    })
                    srt_index += 1

                # Advance global timeline using measured audio duration
                segment_offset_time += duration

            # Write formatted SRT blocks
            with open(srt_output_path, "w", encoding="utf-8") as f:
                for cue in all_cues:
                    start_str = self.format_srt_time(cue["start"])
                    end_str = self.format_srt_time(cue["end"])
                    f.write(f"{cue['index']}\n")
                    f.write(f"{start_str} --> {end_str}\n")
                    f.write(f"{cue['text']}\n\n")

            logger.info(f"Subtitle file generated successfully with {len(all_cues)} verified cues.")
            return True

        except Exception as e:
            logger.critical(f"FATAL: Subtitle generation failed: {e}")
            raise CaptionAlignmentError(f"Subtitle generation aborted: {e}") from e

if __name__ == "__main__":
    pass
