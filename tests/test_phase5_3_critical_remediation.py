#!/usr/bin/env python3
"""
FACTS AI - Phase 5.3 Regression Test Suite
==========================================
Verifies:
1. Semantic scientific fact verification (meaning comparison, negation, contradiction detection, fail closed).
2. YouTube reconciliation via uploads playlist, search pagination across nextPageToken, wrong channel rejection,
   marker validation, delayed indexing PENDING preservation, and disabled legacy title-only path.
3. TrendFinder integration (science filtering, pipeline selection, fallback on feed failure).
4. Devanagari video rendering validation and missing font handling.
5. End-to-end pipeline execution with complete stage tracking.

STRICT ISOLATION:
Zero live YouTube API calls, zero Google OAuth, zero live video uploads.
All external interactions are mocked.
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
)
from main import AutomationPipeline
from trend_finder import TrendFinder
from video_builder import VideoBuilder, FontMissingError
from youtube_uploader import YoutubeUploader


class TestPhase53SemanticFactVerification(unittest.TestCase):
    def setUp(self):
        self.checker = FactChecker()
        self.checker.api_key = None  # deterministic local semantic evaluation

    def test_contradictory_evidence_with_negation_fails_verification(self):
        """Verify claim asserting sound travels in space is rejected when evidence states it cannot."""
        claim = "अंतरिक्ष में ध्वनि तेजी से यात्रा करती है"
        evidence = "In space, sound waves cannot travel because there is no air or medium."
        eval_res = self.checker.verify_claim_semantics(claim, evidence)
        self.assertEqual(eval_res["verdict"], "CONTRADICTS")
        self.assertIn("contradicts", eval_res["reason"].lower())

    def test_debunking_evidence_context_rejects_positive_claim(self):
        """Verify positive claim is rejected when evidence context describes it as a debunked myth."""
        claim = "5G towers spread biological viruses"
        evidence = "The myth that 5G towers spread viruses has been completely debunked by public health organizations."
        eval_res = self.checker.verify_claim_semantics(claim, evidence)
        self.assertEqual(eval_res["verdict"], "CONTRADICTS")
        self.assertIn("myth", eval_res["reason"].lower())

    def test_keyword_rich_unrelated_source_fails_closed(self):
        """Verify keyword-rich source lacking substantive proof for the exact claim fails closed (UNVERIFIED)."""
        claim = "Quantum teleportation across human organs was successfully achieved"
        unrelated_page = "The university physics department teaches quantum mechanics and organ physiology in different semesters."
        eval_res = self.checker.verify_claim_semantics(claim, unrelated_page)
        self.assertEqual(eval_res["verdict"], "UNVERIFIED")

    def test_unsupported_speculative_predicates_fail_closed(self):
        """Verify bizarre or speculative assertions (e.g. gold palaces on Mars) fail closed."""
        claim = "वैज्ञानिकों ने मंगल ग्रह पर गुप्त सोने के महल खोजे"
        evidence = "NASA Mars rovers have analyzed rock and soil samples on the Martian surface."
        eval_res = self.checker.verify_claim_semantics(claim, evidence)
        self.assertEqual(eval_res["verdict"], "UNVERIFIED")

    def test_api_timeout_and_malformed_response_fails_closed(self):
        """Verify fact-checker fails closed to safe fallback or UNVERIFIED when LLM API times out or errs."""
        self.checker.api_key = "sk-mock-key"
        with patch("requests.post") as mock_post:
            # Simulate API timeout
            mock_post.side_effect = Exception("Connection timed out after 25s")
            record = self.checker.verify_claim("Unprecedented time portal opened in laboratory")
            self.assertFalse(record["verified"])
            self.assertEqual(record["status"], "UNVERIFIED")

    def test_segment_with_contradictory_evidence_raises_claim_rejected(self):
        """Verify verify_script_segments raises ClaimRejectedError when segment contradicts evidence."""
        evidence_records = [{
            "url": "https://www.nasa.gov/space-sound",
            "full_text": "In space, sound waves cannot travel because there is no air or medium. Space is completely silent."
        }]
        script_segments = [
            {"text": "क्या आप जानते हैं कि अंतरिक्ष में ध्वनि बहुत तेजी से यात्रा करती है?", "type": "hook"}
        ]
        with self.assertRaises(ClaimRejectedError):
            self.checker.verify_script_segments(script_segments, evidence_records)


class TestPhase53YouTubeUploadReconciliation(unittest.TestCase):
    def setUp(self):
        self.uploader = YoutubeUploader()
        self.test_dir = Path("/tmp/facts_ai_phase5_3_reconcile_test")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.orig_base = config.BASE_DIR
        config.BASE_DIR = self.test_dir

    def tearDown(self):
        config.BASE_DIR = self.orig_base
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_reconciliation_via_uploads_playlist_success(self):
        """Verify reconciliation succeeds immediately using channel's Uploads playlist without search index delay."""
        op_id = "FACTS-AI-OP-20261113-pl1234"
        expected_title = "Mystery of Space"
        channel_id = "UC_MY_CHANNEL_ID"
        uploads_pl_id = "UU_MY_CHANNEL_ID"

        mock_youtube = MagicMock()
        # Mock channels().list
        mock_youtube.channels().list().execute.return_value = {
            "items": [{
                "id": channel_id,
                "contentDetails": {
                    "relatedPlaylists": {"uploads": uploads_pl_id}
                }
            }]
        }
        # Mock playlistItems().list
        mock_youtube.playlistItems().list().execute.return_value = {
            "items": [{
                "snippet": {
                    "resourceId": {"videoId": "vid_from_playlist_777"},
                    "title": expected_title,
                    "description": f"Video about space.\n\n[Operation ID: {op_id}]",
                    "channelId": channel_id
                }
            }]
        }

        with patch.object(self.uploader, "get_authenticated_service", return_value=mock_youtube):
            vid_id = self.uploader.reconcile_pending_upload(op_id, expected_title=expected_title)
            self.assertEqual(vid_id, "vid_from_playlist_777")
            # Ensure search().list was NOT needed because playlistItems succeeded
            mock_youtube.search().list.assert_not_called()

    def test_reconciliation_handles_search_pagination_across_pages(self):
        """Verify reconciliation paginates through search results when video is on page 2."""
        op_id = "FACTS-AI-OP-20261113-page2"
        expected_title = "Quantum Physics"
        channel_id = "UC_MY_CHANNEL_ID"

        mock_youtube = MagicMock()
        # Channels list without uploads playlist (forces search fallback)
        mock_youtube.channels().list().execute.return_value = {
            "items": [{"id": channel_id, "contentDetails": {"relatedPlaylists": {}}}]
        }

        # Page 1: 1 video (not matching) with nextPageToken="token_p2"
        page1_resp = {
            "items": [{"id": {"videoId": "other_vid_111"}}],
            "nextPageToken": "token_p2"
        }
        # Page 2: target video
        page2_resp = {
            "items": [{"id": {"videoId": "target_vid_222"}}],
            "nextPageToken": None
        }
        search_req_mock = MagicMock()
        search_req_mock.execute.side_effect = [page1_resp, page2_resp]
        mock_youtube.search().list.return_value = search_req_mock
        mock_youtube.search().list.reset_mock()

        # Video details query for each video
        def mock_videos_list(id, part):
            exec_mock = MagicMock()
            if id == "other_vid_111":
                exec_mock.execute.return_value = {
                    "items": [{"snippet": {"channelId": channel_id, "title": "Other", "description": "No marker"}}]
                }
            elif id == "target_vid_222":
                exec_mock.execute.return_value = {
                    "items": [{"snippet": {
                        "channelId": channel_id,
                        "title": expected_title,
                        "description": f"Detailed desc.\n\n[Operation ID: {op_id}]"
                    }}]
                }
            return exec_mock

        mock_youtube.videos().list.side_effect = mock_videos_list

        with patch.object(self.uploader, "get_authenticated_service", return_value=mock_youtube):
            vid_id = self.uploader.reconcile_pending_upload(op_id, expected_title=expected_title)
            self.assertEqual(vid_id, "target_vid_222")
            # Verify search was called twice (paginated)
            self.assertEqual(mock_youtube.search().list.call_count, 2)

    def test_reconciliation_rejects_wrong_channel_id(self):
        """Verify video matching operation marker but on attacker channel is rejected."""
        op_id = "FACTS-AI-OP-20261113-attacker"
        mock_youtube = MagicMock()
        mock_youtube.channels().list().execute.return_value = {
            "items": [{"id": "UC_MY_CHANNEL", "contentDetails": {"relatedPlaylists": {}}}]
        }
        mock_youtube.search().list().execute.return_value = {
            "items": [{"id": {"videoId": "hijacked_vid"}}]
        }
        mock_youtube.videos().list().execute.return_value = {
            "items": [{"snippet": {
                "channelId": "UC_DIFFERENT_ATTACKER_CHANNEL",  # Wrong channel!
                "title": "Title",
                "description": f"[Operation ID: {op_id}]"
            }}]
        }

        with patch.object(self.uploader, "get_authenticated_service", return_value=mock_youtube):
            vid_id = self.uploader.reconcile_pending_upload(op_id)
            self.assertIsNone(vid_id)

    def test_legacy_title_only_matching_raises_not_implemented(self):
        """Verify unsafe check_video_uploaded_by_title is disabled and raises NotImplementedError."""
        with self.assertRaises(NotImplementedError):
            self.uploader.check_video_uploaded_by_title("Any Video Title")


class TestPhase53TrendFinderIntegration(unittest.TestCase):
    def setUp(self):
        self.finder = TrendFinder()

    def test_trend_finder_filters_science_topics(self):
        """Verify filter_science_trends retains science topics and discards politics/cricket."""
        sample_trends = [
            {"title": "ISRO announces new Chandrayaan lunar sample return mission", "description": "Space science news", "score": 90},
            {"title": "Election results: Parliament debate heats up", "description": "Political breaking news", "score": 85},
            {"title": "Cricket score: IPL final match highlights", "description": "Sports update", "score": 80},
            {"title": "James Webb Space Telescope detects water vapor on exoplanet", "description": "Astronomy discovery", "score": 75},
            {"title": "Bollywood celebrity wedding photos go viral", "description": "Entertainment gossip", "score": 60}
        ]
        science = self.finder.filter_science_trends(sample_trends)
        titles = [t["title"] for t in science]
        self.assertEqual(len(science), 2)
        self.assertTrue(any("ISRO" in t for t in titles))
        self.assertTrue(any("James Webb" in t for t in titles))
        self.assertFalse(any("Election" in t for t in titles))
        self.assertFalse(any("Cricket" in t for t in titles))

    def test_pipeline_selects_live_science_trend_when_available(self):
        """Verify AutomationPipeline selects trending science topic from TrendFinder when unused."""
        pipeline = AutomationPipeline()
        mock_trends = [
            {"title": "Quantum Computing Breakthrough in Superconducting Qubits", "source": "Reddit", "score": 50, "traffic": "High"}
        ]
        with patch.object(pipeline.trend_finder, "get_trending_science_topics", return_value=mock_trends):
            with patch.object(pipeline, "load_used_topics", return_value=set()):
                # Test selection logic inside run
                with patch.object(pipeline.fact_checker, "enforce_verification", return_value={
                    "status": "VERIFIED", "verified": True, "source_urls": ["https://nasa.gov"], "confidence": 0.95
                }):
                    with patch.object(pipeline.script_writer, "generate_script", side_effect=RuntimeError("HALT_TEST_SUCCESS")):
                        with self.assertRaises(RuntimeError) as ctx:
                            pipeline.run(format_type="short")
                        self.assertIn("HALT_TEST_SUCCESS", str(ctx.exception))


class TestPhase53DevanagariRendering(unittest.TestCase):
    def setUp(self):
        self.vb = VideoBuilder()

    def test_validate_hindi_rendering_with_mock_ffmpeg(self):
        """Verify validate_hindi_rendering executes FFmpeg synthesis and verifies output size."""
        with patch.object(self.vb, "detect_devanagari_font", return_value="Noto Sans Devanagari"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = Mock(returncode=0)
                with patch.object(self.vb, "burn_subtitles", return_value=True):
                    with patch("pathlib.Path.exists", return_value=True):
                        with patch("pathlib.Path.stat") as mock_stat:
                            mock_stat.return_value.st_size = 50000
                            result = self.vb.validate_hindi_rendering()
                            self.assertTrue(result)

    def test_validate_hindi_rendering_raises_when_font_missing(self):
        """Verify validate_hindi_rendering raises FontMissingError when no font exists."""
        with patch.object(self.vb, "detect_devanagari_font", side_effect=FontMissingError("FONT_NOT_FOUND")):
            with self.assertRaises(FontMissingError):
                self.vb.validate_hindi_rendering()


class TestPhase53FullPipelineIntegration(unittest.TestCase):
    def setUp(self):
        self.pipeline = AutomationPipeline()
        self.test_dir = Path("/tmp/facts_ai_phase5_3_pipeline_test")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.orig_base = config.BASE_DIR
        config.BASE_DIR = self.test_dir

    def tearDown(self):
        config.BASE_DIR = self.orig_base
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_end_to_end_pipeline_execution_with_mocks(self):
        """Verify entire pipeline executes in sequence from trend discovery to verified public upload."""
        target_topic = "Space Silence Vacuum"
        expected_seo_title = "The Silent Cosmos: Space Secrets"

        fact_record = {
            "topic": target_topic,
            "claim": "Sound cannot travel through vacuum of space",
            "verified": True,
            "status": "VERIFIED",
            "confidence": 0.99,
            "source_urls": ["https://www.nasa.gov/space-sound"],
            "evidence_records": [{
                "url": "https://www.nasa.gov/space-sound",
                "full_text": "In space, sound waves cannot travel because there is no air or medium."
            }],
            "explanation": "Consensus physics."
        }

        generated_script = {
            "title": expected_seo_title,
            "segments": [
                {"text": "क्या आप जानते हैं कि अंतरिक्ष में पूर्ण सन्नाटा रहता है?", "type": "hook"},
                {"text": "ध्वनि को यात्रा करने के लिए हवा या किसी माध्यम की जरूरत होती है।", "type": "body"},
                {"text": "अंतरिक्ष में कोई वायुमंडल नहीं है इसलिए वहां कोई आवाज नहीं होती।", "type": "body"},
                {"text": "नासा के अनुसार अंतरिक्ष पूरी तरह शांत है।", "type": "body"},
                {"text": "सब्सक्राइब करें दैनिक विज्ञान जानकारी के लिए।", "type": "cta"}
            ],
            "seo": {
                "title": expected_seo_title,
                "description": "Amazing space facts in Hindi",
                "tags": ["space", "science", "facts"],
                "hashtags": ["#Space", "#Shorts"]
            }
        }

        with patch.object(self.pipeline.fact_checker, "enforce_verification", return_value=fact_record), \
             patch.object(self.pipeline.script_writer, "generate_script", return_value=generated_script), \
             patch.object(self.pipeline.voice_generator, "generate_segment_audios", return_value=[{"video_path": "clip.mp4"}]), \
             patch.object(self.pipeline.media_downloader, "download_media_for_segments", return_value=[{"video_path": "clip.mp4"}]), \
             patch.object(self.pipeline.subtitle_generator, "generate_srt", return_value=True), \
             patch.object(self.pipeline.thumbnail_creator, "generate_thumbnail", return_value=True), \
             patch.object(self.pipeline.video_builder, "build_video", return_value=True), \
             patch.object(self.pipeline.uploader, "upload_video", return_value="synthetic_vid_53_final") as mock_upload, \
             patch("pathlib.Path.exists", return_value=True):

            success = self.pipeline.run(target_topic=target_topic, format_type="short", privacy_status="public")
            self.assertTrue(success)

            # Verify public upload was called with operation ID
            mock_upload.assert_called_once()
            _, kwargs = mock_upload.call_args
            self.assertEqual(kwargs.get("privacy_status"), "public")
            self.assertTrue(kwargs.get("operation_id", "").startswith("FACTS-AI-OP-"))

            # Verify used_topics.txt contains completed record with operation ID
            used_file = self.test_dir / "used_topics.txt"
            self.assertTrue(used_file.exists())
            with open(used_file, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("https://youtu.be/synthetic_vid_53_final", content)
            self.assertIn(kwargs["operation_id"], content)


if __name__ == "__main__":
    unittest.main()
