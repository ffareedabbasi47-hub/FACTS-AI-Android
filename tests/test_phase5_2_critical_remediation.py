#!/usr/bin/env python3
"""
FACTS AI - Phase 5.2 Critical Defect Remediation Test Suite
===========================================================
Regression tests verifying:
1. Real scientific evidence verification (rejects fabricated URLs, 404s, unrelated pages, and unsupported segment claims).
2. Ambiguous upload reconciliation via unique operation marker and channel ownership (eliminates topic vs SEO title mismatch).
3. Strict Hindi language validation (Devanagari, approved technical acronyms, foreign script rejection, ZWJ/ZWNJ safety).
4. Linux Devanagari font detection and missing-glyph protection.

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
from unittest.mock import patch, MagicMock, Mock

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fact_checker import (
    FactChecker,
    FactCheckError,
    ClaimRejectedError,
    UnverifiedClaimError
)
from script_writer import ScriptWriter, LanguageValidationError, APPROVED_TECHNICAL_ACRONYMS
from voice_generator import VoiceGenerator, VoiceSynthesisError
from video_builder import VideoBuilder, FontMissingError
from youtube_uploader import YoutubeUploader
from main import AutomationPipeline
import config

class TestPhase52ScientificEvidenceVerification(unittest.TestCase):
    def setUp(self):
        self.checker = FactChecker()

    def test_fabricated_nasa_url_rejected_on_404(self):
        """Verify fabricated URL on trusted NASA domain returning 404 is rejected."""
        fake_nasa_url = "https://www.nasa.gov/fabricated-nonexistent-claim-xyz123"
        
        with patch("requests.get") as mock_get:
            mock_resp = Mock()
            mock_resp.status_code = 404
            mock_get.return_value = mock_resp
            
            result = self.checker.fetch_and_validate_source(fake_nasa_url)
            self.assertIsNone(result, "Fabricated 404 NASA URL was not rejected!")

    def test_unrelated_source_page_rejected_on_content_mismatch(self):
        """Verify trusted domain returning HTTP 200 with unrelated content (e.g. gardening) is rejected."""
        gardening_html = """
        <html><body><h1>Growing Organic Tomatoes and Roses in Florida</h1>
        <p>Ensure soil pH is balanced between 6.0 and 6.8. Water plants twice daily during summer.</p></body></html>
        """
        nasa_url = "https://www.nasa.gov/mission_pages/station/research/gardening.html"
        
        with patch("requests.get") as mock_get:
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.url = nasa_url
            mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
            mock_resp.text = gardening_html
            mock_get.return_value = mock_resp
            
            # Fetch content
            source_data = self.checker.fetch_and_validate_source(nasa_url)
            self.assertIsNotNone(source_data)
            
            # Evidence relevance check against astronomy claim must fail
            snippet = self.checker.extract_evidence_snippet("Sound cannot travel through vacuum of space", source_data["full_text"])
            self.assertIsNone(snippet, "Unrelated gardening page was accepted as evidence for space physics!")

    def test_related_source_page_extracts_evidence_snippet(self):
        """Verify trusted source page with relevant scientific text successfully yields evidence snippet."""
        space_html = """
        <html><body><h1>What does space sound like?</h1>
        <p>In space, there is no air or atmosphere. Because sound waves require a physical medium like gas or liquid to propagate, the vacuum of space is completely silent.</p></body></html>
        """
        nasa_url = "https://www.nasa.gov/science-research/planetary-science/what-does-space-sound-like/"
        
        with patch("requests.get") as mock_get:
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.url = nasa_url
            mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
            mock_resp.text = space_html
            mock_get.return_value = mock_resp
            
            source_data = self.checker.fetch_and_validate_source(nasa_url)
            self.assertIsNotNone(source_data)
            snippet = self.checker.extract_evidence_snippet("Sound cannot travel through vacuum of space", source_data["full_text"])
            self.assertIsNotNone(snippet)
            self.assertIn("vacuum", snippet.lower())

    def test_unsupported_segment_claim_halts_script_verification(self):
        """Verify script containing an unsupported scientific segment claim fails verification."""
        evidence_records = [{
            "url": "https://www.nasa.gov/space-sound",
            "full_text": "In space, sound waves cannot travel because there is no air or medium."
        }]
        script = {
            "title": "अंतरिक्ष का रहस्य",
            "segments": [
                {"text": "क्या आप जानते हैं कि अंतरिक्ष में पूर्ण सन्नाटा रहता है?", "type": "hook"},
                {"text": "वैज्ञानिकों ने पाया कि मंगल ग्रह पर गुप्त सोने के महल मौजूद हैं।", "type": "body"},  # Unsupported!
                {"text": "सब्सक्राइब करें दैनिक जानकारी के लिए।", "type": "cta"}
            ]
        }
        with self.assertRaises(UnverifiedClaimError) as ctx:
            self.checker.verify_script_segments(script["segments"], evidence_records)
        self.assertIn("failed verification", str(ctx.exception))
        self.assertIn("Segment 1", str(ctx.exception))

class TestPhase52UploadReconciliation(unittest.TestCase):
    def setUp(self):
        self.uploader = YoutubeUploader()
        self.pipeline = AutomationPipeline()
        self.test_dir = Path("/tmp/facts_ai_phase5_2_upload_test")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.used_topics_file = self.test_dir / "used_topics.txt"
        self.orig_base = config.BASE_DIR
        config.BASE_DIR = self.test_dir

    def tearDown(self):
        config.BASE_DIR = self.orig_base
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_reconcile_upload_matches_operation_id_even_with_title_mismatch(self):
        """Verify ambiguous upload reconciles successfully using unique operation ID when SEO title differs from topic."""
        topic_name = "Space Exploration"
        seo_title = "The Great Cosmic Mystery: 5 Mind-Blowing Facts"
        op_id = "FACTS-AI-OP-20261113-a1b2c3d4"
        
        mock_youtube = MagicMock()
        # Mock channel identity
        mock_youtube.channels().list.return_value.execute.return_value = {
            "items": [{"id": "UC_TEST_CHANNEL_123"}]
        }
        # Mock search finding video matching operation ID
        mock_youtube.search().list.return_value.execute.return_value = {
            "items": [{"id": {"videoId": "reconciled_vid_777"}}]
        }
        # Mock video details returning matching channel, marker in description, and matching SEO title
        mock_youtube.videos().list.return_value.execute.return_value = {
            "items": [{
                "snippet": {
                    "channelId": "UC_TEST_CHANNEL_123",
                    "title": seo_title,
                    "description": f"Mind blowing facts video.\n\n[Operation ID: {op_id}]"
                }
            }]
        }
        
        with patch.object(self.uploader, "get_authenticated_service", return_value=mock_youtube):
            confirmed_id = self.uploader.reconcile_pending_upload(operation_id=op_id, expected_title=seo_title)
            self.assertEqual(confirmed_id, "reconciled_vid_777")

    def test_reconcile_upload_rejects_video_missing_operation_marker(self):
        """Verify reconciliation rejects a video on the channel having same title but missing operation marker."""
        op_id = "FACTS-AI-OP-20261113-test999"
        seo_title = "Ancient Indian Temple Secrets"
        
        mock_youtube = MagicMock()
        mock_youtube.channels().list.return_value.execute.return_value = {
            "items": [{"id": "UC_TEST_CHANNEL_123"}]
        }
        mock_youtube.search().list.return_value.execute.return_value = {
            "items": [{"id": {"videoId": "different_video_999"}}]
        }
        # Video details has matching title but NO operation marker in description!
        mock_youtube.videos().list.return_value.execute.return_value = {
            "items": [{
                "snippet": {
                    "channelId": "UC_TEST_CHANNEL_123",
                    "title": seo_title,
                    "description": "An older video about temples without any operation ID."
                }
            }]
        }
        
        with patch.object(self.uploader, "get_authenticated_service", return_value=mock_youtube):
            confirmed_id = self.uploader.reconcile_pending_upload(operation_id=op_id, expected_title=seo_title)
            self.assertIsNone(confirmed_id, "Reconciled a video lacking the unique operation marker!")

    def test_reconcile_upload_rejects_different_channel(self):
        """Verify reconciliation rejects video matching title and marker if channel ID differs."""
        op_id = "FACTS-AI-OP-20261113-test888"
        
        mock_youtube = MagicMock()
        mock_youtube.channels().list.return_value.execute.return_value = {
            "items": [{"id": "UC_MY_CHANNEL"}]
        }
        mock_youtube.search().list.return_value.execute.return_value = {
            "items": [{"id": {"videoId": "hijacked_vid"}}]
        }
        mock_youtube.videos().list.return_value.execute.return_value = {
            "items": [{
                "snippet": {
                    "channelId": "UC_DIFFERENT_CHANNEL_ATTACKER",
                    "title": "Any Title",
                    "description": f"[Operation ID: {op_id}]"
                }
            }]
        }
        with patch.object(self.uploader, "get_authenticated_service", return_value=mock_youtube):
            confirmed_id = self.uploader.reconcile_pending_upload(operation_id=op_id)
            self.assertIsNone(confirmed_id, "Reconciled a video belonging to a different channel!")

class TestPhase52HindiLanguageStrictValidation(unittest.TestCase):
    def setUp(self):
        self.writer = ScriptWriter()
        self.vg = VoiceGenerator()

    def test_approved_technical_acronyms_permitted(self):
        """Verify approved technical acronyms (NASA, ISRO, AI, UPI, DNA) pass Devanagari validation."""
        valid_sentences = [
            "NASA और ISRO ने अंतरिक्ष में नए शोध किए हैं।",
            "AI और UPI तकनीक भारत में तेजी से बढ़ रही है।",
            "मानव DNA में जीवन के सभी रहस्य छिपे हैं।"
        ]
        for sentence in valid_sentences:
            self.assertTrue(self.writer.validate_hindi_text(sentence), f"Approved acronym rejected: {sentence}")

    def test_disallowed_english_narration_words_rejected(self):
        """Verify non-approved English words are strictly rejected even inside Hindi text."""
        invalid_sentences = [
            "अंतरिक्ष में completely silent माहौल रहता है।",
            "यह video आपको बेहद पसंद आएगा।",
            "वैज्ञानिकों ने secret खोज निकाली है।"
        ]
        for sentence in invalid_sentences:
            self.assertFalse(self.writer.validate_hindi_text(sentence), f"English narration accepted: {sentence}")

    def test_foreign_scripts_strictly_rejected(self):
        """Verify Arabic, Cyrillic, Greek, and Chinese characters are strictly rejected."""
        foreign_script_texts = [
            "अंतरिक्ष में سحر मौजूद है।",           # Arabic
            "ध्वनि तरंगें космос में नहीं चलतीं।",    # Cyrillic
            "विज्ञान और φυσική का रहस्य।",         # Greek
            "ब्रह्मांड का 宇宙 सच।"                 # Chinese
        ]
        for text in foreign_script_texts:
            self.assertFalse(self.writer.validate_hindi_text(text), f"Foreign script accepted: {text}")

    def test_hindi_combining_marks_and_zwj_zwnj_preserved(self):
        """Verify combining marks (matras) and format controls (ZWJ/ZWNJ) clean without token corruption."""
        # Test cleaning with ZWNJ and ZWJ
        raw_zwnj = "\u200cनमस्ते\u200d"
        cleaned = self.vg._clean_word_for_comparison(raw_zwnj)
        self.assertEqual(cleaned, "नमस्ते")
        
        # Test matras preserved
        self.assertEqual(self.vg._clean_word_for_comparison("शांत,"), "शांत")
        self.assertEqual(self.vg._clean_word_for_comparison("है।"), "है")
        self.assertEqual(self.vg._clean_word_for_comparison("नहीं;"), "नहीं")

    def test_shorts_segment_count_gate(self):
        """Verify Shorts script with fewer than 4 or more than 6 segments raises LanguageValidationError."""
        # 3 segments (too short)
        short_script = {
            "title": "छोटा शीर्षक",
            "segments": [
                {"text": "पहला भाग।", "type": "hook"},
                {"text": "दूसरा भाग।", "type": "body"},
                {"text": "तीसरा भाग।", "type": "cta"}
            ]
        }
        with self.assertRaises(LanguageValidationError):
            self.writer.validate_script_language(short_script, "hi", format_type="short")

        # 7 segments (too long)
        long_script = {
            "title": "लंबा शीर्षक",
            "segments": [{"text": f"भाग संख्या {i}।", "type": "body"} for i in range(7)]
        }
        with self.assertRaises(LanguageValidationError):
            self.writer.validate_script_language(long_script, "hi", format_type="short")

class TestPhase52FontSupportAndCLI(unittest.TestCase):
    def setUp(self):
        self.vb = VideoBuilder()

    def test_missing_devanagari_font_raises_font_missing_error(self):
        """Verify detect_devanagari_font(strict=True) raises FontMissingError when no font is installed."""
        mock_fonts_dir = MagicMock()
        mock_fonts_dir.exists.return_value = False
        with patch("subprocess.run") as mock_run:
            # Mock fc-list returning no Hindi font
            mock_run.return_value = Mock(returncode=0, stdout="")
            with patch.object(config, "FONTS_DIR", mock_fonts_dir):
                with patch("os.name", "posix"):
                    with self.assertRaises(FontMissingError) as ctx:
                        self.vb.detect_devanagari_font(strict=True)
                    self.assertIn("DEVANAGARI FONT MISSING", str(ctx.exception))

    def test_detected_devanagari_font_returned_when_available(self):
        """Verify detect_devanagari_font returns Noto Sans Devanagari when installed in fontconfig."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="Noto Sans Devanagari\n")
            with patch("os.name", "posix"):
                font = self.vb.detect_devanagari_font(strict=True)
                self.assertIn("Noto Sans Devanagari", font)

    def test_voice_selection_parameter_in_pipeline(self):
        """Verify AutomationPipeline accepts voice parameter and configures VoiceGenerator."""
        pipeline = AutomationPipeline(voice="hi-IN-SwaraNeural")
        self.assertEqual(pipeline.voice_generator.voice, "hi-IN-SwaraNeural")

if __name__ == "__main__":
    unittest.main()
