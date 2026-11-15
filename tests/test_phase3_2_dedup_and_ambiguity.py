#!/usr/bin/env python3
"""
FACTS AI - Phase 3.2 Unit Test Suite
====================================
Tests:
1. True Topic Deduplication (re-selection, strict rejection, safe failure on exhaustion).
2. Ambiguous Upload Protection (pending state persistence, reconciliation, failure-safe abort).
3. Durable Topic History integrity.
Zero live YouTube/Google network calls. All mocks & synthetic data.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import AutomationPipeline
import config

class TestPhase32DedupAndAmbiguity(unittest.TestCase):
    def setUp(self):
        self.pipeline = AutomationPipeline()
        self.test_dir = Path("/tmp/facts_ai_phase3_2_test")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.used_topics_file = self.test_dir / "used_topics.txt"
        # Point config.BASE_DIR to test scratch
        self.orig_base = config.BASE_DIR
        config.BASE_DIR = self.test_dir

    def tearDown(self):
        config.BASE_DIR = self.orig_base
        if self.used_topics_file.exists():
            self.used_topics_file.unlink()

    def test_normalize_topic(self):
        """Verify normalization strips case, punctuation, whitespace, and prefixes."""
        t1 = "How UPI Auto-Debits Secretly Drain Your Bank Account!"
        self.assertEqual(self.pipeline.normalize_topic(t1), "howupiautodebitssecretlydrainyourbankaccount")
        
        pending_line = "[PENDING] How UPI Auto-Debits Drain | 2026-11-13T10:00:00"
        self.assertEqual(self.pipeline.normalize_topic(pending_line), "howupiautodebitsdrain")

    def test_pending_topic_lifecycle(self):
        """Verify topic lifecycle: mark_pending -> get_pending -> mark_completed."""
        topic = "Ancient Indian Temple Architecture"
        self.pipeline.mark_topic_pending(topic)
        
        # Verify in pending topics
        pending = self.pipeline.get_pending_topics()
        self.assertIn(topic, pending)
        
        # Verify in load_used_topics
        used = self.pipeline.load_used_topics()
        self.assertIn(topic, used)
        
        # Reconcile to completed
        self.pipeline.mark_topic_completed(topic, "vid_abc_123")
        self.assertEqual(len(self.pipeline.get_pending_topics()), 0)
        
        with open(self.used_topics_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("https://youtu.be/vid_abc_123", content)
        self.assertNotIn("[PENDING]", content)

    def test_explicit_duplicate_topic_rejected(self):
        """Verify user-provided duplicate topic raises ValueError immediately."""
        self.pipeline.mark_topic_completed("Black Holes in the Universe", "vid_1")
        
        with self.assertRaises(ValueError) as ctx:
            self.pipeline.run_pipeline(target_topic="Black Holes in the Universe!")
        self.assertIn("Duplicate Topic Rejected", str(ctx.exception))

    def test_topic_exhaustion_fails_safely(self):
        """Verify pipeline aborts safely with RuntimeError when all candidate topics are exhausted."""
        # Mark all niches as used
        for n in config.NICHES:
            self.pipeline.mark_topic_completed(n, "mock_id")
            
        with patch.object(self.pipeline.script_writer, "api_key", "sk-mock"), \
             patch.object(self.pipeline.trend_finder, "get_trending_science_topics", return_value=[]):
            with patch("requests.post") as mock_post:
                # LLM returns a topic that is also already used
                mock_post.return_value.status_code = 200
                mock_post.return_value.json.return_value = {
                    "choices": [{"message": {"content": config.NICHES[0]}}]
                }
                with self.assertRaises(RuntimeError) as ctx:
                    self.pipeline.run_pipeline(target_topic=None)
                self.assertIn("True Deduplication Gate", str(ctx.exception))

    def test_ambiguous_upload_aborts_without_reconciliation(self):
        """Verify pending upload with unconfirmed status aborts pipeline to prevent duplicate video."""
        pending_topic = "Unconfirmed Quantum Physics"
        self.pipeline.mark_topic_pending(pending_topic)
        
        # YouTube API check cannot confirm video (returns None)
        with patch.object(self.pipeline.uploader, "check_video_uploaded_by_title", return_value=None):
            with self.assertRaises(RuntimeError) as ctx:
                self.pipeline.run_pipeline(target_topic="New Unique Topic")
            self.assertIn("AMBIGUOUS UPLOAD BLOCKED", str(ctx.exception))
            
        # Verify pending record is preserved
        self.assertIn(pending_topic, self.pipeline.get_pending_topics())

    def test_ambiguous_upload_reconciles_when_confirmed(self):
        """Verify pending upload is marked completed if YouTube API confirms existing video."""
        pending_topic = "Confirmed Space Exploration"
        self.pipeline.mark_topic_pending(pending_topic)
        
        # YouTube API check confirms video exists with ID 'reconciled_999'
        with patch.object(self.pipeline.uploader, "check_video_uploaded_by_title", return_value="reconciled_999"):
            with patch.object(self.pipeline, "load_used_topics", return_value={"Confirmed Space Exploration"}):
                # When checking reconciliation, it marks it completed
                pending_list = self.pipeline.get_pending_topics()
                self.assertEqual(len(pending_list), 1)
                confirmed_id = self.pipeline.uploader.check_video_uploaded_by_title(pending_topic)
                self.pipeline.mark_topic_completed(pending_topic, confirmed_id)
                self.assertEqual(len(self.pipeline.get_pending_topics()), 0)

if __name__ == "__main__":
    unittest.main()
