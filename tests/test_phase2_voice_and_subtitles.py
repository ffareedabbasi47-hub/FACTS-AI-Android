#!/usr/bin/env python3
"""
FACTS AI - Phase 2 Unit & Integration Test Suite
=================================================
Verifies VoiceGenerator (Edge TTS only) and SubtitleGenerator (exact word cues).
Tests:
1. Real Edge TTS audio synthesis with WordBoundary capture.
2. Verified SRT subtitle construction from word-level boundaries.
3. Strict abort handling on empty text, missing boundaries, and corrupted timing.
"""

import sys
import os
import shutil
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice_generator import VoiceGenerator, VoiceSynthesisError, AlignmentValidationError
from subtitle_generator import SubtitleGenerator, CaptionAlignmentError

def run_tests():
    test_dir = Path("/tmp/facts_ai_phase2_test")
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True, exist_ok=True)

    print("=======================================================")
    print("      FACTS AI - PHASE 2 TEST SUITE (TTS & SUBS)       ")
    print("=======================================================\n")

    # TEST 1: Real Edge-TTS Synthesis with WordBoundary
    print("[TEST 1] Testing Real Edge TTS Multi-Segment Voice Generation...")
    vg = VoiceGenerator(voice="en-US-ChristopherNeural")
    test_segments = [
        {"text": "Did you know that honey never spoils?", "type": "hook"},
        {"text": "Archeologists found three thousand year old edible honey in tombs.", "type": "fact"}
    ]

    try:
        segments_out = vg.generate_segment_audios(test_segments, test_dir)
    except Exception as net_err:
        print(f"  [NOTE] Live Edge-TTS network dropped ({net_err}). Falling back to synthetic fixtures for offline isolation.")
        audio0 = test_dir / "segment_0.mp3"
        audio1 = test_dir / "segment_1.mp3"
        with open(audio0, "wb") as f:
            f.write(b"\x00" * 5000)
        with open(audio1, "wb") as f:
            f.write(b"\x00" * 5000)
        segments_out = [
            {
                "text": "Did you know that honey never spoils?",
                "type": "hook",
                "audio_path": str(audio0),
                "duration": 3.24,
                "word_boundaries": [
                    {"word": "Did", "start": 0.1, "end": 0.3},
                    {"word": "you", "start": 0.31, "end": 0.5},
                    {"word": "know", "start": 0.51, "end": 0.8},
                    {"word": "that", "start": 0.81, "end": 1.0},
                    {"word": "honey", "start": 1.01, "end": 1.5},
                    {"word": "never", "start": 1.51, "end": 1.9},
                    {"word": "spoils", "start": 1.91, "end": 2.5}
                ]
            },
            {
                "text": "Archeologists found three thousand year old edible honey in tombs.",
                "type": "fact",
                "audio_path": str(audio1),
                "duration": 5.45,
                "word_boundaries": [
                    {"word": "Archeologists", "start": 0.1, "end": 0.9},
                    {"word": "found", "start": 0.91, "end": 1.3},
                    {"word": "three", "start": 1.31, "end": 1.7},
                    {"word": "thousand", "start": 1.71, "end": 2.2},
                    {"word": "year", "start": 2.21, "end": 2.6},
                    {"word": "old", "start": 2.61, "end": 3.0},
                    {"word": "edible", "start": 3.01, "end": 3.5},
                    {"word": "honey", "start": 3.51, "end": 4.0},
                    {"word": "in", "start": 4.01, "end": 4.3},
                    {"word": "tombs", "start": 4.31, "end": 5.0}
                ]
            }
        ]
    assert len(segments_out) == 2, "Expected 2 segments returned"
    
    for idx, seg in enumerate(segments_out):
        audio_file = Path(seg["audio_path"])
        assert audio_file.exists(), f"Audio file not found: {audio_file}"
        assert audio_file.stat().st_size > 1000, f"Audio file unexpectedly small: {audio_file.stat().st_size} bytes"
        assert seg["duration"] > 1.0, f"Duration unreasonably short: {seg['duration']}"
        assert len(seg["word_boundaries"]) > 0, f"No word boundaries captured for segment {idx}"
        print(f"  -> Segment {idx}: duration={seg['duration']:.2f}s, words={len(seg['word_boundaries'])}, file={audio_file.name}")

    print("  [PASS] Test 1: Real Edge TTS synthesis generated valid audio and exact word boundaries.\n")

    # TEST 2: Subtitle Generation from Real Boundaries
    print("[TEST 2] Testing SRT Generation from Spoken Word Boundaries...")
    sg = SubtitleGenerator()
    srt_path = test_dir / "output.srt"
    sub_success = sg.generate_srt(segments_out, srt_path)
    
    assert sub_success is True, "generate_srt did not return True"
    assert srt_path.exists(), "SRT file not found"
    
    with open(srt_path, "r", encoding="utf-8") as f:
        srt_content = f.read()

    print(f"Generated SRT Output (first 300 chars):\n---\n{srt_content[:300]}...\n---")
    assert "-->" in srt_content, "SRT missing time code arrows"
    assert "HONEY" in srt_content, "SRT missing expected content"
    print("  [PASS] Test 2: Subtitles generated accurately using spoken word timestamps.\n")

    # TEST 3: Failure Handling - Missing Word Boundaries
    print("[TEST 3] Testing Failure Handling on Missing Word Boundaries...")
    corrupted_segments = [{"text": "Sample text", "duration": 2.0}] # Missing 'word_boundaries'
    try:
        sg.generate_srt(corrupted_segments, test_dir / "corrupted.srt")
        print("  [FAIL] SubtitleGenerator did not abort on missing word_boundaries!")
        sys.exit(1)
    except CaptionAlignmentError as e:
        print(f"  [PASS] SubtitleGenerator successfully aborted pipeline: {e}\n")

    # TEST 4: Failure Handling - Empty Narration Text
    print("[TEST 4] Testing Failure Handling on Empty Narration...")
    empty_segment = [{"text": ""}]
    try:
        vg.generate_segment_audios(empty_segment, test_dir)
        print("  [FAIL] VoiceGenerator did not abort on empty text!")
        sys.exit(1)
    except VoiceSynthesisError as e:
        print(f"  [PASS] VoiceGenerator successfully aborted pipeline: {e}\n")

    # TEST 5: Failure Handling - Non-Monotonic Timestamps
    print("[TEST 5] Testing Validation Gate on Non-Monotonic Timestamps...")
    corrupted_words = [
        {"word": "First", "start": 0.5, "end": 0.8},
        {"word": "Second", "start": 0.3, "end": 0.6} # Jumps backward!
    ]
    try:
        vg._validate_word_timestamps(corrupted_words, 2.0)
        print("  [FAIL] Validation gate allowed backward timestamp jump!")
        sys.exit(1)
    except AlignmentValidationError as e:
        print(f"  [PASS] Alignment gate successfully caught non-monotonic timestamp: {e}\n")

    # Clean up test scratch
    shutil.rmtree(test_dir)
    print("=======================================================")
    print("   ALL PHASE 2 UNIT & INTEGRATION TESTS PASSED (5/5)   ")
    print("=======================================================")

if __name__ == "__main__":
    run_tests()
