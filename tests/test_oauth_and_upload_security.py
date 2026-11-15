#!/usr/bin/env python3
"""
FACTS AI - Phase 3 OAuth & Upload Safety Mock Test Suite
=========================================================
Tests OAuth 2.0 credential loading, token refresh, headless CI guards,
resumable upload retries, and duplicate topic prevention using synthetic data.
Strictly isolated: ZERO live YouTube API calls or real credentials.
"""

import os
import sys
import json
import base64
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from youtube_uploader import YoutubeUploader
from main import AutomationPipeline
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError

SYNTHETIC_CLIENT_ID = "000000000000-synthetic.apps.googleusercontent.com"
SYNTHETIC_CLIENT_SECRET = "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"
SYNTHETIC_REFRESH_TOKEN = "1//synthetic_refresh_token_abcdef12345"
SYNTHETIC_TOKEN_DATA = {
    "token": "ya29.synthetic_access_token",
    "refresh_token": SYNTHETIC_REFRESH_TOKEN,
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_id": SYNTHETIC_CLIENT_ID,
    "client_secret": SYNTHETIC_CLIENT_SECRET,
    "scopes": ["https://www.googleapis.com/auth/youtube.upload"]
}

class TestOAuthAndUploadSecurity(unittest.TestCase):
    def setUp(self):
        self.uploader = YoutubeUploader()
        self.pipeline = AutomationPipeline()

    def test_in_memory_json_credential_loading(self):
        """Verify YOUTUBE_TOKEN_JSON environment variable loads valid in-memory credentials."""
        token_json = json.dumps(SYNTHETIC_TOKEN_DATA)
        with patch.dict(os.environ, {"YOUTUBE_TOKEN_JSON": token_json}):
            creds = self.uploader.load_credentials_from_env()
            self.assertIsNotNone(creds)
            self.assertIsInstance(creds, Credentials)
            self.assertEqual(creds.client_id, SYNTHETIC_CLIENT_ID)

    def test_in_memory_base64_credential_loading(self):
        """Verify YOUTUBE_TOKEN_JSON supports base64-encoded JSON securely."""
        token_b64 = base64.b64encode(json.dumps(SYNTHETIC_TOKEN_DATA).encode("utf-8")).decode("utf-8")
        with patch.dict(os.environ, {"YOUTUBE_TOKEN_JSON": token_b64}):
            creds = self.uploader.load_credentials_from_env()
            self.assertIsNotNone(creds)
            self.assertIsInstance(creds, Credentials)
            self.assertEqual(creds.client_id, SYNTHETIC_CLIENT_ID)

    def test_malformed_json_fails_gracefully(self):
        """Verify malformed JSON in environment variable does not crash and returns None."""
        with patch.dict(os.environ, {"YOUTUBE_TOKEN_JSON": "{malformed_json: bad"}):
            creds = self.uploader.load_credentials_from_env()
            self.assertIsNone(creds)

    def test_expired_token_automatic_refresh(self):
        """Verify expired credentials automatically invoke refresh(Request())."""
        mock_creds = MagicMock(spec=Credentials)
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = SYNTHETIC_REFRESH_TOKEN
        # When refresh is called, valid becomes True as in real Google Credentials
        def fake_refresh(req):
            mock_creds.valid = True
        mock_creds.refresh.side_effect = fake_refresh
        self.uploader.credentials_file = Path("/tmp/nonexistent_creds_refresh.json")

        with patch.object(self.uploader, "load_credentials_from_env", return_value=mock_creds):
            with patch("youtube_uploader.build") as mock_build:
                self.uploader.get_authenticated_service()
                mock_creds.refresh.assert_called_once()
                mock_build.assert_called_once_with("youtube", "v3", credentials=mock_creds)

    def test_headless_ci_blocks_interactive_browser_login(self):
        """Verify headless/CI environment raises RuntimeError instead of hanging on run_local_server."""
        self.uploader.credentials_file = Path("/tmp/nonexistent_creds_headless.json")
        with patch.object(self.uploader, "load_credentials_from_env", return_value=None):
            with patch.dict(os.environ, {"CI": "true"}):
                with self.assertRaises(RuntimeError) as ctx:
                    self.uploader.get_authenticated_service()
                self.assertIn("Headless/CI environment detected", str(ctx.exception))

    def test_privacy_status_public_accepted(self):
        """Verify privacy_status='public' is explicitly accepted as intended production behavior."""
        mock_youtube = MagicMock()
        mock_insert = MagicMock()
        mock_youtube.videos().insert.return_value = mock_insert
        mock_insert.next_chunk.return_value = (None, {"id": "synthetic_vid_123"})

        with patch.object(self.uploader, "get_authenticated_service", return_value=mock_youtube):
            with patch("youtube_uploader.MediaFileUpload"):
                video_id = self.uploader.upload_video(
                    video_path=Path("/tmp/synthetic_video.mp4"),
                    title="Synthetic Title",
                    description="Synthetic Desc",
                    tags=["facts", "ai"],
                    privacy_status="public"
                )
                self.assertEqual(video_id, "synthetic_vid_123")
                # Verify privacyStatus was passed as 'public' in body
                call_args = mock_youtube.videos().insert.call_args
                self.assertEqual(call_args[1]["body"]["status"]["privacyStatus"], "public")

    def test_privacy_status_invalid_rejected(self):
        """Verify unauthorized/typo privacy status strings are strictly rejected."""
        with self.assertRaises(ValueError) as ctx:
            self.uploader.upload_video(
                video_path=Path("/tmp/synthetic_video.mp4"),
                title="Synthetic Title",
                description="Synthetic Desc",
                tags=[],
                privacy_status="invalid_status"
            )
        self.assertIn("Invalid privacy status", str(ctx.exception))

    def test_resumable_upload_transient_chunk_retry(self):
        """Verify transient HTTP 503 during next_chunk() retries with backoff and succeeds."""
        mock_youtube = MagicMock()
        mock_insert = MagicMock()
        mock_youtube.videos().insert.return_value = mock_insert

        # Simulate 1 transient 503 error followed by successful upload
        err_response = Mock(status=503)
        mock_insert.next_chunk.side_effect = [
            HttpError(err_response, b"Service Unavailable"),
            (None, {"id": "resumed_vid_456"})
        ]

        with patch.object(self.uploader, "get_authenticated_service", return_value=mock_youtube):
            with patch("youtube_uploader.MediaFileUpload"):
                with patch("time.sleep"):  # Speed up test execution
                    video_id = self.uploader.upload_video(
                        video_path=Path("/tmp/synthetic_video.mp4"),
                        title="Retry Test Title",
                        description="Retry Test Desc",
                        tags=[],
                        privacy_status="public"
                    )
                    self.assertEqual(video_id, "resumed_vid_456")
                    self.assertEqual(mock_insert.next_chunk.call_count, 2)

    def test_resumable_upload_non_retryable_error_aborts(self):
        """Verify non-retryable 400 Bad Request error aborts cleanly without retrying."""
        mock_youtube = MagicMock()
        mock_insert = MagicMock()
        mock_youtube.videos().insert.return_value = mock_insert

        err_response = Mock(status=400)
        mock_insert.next_chunk.side_effect = HttpError(err_response, b"Bad Request")

        with patch.object(self.uploader, "get_authenticated_service", return_value=mock_youtube):
            with patch("youtube_uploader.MediaFileUpload"):
                video_id = self.uploader.upload_video(
                    video_path=Path("/tmp/synthetic_video.mp4"),
                    title="Abort Test Title",
                    description="Abort Test Desc",
                    tags=[],
                    privacy_status="public"
                )
                self.assertEqual(video_id, "")
                # Called only once because 400 is not retryable
                self.assertEqual(mock_insert.next_chunk.call_count, 1)

    def test_duplicate_topic_normalization_and_prevention(self):
        """Verify topic normalization matches topics regardless of case, punctuation, or whitespace."""
        raw_topic = "How UPI Auto-Debits Drain Money!"
        normalized = self.pipeline.normalize_topic(raw_topic)
        self.assertEqual(normalized, "howupiautodebitsdrainmoney")

        used_topics = ["How UPI auto-debits drain money!"]
        normalized_set = {self.pipeline.normalize_topic(t) for t in used_topics}
        self.assertIn(normalized, normalized_set)

    def test_secure_credentials_file_permissions(self):
        """Verify _save_credentials_file writes with mode 0600."""
        test_file = Path("/tmp/test_facts_ai_creds.json")
        mock_creds = MagicMock()
        mock_creds.to_json.return_value = json.dumps(SYNTHETIC_TOKEN_DATA)
        self.uploader.credentials_file = test_file

        try:
            self.uploader._save_credentials_file(mock_creds)
            self.assertTrue(test_file.exists())
            # In Linux/Unix, verify file mode permissions is 0600
            if os.name != "nt":
                mode = oct(test_file.stat().st_mode & 0o777)
                self.assertEqual(mode, "0o600")
        finally:
            if test_file.exists():
                test_file.unlink()

if __name__ == "__main__":
    unittest.main()
