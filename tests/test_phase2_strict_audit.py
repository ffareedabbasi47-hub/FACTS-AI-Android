#!/usr/bin/env python3
"""
FACTS AI - Phase 2 Strict Final Audit Test Suite
=================================================
Covers all 10 mandatory audit test scenarios:
1. Zero-duration word (end == start)
2. Negative timestamp (start < 0 or end < 0)
3. End timestamp beyond audio duration
4. Non-monotonic timestamps (curr_start < prev_start)
5. Missing word in returned boundaries
6. Duplicate word in returned boundaries
7. Reordered words in returned boundaries
8. Multi-segment continuous timeline accumulation
9. Millisecond rounding across second/minute/hour boundaries without 999 clamping
10. Empty narration and failed Edge TTS requests
"""

import sys
import shutil
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice_generator import VoiceGenerator, VoiceSynthesisError, AlignmentValidationError
from subtitle_generator import SubtitleGenerator, CaptionAlignmentError

def run_strict_audit_tests():
    vg = VoiceGenerator()
    sg = SubtitleGenerator()

    test_scratch = Path("/tmp/facts_ai_phase2_strict_audit")
    if test_scratch.exists():
        shutil.rmtree(test_scratch)
    test_scratch.mkdir(parents=True, exist_ok=True)

    print("=================================================================")
    print("      FACTS AI - PHASE 2 STRICT CODE AUDIT VERIFICATION          ")
    print("=================================================================\n")

    # TEST 1: Zero-duration word rejection
    print("[TEST 1] Testing rejection of zero-duration word (end == start)...")
    zero_dur_boundaries = [
        {"word": "Black", "start": 0.0, "end": 0.5},
        {"word": "hole", "start": 0.5, "end": 0.5}  # 0 duration!
    ]
    try:
        vg._validate_word_timestamps(zero_dur_boundaries, audio_duration=1.0)
        raise AssertionError("Validation gate permitted zero-duration word!")
    except AlignmentValidationError as e:
        print(f"  [PASS] Correctly rejected zero-duration word: {e}\n")

    # TEST 2: Negative timestamp rejection
    print("[TEST 2] Testing rejection of negative timestamps...")
    neg_boundaries = [
        {"word": "Negative", "start": -0.1, "end": 0.4}
    ]
    try:
        vg._validate_word_timestamps(neg_boundaries, audio_duration=1.0)
        raise AssertionError("Validation gate permitted negative timestamp!")
    except AlignmentValidationError as e:
        print(f"  [PASS] Correctly rejected negative timestamp: {e}\n")

    # TEST 3: End timestamp beyond audio duration rejection
    print("[TEST 3] Testing rejection of timestamp beyond measured audio duration...")
    excessive_boundaries = [
        {"word": "Light", "start": 0.0, "end": 2.5}
    ]
    try:
        vg._validate_word_timestamps(excessive_boundaries, audio_duration=1.8)  # Audio is only 1.8s
        raise AssertionError("Validation gate permitted boundary exceeding audio duration!")
    except AlignmentValidationError as e:
        print(f"  [PASS] Correctly rejected boundary exceeding audio duration: {e}\n")

    # TEST 4: Non-monotonic timestamps rejection
    print("[TEST 4] Testing rejection of non-monotonic timestamps (backward jump)...")
    non_monotonic = [
        {"word": "Alpha", "start": 0.5, "end": 0.8},
        {"word": "Beta", "start": 0.4, "end": 0.7}  # 0.4s < 0.5s!
    ]
    try:
        vg._validate_word_timestamps(non_monotonic, audio_duration=1.5)
        raise AssertionError("Validation gate permitted non-monotonic timestamps!")
    except AlignmentValidationError as e:
        print(f"  [PASS] Correctly rejected non-monotonic timestamps: {e}\n")

    # TEST 5: Transcript integrity - Missing word detection
    print("[TEST 5] Testing transcript integrity - Missing word detection...")
    transcript_5 = "The sun is a giant star"
    boundaries_5 = [
        {"word": "The", "start": 0.0, "end": 0.2},
        {"word": "sun", "start": 0.2, "end": 0.5},
        {"word": "is", "start": 0.5, "end": 0.7},
        {"word": "star", "start": 0.7, "end": 1.1}  # 'a' and 'giant' are missing!
    ]
    try:
        vg._verify_transcript_integrity(transcript_5, boundaries_5)
        raise AssertionError("Validation gate permitted missing words in transcript!")
    except AlignmentValidationError as e:
        print(f"  [PASS] Correctly detected missing words: {e}\n")

    # TEST 6: Transcript integrity - Duplicate word detection
    print("[TEST 6] Testing transcript integrity - Duplicate word detection...")
    transcript_6 = "Gravity bends light"
    boundaries_6 = [
        {"word": "Gravity", "start": 0.0, "end": 0.5},
        {"word": "bends", "start": 0.5, "end": 0.8},
        {"word": "bends", "start": 0.8, "end": 1.1},  # Duplicated word!
        {"word": "light", "start": 1.1, "end": 1.4}
    ]
    try:
        vg._verify_transcript_integrity(transcript_6, boundaries_6)
        raise AssertionError("Validation gate permitted duplicated word!")
    except AlignmentValidationError as e:
        print(f"  [PASS] Correctly detected duplicated word: {e}\n")

    # TEST 7: Transcript integrity - Reordered words detection
    print("[TEST 7] Testing transcript integrity - Reordered words detection...")
    transcript_7 = "Quantum physics is fascinating"
    boundaries_7 = [
        {"word": "Physics", "start": 0.0, "end": 0.5},
        {"word": "Quantum", "start": 0.5, "end": 1.0},  # Reordered!
        {"word": "is", "start": 1.0, "end": 1.2},
        {"word": "fascinating", "start": 1.2, "end": 1.8}
    ]
    try:
        vg._verify_transcript_integrity(transcript_7, boundaries_7)
        raise AssertionError("Validation gate permitted reordered words!")
    except AlignmentValidationError as e:
        print(f"  [PASS] Correctly detected reordered words: {e}\n")

    # TEST 8: Multi-segment continuous timeline assembly
    print("[TEST 8] Testing multi-segment continuous timeline assembly...")
    multi_segments = [
        {
            "text": "Segment one begins.",
            "duration": 2.500,
            "word_boundaries": [
                {"word": "Segment", "start": 0.100, "end": 0.600},
                {"word": "one", "start": 0.650, "end": 0.900},
                {"word": "begins", "start": 0.950, "end": 1.400}
            ]
        },
        {
            "text": "Segment two follows.",
            "duration": 3.000,
            "word_boundaries": [
                {"word": "Segment", "start": 0.200, "end": 0.700},
                {"word": "two", "start": 0.750, "end": 1.000},
                {"word": "follows", "start": 1.050, "end": 1.600}
            ]
        }
    ]
    srt_out = test_scratch / "multi_segment.srt"
    sg.generate_srt(multi_segments, srt_out)
    with open(srt_out, "r", encoding="utf-8") as f:
        srt_text = f.read()

    print(f"Generated Multi-Segment SRT:\n{srt_text}")
    # Verify Segment 2 is offset by Segment 1 duration (2.500s + 0.200s = 2.700s)
    assert "00:00:02,700 --> 00:00:04,100" in srt_text, "Segment 2 start time is not correctly offset by Segment 1 duration!"
    print("  [PASS] Multi-segment timeline accurately accumulated using measured audio duration.\n")

    # TEST 9: SRT Millisecond Rounding & Carry (No 999 clamping)
    print("[TEST 9] Testing SRT timestamp formatting & millisecond rollover...")
    # 0.9996s rounds to 1.000s
    t1 = sg.format_srt_time(0.9996)
    assert t1 == "00:00:01,000", f"Expected '00:00:01,000', got '{t1}'"

    # 59.9997s carries into 1 minute
    t2 = sg.format_srt_time(59.9997)
    assert t2 == "00:01:00,000", f"Expected '00:01:00,000', got '{t2}'"

    # 3599.9998s carries into 1 hour
    t3 = sg.format_srt_time(3599.9998)
    assert t3 == "01:00:00,000", f"Expected '01:00:00,000', got '{t3}'"

    # Negative timestamp must be rejected
    try:
        sg.format_srt_time(-1.5)
        raise AssertionError("format_srt_time permitted negative timestamp!")
    except CaptionAlignmentError:
        pass

    print(f"  0.9996s   -> {t1}")
    print(f"  59.9997s  -> {t2}")
    print(f"  3599.9998s -> {t3}")
    print("  Negative   -> Rejected with CaptionAlignmentError")
    print("  [PASS] Millisecond rounding and carry strictly mathematically correct.\n")

    # TEST 10: Empty narration & failed Edge TTS request
    print("[TEST 10] Testing failure handling on empty text and invalid voice...")
    try:
        vg.generate_segment_audios([{"text": ""}], test_scratch)
        raise AssertionError("VoiceGenerator allowed empty text!")
    except VoiceSynthesisError as e:
        print(f"  [PASS] Correctly aborted on empty text: {e}")

    # Test invalid voice error handling
    bad_vg = VoiceGenerator()
    bad_vg.voice = "non-existent-voice-xyz"
    try:
        bad_vg.generate_segment_audios([{"text": "Test failed request"}], test_scratch)
        raise AssertionError("VoiceGenerator did not abort on invalid voice!")
    except VoiceSynthesisError as e:
        print(f"  [PASS] Correctly aborted on failed Edge TTS voice/request: {e}\n")

    # Clean up
    shutil.rmtree(test_scratch)

    print("=================================================================")
    print("   ALL 10 PHASE 2 STRICT AUDIT TEST SCENARIOS PASSED (10/10)     ")
    print("=================================================================")

if __name__ == "__main__":
    run_strict_audit_tests()
