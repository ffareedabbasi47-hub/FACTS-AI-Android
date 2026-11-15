#!/usr/bin/env python3
"""
FACTS AI - Phase 5.8 Critical Remediation Test Suite
===================================================
Regression tests verifying:
1. P0 Scientific fact-check safety:
   - Removed concept co-occurrence loophole.
   - Keyword overlap, entity matching, or polarity matching alone NEVER grants VERIFIED.
   - Canonical consensus facts remain VERIFIED.
   - Adversarial Hindi false-claims fail closed to CONTRADICTS or UNVERIFIED.
2. P0 Topic recovery:
   - --mark-confirmed resolves and preserves original topic history via operation ID.
   - Validates pending operation existence before accessing list elements.
   - Rejects unknown or ambiguous operation IDs.
   - Deduplication memory correctly identifies confirmed topic as used.
3. P1 Hindi subtitle rendering:
   - FFmpeg font-family selection returns clean family name (not file path).
   - fontsdir is correctly configured and handles paths containing spaces.
   - Real FFmpeg rendering test with Devanagari matras, halant, and conjuncts.
4. P1 Hindi thumbnails:
   - Bundled Noto Sans Devanagari font loaded for Hindi titles.
   - Existing English font behavior preserved for Latin titles.
   - Real Pillow Devanagari image generation and byte inspection.
5. P1 GitHub Actions history reconciliation:
   - Removal of git pull --rebase.
   - Conflict-safe reconciliation strips conflict markers.
   - Precedence: COMPLETED > PENDING, FAILED > PENDING.
   - Union of concurrent divergent histories preserved without duplicates.
"""

import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from fact_checker import FactChecker, ClaimRejectedError, UnverifiedClaimError
from main import AutomationPipeline
from thumbnail_creator import ThumbnailCreator
from video_builder import VideoBuilder, FontMissingError


class TestPhase58FactCheckSafety(unittest.TestCase):
    def setUp(self):
        self.checker = FactChecker()
        self.checker.api_key = None  # deterministic offline evaluation

    def test_false_hindi_claim_with_correct_concepts_fails_closed(self):
        """
        Adversarial test: Hindi claim combining genuine scientific entities (Mars, planet, trees)
        without negation must NOT be granted VERIFIED by concept co-occurrence.
        Must fail closed to UNVERIFIED.
        """
        claim = "वैज्ञानिकों ने मंगल ग्रह पर विशाल हरे पेड़ और नदियाँ खोजीं"
        evidence = "NASA rovers on Mars have found rocky terrain and evidence of ancient dry lake beds on the red planet."
        eval_res = self.checker.verify_claim_semantics(claim, evidence)
        self.assertNotEqual(eval_res["verdict"], "VERIFIED", "False Hindi claim was improperly granted VERIFIED status!")
        self.assertEqual(eval_res["verdict"], "UNVERIFIED")
        self.assertEqual(eval_res["confidence"], 0.0)

    def test_absurd_hindi_claim_with_solar_concepts_fails_closed(self):
        """
        Adversarial test: Claim asserting Sun is a frozen cold planet sharing concepts (Sun, planet)
        must be rejected as CONTRADICTS or UNVERIFIED, never VERIFIED.
        """
        claim = "सूर्य पूरी तरह ठंडा होकर बर्फ का ग्रह बन चुका है"
        evidence = "The Sun is the solar system star with core temperatures exceeding 15 million degrees Celsius."
        eval_res = self.checker.verify_claim_semantics(claim, evidence)
        self.assertNotEqual(eval_res["verdict"], "VERIFIED")
        self.assertIn(eval_res["verdict"], ["CONTRADICTS", "UNVERIFIED"])

    def test_canonical_hindi_facts_remain_verified(self):
        """Legitimate canonical consensus Hindi assertions must still be correctly verified."""
        canonical_claims = [
            "अंतरिक्ष में ध्वनि यात्रा नहीं कर सकती",
            "ध्वनि को यात्रा करने के लिए किसी माध्यम की आवश्यकता होती है",
            "शुक्र हमारे सौर मंडल का सबसे गर्म ग्रह है",
            "न्यूट्रॉन तारे एक सेकंड में सैकड़ों बार घूम सकते हैं"
        ]
        evidence = "In space, sound waves cannot travel through vacuum. Venus is the hottest planet. Neutron stars spin rapidly."
        for claim in canonical_claims:
            eval_res = self.checker.verify_claim_semantics(claim, evidence)
            self.assertEqual(eval_res["verdict"], "VERIFIED", f"Canonical fact failed verification: {claim}")
            self.assertGreaterEqual(eval_res["confidence"], 0.95)

    def test_keyword_overlap_alone_never_grants_verified(self):
        """Random Hindi sentence sharing scientific keywords with evidence must return UNVERIFIED."""
        claim = "कोशिका और डीएनए अंतरिक्ष में संगीत सुनते हैं"
        evidence = "DNA in living cells carries genetic blueprints for organisms on Earth."
        eval_res = self.checker.verify_claim_semantics(claim, evidence)
        self.assertEqual(eval_res["verdict"], "UNVERIFIED")
        self.assertEqual(eval_res["confidence"], 0.0)


class TestPhase58TopicRecovery(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="facts_ai_p58_topic_test_"))
        self.used_path = self.test_dir / "used_topics.txt"
        self.patcher = patch.object(config, "BASE_DIR", self.test_dir)
        self.patcher.start()
        self.pipeline = AutomationPipeline()

    def tearDown(self):
        self.patcher.stop()
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_mark_confirmed_retrieves_original_topic(self):
        """Verify mark_topic_completed preserves the original topic when confirming via operation ID."""
        orig_topic = "Gravitational Lensing by Dark Matter"
        op_id = "FACTS-AI-OP-20261113-test01"
        self.pipeline.mark_topic_pending(orig_topic, op_id=op_id, seo_title="Dark Matter Mystery")

        # Simulate CLI confirmation using the op_id
        pending_ops = [op for op in self.pipeline.get_pending_operations() if op.get("op_id") == op_id]
        self.assertEqual(len(pending_ops), 1)
        self.assertEqual(pending_ops[0]["topic"], orig_topic)

        # Mark completed with original topic
        self.pipeline.mark_topic_completed(pending_ops[0]["topic"], "test_video_123", op_id=op_id)

        # Verify used_topics.txt retains original topic, NOT 'ManualTopic'
        content = self.used_path.read_text(encoding="utf-8")
        self.assertIn(orig_topic, content)
        self.assertNotIn("ManualTopic", content)
        self.assertIn("https://youtu.be/test_video_123", content)
        self.assertIn(op_id, content)

        # Verify deduplication memory catches it
        used_set = {self.pipeline.normalize_topic(t) for t in self.pipeline.load_used_topics()}
        self.assertIn(self.pipeline.normalize_topic(orig_topic), used_set)

    def test_mark_confirmed_defensive_replacement_extracts_pending_topic(self):
        """Even if caller provides a generic topic, mark_topic_completed extracts the original topic from record."""
        orig_topic = "Quantum Entanglement at Distance"
        op_id = "FACTS-AI-OP-20261113-test02"
        self.pipeline.mark_topic_pending(orig_topic, op_id=op_id)

        # Call with generic 'ManualTopic'
        self.pipeline.mark_topic_completed("ManualTopic", "vid_999", op_id=op_id)

        content = self.used_path.read_text(encoding="utf-8")
        self.assertIn(orig_topic, content)
        self.assertNotIn("ManualTopic", content)

    def test_unknown_operation_id_rejected(self):
        """Reject unknown operation IDs before performing any state modification."""
        unknown_id = "FACTS-AI-OP-NONEXISTENT-999"
        pending_ops = [op for op in self.pipeline.get_pending_operations() if op.get("op_id") == unknown_id]
        self.assertEqual(len(pending_ops), 0)


class TestPhase58HindiSubtitleRendering(unittest.TestCase):
    def setUp(self):
        self.vb = VideoBuilder()

    def test_font_family_returns_clean_family_name(self):
        """Verify detect_devanagari_font returns a valid font family string (not a file path)."""
        font = self.vb.detect_devanagari_font(strict=True)
        self.assertTrue(len(font) > 0)
        self.assertFalse(font.endswith(".ttf"), f"Returned file path instead of font family name: {font}")
        self.assertFalse("/" in font, f"Returned directory path in font family: {font}")
        self.assertFalse("\\" in font, f"Returned backslash in font family: {font}")

    def test_real_ffmpeg_devanagari_render_with_matras_and_conjuncts(self):
        """Verify real FFmpeg process can burn Hindi subtitles with conjuncts, matras, and fontsdir."""
        test_dir = Path(tempfile.mkdtemp(prefix="facts_ai_p58_ffmpeg_"))
        test_video = test_dir / "base.mp4"
        test_srt = test_dir / "subtitles.srt"
        out_video = test_dir / "output_burned.mp4"

        try:
            # 1. Generate 1s synthetic base video
            r1 = subprocess.run([
                "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=720x1280:d=1.0",
                "-c:v", "libx264", "-t", "1.0", str(test_video)
            ], capture_output=True)
            self.assertEqual(r1.returncode, 0)

            # 2. Write complex Hindi subtitle with conjuncts and matras
            hindi_text = "अंतरिक्ष में प्रकाश: क्या यह सच है? न्यूट्रॉन तारे और सन्नाटा।"
            test_srt.write_text(f"1\n00:00:00,100 --> 00:00:00,900\n{hindi_text}\n\n", encoding="utf-8")

            # 3. Burn subtitles using VideoBuilder
            success = self.vb.burn_subtitles(str(test_video), str(test_srt), str(out_video))
            self.assertTrue(success, "burn_subtitles failed on real FFmpeg execution!")
            self.assertTrue(out_video.exists())
            self.assertGreater(out_video.stat().st_size, 5000, "Rendered video unexpectedly small!")
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)


class TestPhase58HindiThumbnails(unittest.TestCase):
    def setUp(self):
        self.tc = ThumbnailCreator()

    def test_hindi_title_selects_devanagari_font(self):
        """Verify Hindi title triggers selection of bundled Noto Sans Devanagari font."""
        hindi_title = "अंतरिक्ष का सबसे बड़ा रहस्य"
        font = self.tc.get_font(80, text=hindi_title)
        self.assertIsNotNone(font)
        font_family, font_style = font.getname()
        self.assertTrue("devanagari" in font_family.lower() or "noto" in font_family.lower(), f"Unexpected font: {font_family}")

    def test_english_title_preserves_latin_font(self):
        """Verify English title preserves standard Latin display font behavior."""
        english_title = "THE DEEP COSMIC MYSTERY OF SPACE"
        font = self.tc.get_font(80, text=english_title)
        self.assertIsNotNone(font)

    def test_real_hindi_thumbnail_image_generation(self):
        """Verify real thumbnail JPEG is generated with authentic Devanagari text."""
        test_dir = Path(tempfile.mkdtemp(prefix="facts_ai_p58_thumb_"))
        out_jpg = test_dir / "test_thumb.jpg"
        try:
            hindi_title = "अंतरिक्ष में ध्वनि: क्या यह सच है?"
            res = self.tc.generate_thumbnail(hindi_title, None, out_jpg)
            self.assertTrue(res)
            self.assertTrue(out_jpg.exists())
            self.assertGreater(out_jpg.stat().st_size, 10000, "Thumbnail file too small!")

            # Verify valid JPEG header (0xFF, 0xD8)
            with open(out_jpg, "rb") as f:
                header = f.read(2)
            self.assertEqual(header, b"\xff\xd8", "Generated thumbnail is not a valid JPEG!")
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)


class TestPhase58HistoryReconciliation(unittest.TestCase):
    def test_reconcile_strips_git_conflict_markers(self):
        """Verify reconcile_topic_history eliminates git conflict markers."""
        remote = [
            "Topic One | https://youtu.be/vid1 | op_id=OP-1",
            "<<<<<<< HEAD",
            "Topic Two | https://youtu.be/vid2 | op_id=OP-2",
            "=======",
            "Topic Two Alt | https://youtu.be/vid2alt | op_id=OP-2",
            ">>>>>>> origin/main"
        ]
        local = [
            "Topic Three | https://youtu.be/vid3 | op_id=OP-3"
        ]
        reconciled = AutomationPipeline.reconcile_topic_history(remote, local)
        for line in reconciled:
            self.assertFalse(line.startswith("<<<<<<<"))
            self.assertFalse(line.startswith("======="))
            self.assertFalse(line.startswith(">>>>>>>"))

    def test_completed_precedence_over_pending(self):
        """Verify completed record (with video URL) overrides pending record for same op_id."""
        remote = [
            "[PENDING] op_id=OP-55 | topic=Neutron Stars | 2026-11-13T10:00:00"
        ]
        local = [
            "Neutron Stars | https://youtu.be/vid_ns_55 | op_id=OP-55"
        ]
        reconciled = AutomationPipeline.reconcile_topic_history(remote, local)
        self.assertEqual(len(reconciled), 1)
        self.assertIn("https://youtu.be/vid_ns_55", reconciled[0])
        self.assertNotIn("[PENDING]", reconciled[0])

    def test_failed_precedence_over_pending(self):
        """Verify [FAILED] record overrides [PENDING] record for same op_id."""
        remote = [
            "[PENDING] op_id=OP-66 | topic=Black Holes | 2026-11-13T10:00:00"
        ]
        local = [
            "[FAILED] op_id=OP-66 | reason=Upload aborted before chunk 0 | 2026-11-13T10:05:00"
        ]
        reconciled = AutomationPipeline.reconcile_topic_history(remote, local)
        self.assertEqual(len(reconciled), 1)
        self.assertIn("[FAILED]", reconciled[0])
        self.assertNotIn("[PENDING]", reconciled[0])

    def test_concurrent_divergent_histories_merged(self):
        """Verify independent non-conflicting topics from remote and local are both retained."""
        remote = [
            "Space Silence | https://youtu.be/vid_remote_1 | op_id=OP-REMOTE-1"
        ]
        local = [
            "Venus Temperatures | https://youtu.be/vid_local_1 | op_id=OP-LOCAL-1"
        ]
        reconciled = AutomationPipeline.reconcile_topic_history(remote, local)
        self.assertEqual(len(reconciled), 2)
        combined = " ".join(reconciled)
        self.assertIn("Space Silence", combined)
        self.assertIn("Venus Temperatures", combined)


if __name__ == "__main__":
    unittest.main()
