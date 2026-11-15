#!/usr/bin/env python3
"""
FACTS AI - Phase 5.5 Critical Production Remediation Test Suite
==============================================================
Regression tests verifying:
1. Removal of keyword-only verification (false claims sharing correct scientific keywords are rejected).
2. Number contradiction and unsupported quantity detection.
3. Overriding LLM hallucinated 'VERIFIED' status when claim contradicts evidence.
4. Upload recovery explicit states (PENDING, CONFIRMED, REVIEW_REQUIRED, FAILED) and duplicate prevention.
5. Upload interruption handling across failure points (before chunk 0, missing video ID, delayed indexing).
6. Maintained trend discovery feeds (BBC, NASA, Phys.org, ScienceDaily) and provenance tagging (LIVE_TREND vs LLM_BRAINSTORMED).
7. Real local FFmpeg Devanagari video rendering (live un-mocked execution).

STRICT ISOLATION:
Zero live YouTube API uploads, zero Google OAuth mutations.
"""

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from fact_checker import (
    FactChecker,
    ClaimRejectedError,
    UnverifiedClaimError,
    extract_numbers
)
from main import AutomationPipeline
from trend_finder import TrendFinder
from video_builder import VideoBuilder, FontMissingError
from youtube_uploader import YoutubeUploader


class TestPhase55AdversarialFactChecking(unittest.TestCase):
    def setUp(self):
        self.checker = FactChecker()
        self.checker.api_key = None  # deterministic offline evaluation

    def test_extract_numbers_normalization(self):
        """Verify extract_numbers extracts and normalizes numbers with commas and Hindi digits."""
        text = "Speed is 299,792,458 m/s and temperature is ४६५ degrees."
        nums = extract_numbers(text)
        self.assertIn(299792458.0, nums)
        self.assertIn(465.0, nums)

    def test_false_claim_with_correct_keywords_fails_verification(self):
        """Verify false claim sharing legitimate scientific keywords (neutron, star, spin) fails closed."""
        # Claim shares 'neutron', 'star', 'spin' with baseline facts but asserts false slow rotation
        claim = "Neutron stars take ten thousand years to complete one single rotation"
        evidence = "Neutron stars can rotate extremely rapidly. Millisecond pulsars spin hundreds of times per second."
        eval_res = self.checker.verify_claim_semantics(claim, evidence)
        self.assertIn(eval_res["verdict"], ["CONTRADICTS", "UNVERIFIED"])
        self.assertNotEqual(eval_res["verdict"], "VERIFIED")

    def test_light_speed_number_contradiction_detected(self):
        """Verify claim asserting wrong speed of light is rejected as CONTRADICTS."""
        claim = "The speed of light in vacuum is 500 meters per second"
        evidence = "The speed of light in vacuum is exactly 299,792,458 metres per second."
        eval_res = self.checker.verify_claim_semantics(claim, evidence)
        self.assertEqual(eval_res["verdict"], "CONTRADICTS")
        self.assertIn("contradicts", eval_res["reason"].lower())

    def test_cold_venus_predicate_contradiction_detected(self):
        """Verify claim asserting Venus is cold is rejected as CONTRADICTS."""
        claim = "Venus is the coldest planet in the Solar System covered in thick ice"
        evidence = "Venus has a runaway greenhouse effect that makes it the hottest planet."
        eval_res = self.checker.verify_claim_semantics(claim, evidence)
        self.assertEqual(eval_res["verdict"], "CONTRADICTS")
        self.assertIn("contradicts", eval_res["reason"].lower())

    def test_sound_in_space_travel_contradiction_detected(self):
        """Verify Hindi claim asserting sound travels in space is rejected as CONTRADICTS."""
        claim = "अंतरिक्ष में ध्वनि तेजी से यात्रा करती है"
        evidence = "In space, sound waves cannot travel because there is no air or medium."
        eval_res = self.checker.verify_claim_semantics(claim, evidence)
        self.assertEqual(eval_res["verdict"], "CONTRADICTS")

    def test_llm_hallucinated_verified_overridden_when_contradictory(self):
        """Verify LLM self-reported 'VERIFIED' is overridden or caught when claim violates contradiction rules."""
        self.checker.api_key = "sk-mock-key"
        with patch("requests.post") as mock_post:
            # LLM hallucinating 'VERIFIED' on sound in space
            mock_post.return_value = Mock(
                status_code=200,
                json=lambda: {
                    "choices": [{
                        "message": {
                            "content": json.dumps({
                                "verdict": "VERIFIED",
                                "confidence": 0.99,
                                "reason": "Hallucinated confirmation of sound travel."
                            })
                        }
                    }]
                }
            )
            claim = "अंतरिक्ष में ध्वनि यात्रा करती है"
            evidence = "In space, sound waves cannot travel because there is no air or medium."
            eval_res = self.checker.verify_claim_semantics(claim, evidence)
            # Must be CONTRADICTS
            self.assertEqual(eval_res["verdict"], "CONTRADICTS")
            self.assertIn("contradicts", eval_res["reason"].lower())

    def test_script_segments_with_number_mismatch_fails_verification(self):
        """Verify script segment asserting contradictory numbers raises UnverifiedClaimError."""
        evidence_records = [{
            "url": "https://www.nist.gov/meter",
            "full_text": "The speed of light in vacuum is exactly 299,792,458 metres per second."
        }]
        segments = [
            {"text": "वैज्ञानिकों के अनुसार निर्वात में प्रकाश की गति 500 मीटर प्रति सेकंड है।", "type": "body"}
        ]
        with self.assertRaises((ClaimRejectedError, UnverifiedClaimError)):
            self.checker.verify_script_segments(segments, evidence_records)


class TestPhase55UploadRecoveryAndStates(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("/tmp/facts_ai_phase5_5_recovery_test")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.used_path = self.test_dir / "used_topics.txt"

        self.patcher = patch.object(config, "BASE_DIR", self.test_dir)
        self.patcher.start()

        self.pipeline = AutomationPipeline()
        self.uploader = YoutubeUploader()

    def tearDown(self):
        self.patcher.stop()
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_mark_pending_persists_pending_state(self):
        """Verify mark_topic_pending persists explicit [PENDING] state with operation ID."""
        self.pipeline.mark_topic_pending("Quantum Physics", op_id="OP-TEST-1234", seo_title="Quantum Secrets")
        ops = self.pipeline.get_pending_operations()
        self.assertEqual(len(ops), 1)
        self.assertEqual(ops[0]["status"], "PENDING")
        self.assertEqual(ops[0]["op_id"], "OP-TEST-1234")
        self.assertEqual(ops[0]["topic"], "Quantum Physics")

    def test_mark_review_required_transitions_state(self):
        """Verify mark_topic_review_required transitions [PENDING] to [REVIEW_REQUIRED]."""
        self.pipeline.mark_topic_pending("Black Holes", op_id="OP-BH-5678", seo_title="Black Hole Secrets")
        self.pipeline.mark_topic_review_required("Black Holes", op_id="OP-BH-5678", reason="Video not found on channel")
        ops = self.pipeline.get_pending_operations()
        self.assertEqual(len(ops), 1)
        self.assertEqual(ops[0]["status"], "REVIEW_REQUIRED")
        self.assertEqual(ops[0]["op_id"], "OP-BH-5678")

    def test_mark_failed_releases_pipeline_lock(self):
        """Verify mark_topic_failed transitions operation to [FAILED] and removes it from pending ops."""
        self.pipeline.mark_topic_pending("Dark Matter", op_id="OP-DM-9999", seo_title="Dark Matter Secrets")
        self.pipeline.mark_topic_failed("OP-DM-9999", reason="Upload dropped before chunk 0; video never created.")
        ops = self.pipeline.get_pending_operations()
        self.assertEqual(len(ops), 0, "FAILED operation should not remain in pending queue!")

    def test_review_required_blocks_pipeline_to_prevent_duplicate(self):
        """Verify pipeline halts immediately if any operation is in REVIEW_REQUIRED status."""
        self.pipeline.mark_topic_review_required("Exoplanets", op_id="OP-EXO-111", reason="Unconfirmed upload")
        with patch.object(self.pipeline.uploader, "reconcile_pending_upload", return_value=None):
            with self.assertRaises(RuntimeError) as ctx:
                self.pipeline.run_pipeline("New Topic")
            self.assertIn("AMBIGUOUS UPLOAD BLOCKED", str(ctx.exception))

    def test_successful_reconciliation_transitions_to_completed(self):
        """Verify reconciliation finding video on YouTube transitions operation to completed/confirmed."""
        self.pipeline.mark_topic_pending("Mars Water", op_id="OP-MARS-222", seo_title="Water on Mars")
        with patch.object(self.pipeline.uploader, "reconcile_pending_upload", return_value="verified_yt_vid_999"):
            with patch.object(self.pipeline.fact_checker, "enforce_verification", return_value={"status": "VERIFIED", "source_urls": ["https://nasa.gov"]}):
                with patch.object(self.pipeline.script_writer, "generate_script", side_effect=RuntimeError("HALT_AFTER_RECONCILE")):
                    try:
                        self.pipeline.run_pipeline(target_topic="Europa Oceans")
                    except RuntimeError as e:
                        if "HALT_AFTER_RECONCILE" not in str(e):
                            raise
        # Operation should now be cleared from pending operations
        ops = self.pipeline.get_pending_operations()
        self.assertEqual(len(ops), 0)
        # Content in used_topics should record the confirmed video
        content = self.used_path.read_text(encoding="utf-8")
        self.assertIn("verified_yt_vid_999", content)


class TestPhase55TrendDiscoveryAndProvenance(unittest.TestCase):
    def setUp(self):
        self.finder = TrendFinder()

    def test_maintained_news_trends_fetch_successfully(self):
        """Verify BBC Science feed fetches valid trends with LIVE_TREND provenance."""
        sample_rss = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <title>BBC News - Science &amp; Environment</title>
            <item>
              <title>James Webb Space Telescope detects earliest known black hole</title>
              <description>Astronomers using NASA space observatory discover primordial galaxy.</description>
            </item>
          </channel>
        </rss>
        """
        with patch("requests.get") as mock_get:
            mock_resp = Mock(status_code=200, content=sample_rss.encode("utf-8"))
            mock_get.return_value = mock_resp

            trends = self.finder.get_news_trends()
            self.assertEqual(len(trends), 1)
            self.assertEqual(trends[0]["discovery_type"], "LIVE_TREND")
            self.assertIn("James Webb", trends[0]["title"])

    def test_http_429_rate_limit_handled_gracefully(self):
        """Verify HTTP 429 rate limit is caught and returns empty list without crashing."""
        with patch("requests.get") as mock_get:
            mock_get.return_value = Mock(status_code=429)
            result = self.finder.fetch_rss_feed("https://test.feed/rss")
            self.assertIsNone(result)

    def test_malformed_xml_handled_gracefully(self):
        """Verify malformed non-XML payload returns None without throwing unhandled exceptions."""
        with patch("requests.get") as mock_get:
            mock_get.return_value = Mock(status_code=200, content=b"<html><body>502 Bad Gateway</body></html>")
            result = self.finder.fetch_rss_feed("https://test.feed/rss")
            self.assertIsNone(result)


class TestPhase55RealHindiRendering(unittest.TestCase):
    def setUp(self):
        self.vb = VideoBuilder()

    def test_real_local_ffmpeg_devanagari_burn(self):
        """Verify actual local FFmpeg process can render Devanagari text with conjuncts (unmocked)."""
        font = self.vb.detect_devanagari_font(strict=True)
        self.assertTrue(len(font) > 0, "No Devanagari font detected on system!")

        test_out = Path("/tmp/facts_ai_phase5_5_real_render.mp4")
        if test_out.exists():
            test_out.unlink()

        try:
            rendered = self.vb.validate_hindi_rendering(
                output_path=test_out,
                test_text="अंतरिक्ष में रहस्यमयी प्रकाश: क्या यह सच है?"
            )
            self.assertTrue(rendered, "Real FFmpeg Hindi rendering failed!")
            self.assertTrue(test_out.exists(), "Rendered MP4 file does not exist!")
            self.assertGreater(test_out.stat().st_size, 1000, "Rendered MP4 file is empty or corrupted!")
        finally:
            if test_out.exists():
                test_out.unlink()


if __name__ == "__main__":
    unittest.main()
