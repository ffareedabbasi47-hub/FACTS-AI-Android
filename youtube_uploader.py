import os
import sys
import json
import base64
import random
import socket
import time
import logging
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("YoutubeUploader")

class YoutubeUploader:
    def __init__(self):
        self.scopes = ["https://www.googleapis.com/auth/youtube.upload"]
        self.client_secrets_file = config.YOUTUBE_CLIENT_SECRETS_FILE
        self.credentials_file = config.YOUTUBE_CREDENTIALS_FILE

    def _save_credentials_file(self, creds):
        """Saves authorized user credentials to local JSON with restricted 0600 permissions."""
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
            mode = 0o600
            creds_json = creds.to_json()
            try:
                fd = os.open(str(self.credentials_file), flags, mode)
                with open(fd, "w", encoding="utf-8") as f:
                    f.write(creds_json)
            except Exception:
                with open(self.credentials_file, "w", encoding="utf-8") as f:
                    f.write(creds_json)
            logger.info(f"YouTube credentials securely saved to {self.credentials_file}")
        except Exception as e:
            logger.warning(f"Could not persist credentials to file: {e}")

    def load_credentials_from_env(self):
        """Loads and parses credentials JSON from environment variable (in-memory)."""
        token_str = os.getenv("YOUTUBE_TOKEN_JSON") or os.getenv("YOUTUBE_CREDENTIALS_BASE64")
        if not token_str:
            return None

        token_str = token_str.strip()
        # Handle both raw JSON and base64-encoded JSON safely without printing secret
        if not token_str.startswith("{"):
            try:
                token_str = base64.b64decode(token_str).decode("utf-8")
            except Exception as b64_err:
                logger.error(f"Failed to decode base64 credentials from environment: {b64_err}")
                return None

        try:
            token_info = json.loads(token_str)
            return Credentials.from_authorized_user_info(token_info, self.scopes)
        except Exception as json_err:
            logger.error(f"Failed to parse credentials JSON from environment: {json_err}")
            return None

    def get_authenticated_service(self):
        """Authenticates user via OAuth2 and returns the YouTube API service object."""
        creds = None
        
        # 1. First check environment variable (preferred for headless CI/CD)
        creds = self.load_credentials_from_env()
        if creds:
            logger.info("Loaded YouTube OAuth credentials from environment variable.")

        # 2. Check local credentials JSON file
        if not creds and self.credentials_file.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.credentials_file), self.scopes)
                logger.info("Loaded YouTube OAuth credentials from local file.")
            except Exception as e:
                logger.warning(f"Failed to load cached credentials from file: {e}")
                creds = None
                
        # 3. Refresh expired credentials
        if creds and creds.expired and creds.refresh_token:
            try:
                logger.info("Refreshing expired YouTube OAuth credentials...")
                creds.refresh(Request())
                if self.credentials_file.exists():
                    self._save_credentials_file(creds)
            except Exception as e:
                logger.error(f"Failed to refresh credentials: {e}")
                creds = None

        # 4. If credentials still not valid/present, handle interactive or headless environment
        if not creds or not creds.valid:
            is_headless = (
                os.getenv("CI") == "true" or
                os.getenv("GITHUB_ACTIONS") == "true" or
                not sys.stdin.isatty()
            )
            if is_headless:
                error_msg = (
                    "Headless/CI environment detected: interactive OAuth browser login is disabled. "
                    "Please provide valid credentials via the YOUTUBE_TOKEN_JSON repository secret."
                )
                logger.critical(error_msg)
                raise RuntimeError(error_msg)

            if not self.client_secrets_file.exists():
                logger.critical(
                    f"\n=======================================================\n"
                    f"CRITICAL ERROR: '{self.client_secrets_file.name}' not found!\n"
                    f"To enable YouTube uploads, follow these steps:\n"
                    f"1. Go to Google Cloud Console (https://console.cloud.google.com/)\n"
                    f"2. Create a project and enable 'YouTube Data API v3'.\n"
                    f"3. Go to 'APIs & Services' -> 'Credentials'.\n"
                    f"4. Create an 'OAuth 2.0 Client ID' (Desktop App).\n"
                    f"5. Download the JSON, rename it to 'client_secrets.json', and place it in: {self.client_secrets_file.parent}\n"
                    f"=======================================================\n"
                )
                raise FileNotFoundError(f"Missing {self.client_secrets_file.name}")

            logger.info("Starting local OAuth consent screen login flow...")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.client_secrets_file), self.scopes
            )
            creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
            self._save_credentials_file(creds)

        return build("youtube", "v3", credentials=creds)

    def reconcile_pending_upload(self, operation_id: str, expected_title: str = None) -> Optional[str]:
        """
        Reconciles an ambiguous upload using authenticated channel identity and unique operation marker.
        1. Queries authenticated channel ID and Uploads playlist ID to verify channel ownership.
        2. Inspects channel's recent uploads directly via playlistItems to bypass search indexing latency.
        3. Falls back to channel-scoped search with pagination across nextPageToken.
        4. Verifies channel ID, exact operation marker in description, and expected title.
        5. NEVER confirms an upload using title alone.
        Returns confirmed video_id if verified, or None if uncertain.
        """
        if not operation_id:
            logger.warning("reconcile_pending_upload called without operation_id. Cannot reconcile safely.")
            return None

        marker = f"[Operation ID: {operation_id}]"

        try:
            youtube = self.get_authenticated_service()

            # 1. Verify channel identity and retrieve channel's Uploads playlist
            channels_response = youtube.channels().list(mine=True, part="id,contentDetails").execute()
            ch_items = channels_response.get("items", [])
            if not ch_items:
                logger.warning("Unable to verify channel identity from YouTube API. Outcome remains uncertain.")
                return None
            channel_id = ch_items[0].get("id")
            uploads_playlist_id = ch_items[0].get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")

            # 2. Strategy A: Channel-scoped listing from Uploads playlist (immune to search indexing delay)
            if uploads_playlist_id:
                try:
                    page_token = None
                    pages_checked = 0
                    max_pages = 5

                    while pages_checked < max_pages:
                        pages_checked += 1
                        kwargs = {
                            "playlistId": uploads_playlist_id,
                            "part": "snippet",
                            "maxResults": 50
                        }
                        if page_token:
                            kwargs["pageToken"] = page_token

                        pl_response = youtube.playlistItems().list(**kwargs).execute()
                        items = pl_response.get("items", [])

                        for item in items:
                            snippet = item.get("snippet", {})
                            vid_id = snippet.get("resourceId", {}).get("videoId")
                            vid_desc = snippet.get("description", "")
                            vid_title = snippet.get("title", "")
                            vid_channel = snippet.get("channelId", "")

                            if not vid_id:
                                continue

                            # Verification Gates
                            if vid_channel != channel_id:
                                continue

                            if marker in vid_desc:
                                if expected_title and vid_title.strip().lower() != expected_title.strip().lower():
                                    logger.warning(
                                        f"Video {vid_id} marker matched but title '{vid_title}' differed from expected '{expected_title}'."
                                    )
                                    continue

                                logger.info(f"Reconciliation SUCCESS (Uploads Playlist): Confirmed Video ID '{vid_id}' for Operation '{operation_id}'.")
                                return vid_id

                        page_token = pl_response.get("nextPageToken")
                        if not page_token:
                            break
                except Exception as pl_err:
                    logger.warning(f"Playlist reconciliation query failed ({pl_err}). Falling back to search API...")

            # 3. Strategy B: Paginated Search for the unique operation marker on user channel
            page_token = None
            pages_checked = 0
            max_pages = 5

            while pages_checked < max_pages:
                pages_checked += 1
                kwargs = {
                    "q": operation_id,
                    "part": "id,snippet",
                    "maxResults": 25,
                    "forMine": True,
                    "type": "video"
                }
                if page_token:
                    kwargs["pageToken"] = page_token

                search_response = youtube.search().list(**kwargs).execute()
                items = search_response.get("items", [])

                for item in items:
                    vid_id = item.get("id", {}).get("videoId")
                    if not vid_id:
                        continue

                    # Query full video details to verify description marker and channel ownership
                    video_details = youtube.videos().list(id=vid_id, part="snippet").execute()
                    v_items = video_details.get("items", [])
                    if not v_items:
                        continue

                    snippet = v_items[0].get("snippet", {})
                    vid_channel = snippet.get("channelId", "")
                    vid_desc = snippet.get("description", "")
                    vid_title = snippet.get("title", "")

                    # Strict Verification Gates:
                    # Gate 1: Channel ownership match
                    if vid_channel != channel_id:
                        logger.warning(f"Video {vid_id} belongs to different channel '{vid_channel}' vs '{channel_id}'. Rejected.")
                        continue

                    # Gate 2: Exact operation marker in description (NEVER confirm by title alone)
                    if marker not in vid_desc:
                        logger.warning(f"Video {vid_id} title matches but lacks unique operation marker '{marker}'. Rejected.")
                        continue

                    # Gate 3: Title match verification if expected_title provided
                    if expected_title:
                        if vid_title.strip().lower() != expected_title.strip().lower():
                            logger.warning(f"Video {vid_id} title '{vid_title}' does not match expected '{expected_title}'. Rejected.")
                            continue

                    logger.info(f"Reconciliation SUCCESS (Search Query): Confirmed Video ID '{vid_id}' for Operation '{operation_id}'.")
                    return vid_id

                page_token = search_response.get("nextPageToken")
                if not page_token:
                    break

            logger.info(f"Reconciliation query completed: No verified video found for Operation '{operation_id}'.")
            return None
        except Exception as e:
            logger.warning(f"Unable to query YouTube API for operation reconciliation ({e}). Outcome remains uncertain.")
            return None

    def check_video_uploaded_by_title(self, title: str):
        """
        DEPRECATED & DISABLED: Title-only reconciliation is permanently disabled
        to eliminate false confirmations and prevent duplicate uploads.
        Always use reconcile_pending_upload(operation_id, expected_title).
        """
        raise NotImplementedError(
            "Title-only video confirmation is disabled for security and duplicate prevention. "
            "Use reconcile_pending_upload(operation_id, expected_title) instead."
        )

    def upload_video(self, video_path: Path, title: str, description: str, tags: list, thumbnail_path: Path = None, privacy_status: str = "public", operation_id: str = None) -> str:
        """
        Uploads a video to YouTube with metadata and a thumbnail image.
        Default privacy_status is 'public' per FACTS AI production requirements.
        Embeds unique operation_id marker in description for unambiguous reconciliation.
        Returns the uploaded video ID.
        """
        valid_privacies = ["public", "private", "unlisted"]
        if privacy_status not in valid_privacies:
            raise ValueError(f"Invalid privacy status '{privacy_status}'. Must be one of {valid_privacies}.")

        # Append operation marker to description for unambiguous reconciliation
        if operation_id and f"[Operation ID: {operation_id}]" not in description:
            description = f"{description}\n\n[Operation ID: {operation_id}]"

        try:
            logger.info("Authenticating YouTube service...")
            youtube = self.get_authenticated_service()
            
            body = {
                "snippet": {
                    "title": title[:100],  # Title limit is 100 characters
                    "description": description[:5000],  # Description limit is 5000 characters
                    "tags": tags,
                    "categoryId": "27"  # '27' represents Education
                },
                "status": {
                    "privacyStatus": privacy_status,
                    "selfDeclaredMadeForKids": False
                }
            }
            
            logger.info(f"Initiating upload for video: {video_path} (privacy: {privacy_status})")
            media = MediaFileUpload(
                str(video_path), 
                mimetype="video/mp4", 
                resumable=True, 
                chunksize=256 * 1024 # 256KB chunks
            )
            
            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media
            )
            
            response = None
            max_retries = 5
            retry = 0
            while response is None:
                try:
                    status, response = request.next_chunk()
                    if status:
                        logger.info(f"Uploaded progress: {int(status.progress() * 100)}%")
                    retry = 0 # reset retry counter on successful progress
                except (HttpError, socket.error, TimeoutError, ConnectionResetError) as err:
                    if isinstance(err, HttpError) and err.resp.status not in [500, 502, 503, 504]:
                        logger.error(f"Non-retryable HTTP error {err.resp.status} during upload: {err}")
                        raise
                    retry += 1
                    if retry > max_retries:
                        logger.error(f"Maximum chunk upload retries ({max_retries}) exceeded: {err}")
                        raise
                    sleep_time = min((2 ** retry) + random.random(), 30)
                    logger.warning(
                        f"Transient error during chunk upload: {err}. "
                        f"Retrying in {sleep_time:.2f}s (attempt {retry}/{max_retries})..."
                    )
                    time.sleep(sleep_time)

            video_id = response.get("id") if response else None
            if not video_id:
                logger.error("Upload response received without valid video ID.")
                return ""

            logger.info(f"Video uploaded successfully! Video ID: {video_id}")
            
            # Upload thumbnail if provided
            if thumbnail_path and thumbnail_path.exists() and video_id:
                self.upload_thumbnail(youtube, video_id, thumbnail_path)
                
            return video_id
            
        except Exception as e:
            logger.error(f"Failed to upload video to YouTube: {e}")
            return ""

    def upload_thumbnail(self, youtube_service, video_id: str, thumbnail_path: Path):
        """Uploads a thumbnail image and associates it with the video ID."""
        try:
            logger.info(f"Uploading thumbnail: {thumbnail_path} for video {video_id}")
            media = MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg")
            youtube_service.thumbnails().set(
                videoId=video_id,
                media_body=media
            ).execute()
            logger.info("Thumbnail uploaded successfully.")
        except Exception as e:
            logger.error(f"Failed to set custom thumbnail: {e}")

if __name__ == "__main__":
    # Test client logic
    pass
