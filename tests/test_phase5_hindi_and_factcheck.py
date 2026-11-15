#!/usr/bin/env python3
"""
FACTS AI - Phase 5 Unit & Integration Test Suite
=================================================
Verifies:
1. Dedicated Scientific Fact-Checking Module (verification against reliable sources, URL validation, rejection of refuted/unverified claims, persistent logging).
2. Hindi Script Generation (Devanagari script, ~30s Shorts duration, scientific accuracy preservation, rejection of English narration).
3. Hindi Edge TTS (hi-IN-MadhurNeural default, hi-IN-SwaraNeural alternate, word-boundary timestamps, combining-mark preservation, subtitle synchronization, safe abort).

STRICT ISOLATION:
Zero live YouTube API calls, zero Google OAuth, zero external mutations.
Uses mocks and synthetic test fixtures.
"""

import os
import sys
import json
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fact_checker import (
    FactChecker,
    FactCheckError,
    ClaimRejectedError,
    UnverifiedClaimError,
    TRUSTED_SCIENTIFIC_DOMAINS
)
from script_writer import ScriptWriter, LanguageValidationError
from voice_generator import (
    VoiceGenerator,
    VoiceSynthesisError,
    AlignmentValidationError,
    ScriptLanguageError,
    DEFAULT_HINDI_VOICE,
    ALTERNATE_HINDI_VOICE
)
from subtitle_generator import SubtitleGenerator, CaptionAlignmentError
from main import AutomationPipeline
import config

class TestPhase5FactChecker(unittest.TestCase):
    def setUp(self):
        self.checker = FactChecker()
        self.test_scratch = Path("/tmp/facts_ai_phase5_test")
        self.test_scratch.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if self.test_scratch.exists():
            shutil.rmtree(self.test_scratch)

    def test_url_validation_authoritative_sources(self):
        """Verify URL validation accepts reputable scientific domains and rejects untrusted/malformed URLs."""
        valid_urls = [
            "https://www.nasa.gov/mission_pages/station/research/news/",
            "https://isro.gov.in/chandrayaan3.html",
            "https://www.nature.com/articles/s41586-020-0001",
            "https://www.sciencedirect.com/science/article/pii/S0000",
            "https://www.britannica.com/science/speed-of-light",
            "https://mit.edu/research/quantum-physics",
            "https://arxiv.org/abs/2301.00001"
        ]
        for url in valid_urls:
            self.assertTrue(self.checker.validate_source_url(url), f"Failed to validate authoritative URL: {url}")

        invalid_urls = [
            "http://insecure-domain.xyz",
            "https://fake-science-news-blog.com/article",
            "https://unverified-conspiracy.org/5g",
            "not-a-valid-url",
            "",
            None
        ]
        for url in invalid_urls:
            self.assertFalse(self.checker.validate_source_url(url), f"Allowed invalid/untrusted URL: {url}")

    def test_verify_valid_claim_with_sources(self):
        """Verify legitimate scientific claim passes verification with genuine source URLs."""
        record = self.checker.verify_claim("Space sound vacuum silence")
        self.assertTrue(record["verified"])
        self.assertEqual(record["status"], "VERIFIED")
        self.assertGreaterEqual(record["confidence"], 0.85)
        self.assertGreater(len(record["source_urls"]), 0)
        for url in record["source_urls"]:
            self.assertTrue(self.checker.validate_source_url(url))

    def test_reject_refuted_pseudoscience(self):
        """Verify pseudoscientific / false claims are immediately rejected with ClaimRejectedError."""
        false_claims = [
            "The Earth is flat and gravity is an illusion",
            "5G towers spread biological virus particles",
            "Building a perpetual motion machine in your garage"
        ]
        for claim in false_claims:
            with self.assertRaises(ClaimRejectedError):
                self.checker.enforce_verification(claim)

    def test_unverified_claim_fails_safely(self):
        """Verify claims with no verifiable sources fail safely with UnverifiedClaimError."""
        unknown_claim = "Unprecedented alien civilization discovered in secret backyard bunker"
        with self.assertRaises(UnverifiedClaimError):
            self.checker.enforce_verification(unknown_claim)

    def test_never_claim_verified_without_sources(self):
        """Verify fact-checker demotes claims claimed to be verified if source_urls is empty."""
        with patch.object(self.checker, "api_key", "sk-mock-key"):
            with patch("requests.post") as mock_post:
                # LLM claims verified=True but provides empty source_urls
                mock_post.return_value.status_code = 200
                mock_post.return_value.json.return_value = {
                    "choices": [{
                        "message": {
                            "content": json.dumps({
                                "claim": "Quantum teleportation is possible",
                                "verified": True,
                                "status": "VERIFIED",
                                "confidence": 0.9,
                                "source_urls": [],  # NO SOURCES!
                                "explanation": "True, but no sources given."
                            })
                        }
                    }]
                }
                record = self.checker.verify_claim("Quantum teleportation is possible")
                self.assertFalse(record["verified"], "Claimed verification without sources!")
                self.assertEqual(record["status"], "UNVERIFIED")

    def test_save_verification_log(self):
        """Verify verification record with source URLs and status is durably stored to JSON."""
        log_path = self.test_scratch / "fact_check.json"
        record = {
            "claim": "Speed of light is 300,000 km/s",
            "verified": True,
            "status": "VERIFIED",
            "confidence": 1.0,
            "source_urls": ["https://www.britannica.com/science/speed-of-light"],
            "explanation": "Fundamental physical constant."
        }
        self.checker.save_verification_log(record, log_path)
        self.assertTrue(log_path.exists())
        with open(log_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["status"], "VERIFIED")
        self.assertEqual(len(data["source_urls"]), 1)

class TestPhase5HindiScriptGeneration(unittest.TestCase):
    def setUp(self):
        self.writer = ScriptWriter()

    def test_validate_hindi_text_devanagari_passes(self):
        """Verify natural Hindi text in Devanagari passes language validation."""
        valid_hindi = [
            "अंतरिक्ष में कोई वायुमंडल नहीं है, इसलिए वहां पूर्ण सन्नाटा रहता है।",
            "ध्वनि को यात्रा करने के लिए हवा या किसी माध्यम की जरूरत होती है।",
            "नासा के अनुसार दो अंतरिक्ष यात्री एक-दूसरे की आवाज नहीं सुन सकते।"
        ]
        for text in valid_hindi:
            self.assertTrue(self.writer.validate_hindi_text(text), f"Valid Hindi rejected: {text}")

    def test_validate_hindi_text_english_narration_rejected(self):
        """Verify pure English narration text is strictly rejected."""
        english_texts = [
            "Did you know that space is completely silent?",
            "Neutron stars can rotate at 700 revolutions per second.",
            "Scientists discovered that honey never spoils."
        ]
        for text in english_texts:
            self.assertFalse(self.writer.validate_hindi_text(text), f"English narration accepted: {text}")

    def test_validate_script_language_full_script_passes(self):
        """Verify valid Hindi script with 5 Devanagari segments passes validation."""
        script_data = {
            "title": "अंतरिक्ष का सबसे बड़ा रहस्य",
            "segments": [
                {"text": "क्या आप जानते हैं कि अंतरिक्ष में पूर्ण सन्नाटा रहता है?", "type": "hook"},
                {"text": "ध्वनि को यात्रा करने के लिए माध्यम की जरूरत होती है।", "type": "body"},
                {"text": "अंतरिक्ष में हवा नहीं है, इसलिए कोई आवाज नहीं होती।", "type": "body"},
                {"text": "नासा के अनुसार अंतरिक्ष में दो यात्री बात नहीं सुन सकते।", "type": "body"},
                {"text": "ऐसे ही अद्भुत तथ्यों के लिए अभी सब्सक्राइब करें!", "type": "cta"}
            ]
        }
        self.assertTrue(self.writer.validate_script_language(script_data, "hi"))

    def test_validate_script_language_english_segment_raises(self):
        """Verify script containing an English segment raises LanguageValidationError."""
        script_data = {
            "title": "अंतरिक्ष का रहस्य",
            "segments": [
                {"text": "क्या आप जानते हैं कि अंतरिक्ष पूरी तरह शांत है?", "type": "hook"},
                {"text": "Sound waves need physical particles to travel through space.", "type": "body"}  # English!
            ]
        }
        with self.assertRaises(LanguageValidationError) as ctx:
            self.writer.validate_script_language(script_data, "hi")
        self.assertIn("English narration is not allowed", str(ctx.exception))

    def test_hindi_fallback_script_conforms_to_standards(self):
        """Verify fallback Hindi script is in Devanagari, targets ~30s, and passes validation."""
        fallback = self.writer._get_fallback_hindi_script("अंतरिक्ष में ध्वनि", "short")
        self.assertIn("segments", fallback)
        self.assertGreaterEqual(len(fallback["segments"]), 4)
        self.assertLessEqual(len(fallback["segments"]), 6)
        self.assertTrue(self.writer.validate_script_language(fallback, "hi"))

class TestPhase5HindiEdgeTTS(unittest.TestCase):
    def setUp(self):
        self.vg = VoiceGenerator()
        self.test_scratch = Path("/tmp/facts_ai_phase5_tts_test")
        self.test_scratch.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if self.test_scratch.exists():
            shutil.rmtree(self.test_scratch)

    def test_default_voice_is_madhur(self):
        """Verify VoiceGenerator default voice is hi-IN-MadhurNeural."""
        with patch.dict(os.environ, {}, clear=True):
            vg = VoiceGenerator()
            self.assertEqual(vg.voice, "hi-IN-MadhurNeural")

    def test_alternate_voice_is_swara(self):
        """Verify hi-IN-SwaraNeural can be configured as alternate Hindi voice."""
        vg = VoiceGenerator(voice="hi-IN-SwaraNeural")
        self.assertEqual(vg.voice, "hi-IN-SwaraNeural")

    def test_clean_word_preserves_hindi_matras(self):
        """Verify Unicode word cleaner preserves combining marks/matras while stripping punctuation."""
        hindi_tokens = [
            ("«अंतरिक्ष»", "अंतरिक्ष"),
            ("में,", "में"),
            ("कोई!", "कोई"),
            ("हवा?", "हवा"),
            ("नहीं;", "नहीं"),
            ("है।", "है")
        ]
        for raw, expected in hindi_tokens:
            cleaned = self.vg._clean_word_for_comparison(raw)
            self.assertEqual(cleaned, expected, f"Corrupted Hindi word: {raw} -> {cleaned} (expected: {expected})")

    def test_pre_tts_language_validation_rejects_english(self):
        """Verify pre-TTS validator raises ScriptLanguageError when English is passed to Hindi voice."""
        vg = VoiceGenerator(voice="hi-IN-MadhurNeural")
        with self.assertRaises(ScriptLanguageError) as ctx:
            vg.validate_script_language_before_tts("Did you know that space is completely silent?")
        self.assertIn("English narration is not allowed", str(ctx.exception))

    def test_transcript_integrity_hindi_devanagari(self):
        """Verify _verify_transcript_integrity perfectly matches authentic Devanagari tokens."""
        transcript = "अंतरिक्ष पूरी तरह से शांत है।"
        boundaries = [
            {"word": "अंतरिक्ष", "start": 0.1, "end": 0.6},
            {"word": "पूरी", "start": 0.6, "end": 0.9},
            {"word": "तरह", "start": 0.9, "end": 1.2},
            {"word": "से", "start": 1.2, "end": 1.4},
            {"word": "शांत", "start": 1.4, "end": 1.8},
            {"word": "है", "start": 1.8, "end": 2.2}
        ]
        # Should not raise AlignmentValidationError
        self.vg._verify_transcript_integrity(transcript, boundaries)

    def test_hindi_subtitles_synchronization(self):
        """Verify SubtitleGenerator creates frame-accurate SRT from Hindi word boundaries."""
        sg = SubtitleGenerator()
        segments = [
            {
                "duration": 2.5,
                "word_boundaries": [
                    {"word": "अंतरिक्ष", "start": 0.1, "end": 0.6},
                    {"word": "पूरी", "start": 0.6, "end": 0.9},
                    {"word": "तरह", "start": 0.9, "end": 1.2},
                    {"word": "से", "start": 1.2, "end": 1.4},
                    {"word": "शांत", "start": 1.4, "end": 1.8},
                    {"word": "है", "start": 1.8, "end": 2.2}
                ]
            }
        ]
        srt_path = self.test_scratch / "hindi.srt"
        success = sg.generate_srt(segments, srt_path)
        self.assertTrue(success)
        self.assertTrue(srt_path.exists())
        content = srt_path.read_text(encoding="utf-8")
        self.assertIn("अंतरिक्ष पूरी तरह", content)
        self.assertIn("से शांत है", content)

    def test_voice_synthesis_failure_safe_abort(self):
        """Verify VoiceSynthesisError is raised and pipeline safely aborted if TTS returns empty audio."""
        async def fake_stream_empty():
            if False:
                yield {}

        mock_comm = MagicMock()
        mock_comm.stream.return_value = fake_stream_empty()

        with patch("edge_tts.Communicate", return_value=mock_comm):
            with self.assertRaises(VoiceSynthesisError):
                self.vg.generate_segment_audios(
                    [{"text": "अंतरिक्ष शांत है।"}],
                    self.test_scratch
                )

class TestPhase5PipelineIntegration(unittest.TestCase):
    def setUp(self):
        self.pipeline = AutomationPipeline()
        self.test_scratch = Path("/tmp/facts_ai_phase5_pipeline_test")
        self.test_scratch.mkdir(parents=True, exist_ok=True)
        self.used_topics_file = self.test_scratch / "used_topics.txt"
        self.orig_base = config.BASE_DIR
        config.BASE_DIR = self.test_scratch

    def tearDown(self):
        config.BASE_DIR = self.orig_base
        if self.test_scratch.exists():
            shutil.rmtree(self.test_scratch)

    def test_pipeline_halts_on_refuted_scientific_claim(self):
        """Verify pipeline immediately halts with ClaimRejectedError when given a false/refuted claim."""
        with self.assertRaises(ClaimRejectedError):
            self.pipeline.run_pipeline(target_topic="Flat Earth and why gravity does not exist")

    def test_pipeline_halts_on_unverified_claim(self):
        """Verify pipeline immediately halts with UnverifiedClaimError when claim has no sources."""
        with self.assertRaises(UnverifiedClaimError):
            self.pipeline.run_pipeline(target_topic="Mysterious unidentified creature found inside local tea shop")

if __name__ == "__main__":
    unittest.main()
