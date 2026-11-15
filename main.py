import logging
import os
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

import config
from trend_finder import TrendFinder
from script_writer import ScriptWriter, LanguageValidationError
from voice_generator import VoiceGenerator
from fact_checker import FactChecker, FactCheckError, ClaimRejectedError, UnverifiedClaimError
from media_downloader import MediaDownloader
from subtitle_generator import SubtitleGenerator
from thumbnail_creator import ThumbnailCreator
from video_builder import VideoBuilder, FontMissingError
from youtube_uploader import YoutubeUploader

# Set up logging
log_filename = config.LOGS_DIR / f"automation_{datetime.now().strftime('%Y%m%d')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_filename, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("YouTubeAutomation")

class AutomationPipeline:
    def __init__(self, voice: str = None):
        self.trend_finder = TrendFinder()
        self.fact_checker = FactChecker()
        self.script_writer = ScriptWriter()
        self.voice_generator = VoiceGenerator(voice=voice)
        self.media_downloader = MediaDownloader()
        self.subtitle_generator = SubtitleGenerator()
        self.thumbnail_creator = ThumbnailCreator()
        self.video_builder = VideoBuilder()
        self.uploader = YoutubeUploader()

    def normalize_topic(self, topic: str) -> str:
        """Helper to normalize a topic string for strict history and duplicate matching."""
        if not topic:
            return ""
        clean = topic.replace("[PENDING]", "").strip()
        # If line contains metadata fields, extract topic value
        if "topic=" in clean:
            for part in clean.split("|"):
                part_clean = part.strip()
                if part_clean.startswith("topic="):
                    clean = part_clean[len("topic="):].strip()
                    break
        else:
            clean = clean.split("|")[0].strip()
        return "".join(c for c in clean.lower() if c.isalnum())

    def load_used_topics(self) -> set:
        """Loads a set of all processed topics (both completed and pending)."""
        used_path = config.BASE_DIR / "used_topics.txt"
        topics = set()
        if used_path.exists():
            try:
                with open(used_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line_str = line.strip()
                        if line_str:
                            clean_topic = line_str.split("|")[0].replace("[PENDING]", "").strip()
                            if "topic=" in line_str:
                                for part in line_str.split("|"):
                                    part_clean = part.strip()
                                    if part_clean.startswith("topic="):
                                        clean_topic = part_clean[len("topic="):].strip()
                                        break
                            if clean_topic:
                                topics.add(clean_topic)
            except Exception as e:
                logger.warning(f"Failed to load used topics: {e}")
        return topics

    def get_pending_operations(self) -> list:
        """Returns a list of structured pending or review_required operations from used_topics.txt."""
        used_path = config.BASE_DIR / "used_topics.txt"
        pending = []
        if used_path.exists():
            try:
                with open(used_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line_str = line.strip()
                        status = None
                        remainder = ""
                        if line_str.startswith("[PENDING]"):
                            status = "PENDING"
                            remainder = line_str[len("[PENDING]"):].strip()
                        elif line_str.startswith("[REVIEW_REQUIRED]"):
                            status = "REVIEW_REQUIRED"
                            remainder = line_str[len("[REVIEW_REQUIRED]"):].strip()

                        if status:
                            parts = [p.strip() for p in remainder.split("|")]
                            op_id = None
                            topic = None
                            title = None
                            for p in parts:
                                if p.startswith("op_id="):
                                    op_id = p[len("op_id="):].strip()
                                elif p.startswith("topic="):
                                    topic = p[len("topic="):].strip()
                                elif p.startswith("title="):
                                    title = p[len("title="):].strip()
                            if not topic and parts:
                                topic = parts[0]
                            pending.append({
                                "status": status,
                                "op_id": op_id or "",
                                "topic": topic or "",
                                "title": title or topic or "",
                                "raw_line": line_str
                            })
            except Exception as e:
                logger.warning(f"Failed to check pending operations: {e}")
        return pending

    def get_pending_topics(self) -> list:
        """Returns a list of topics currently in PENDING unconfirmed upload status."""
        return [op["topic"] for op in self.get_pending_operations() if op.get("topic")]

    def mark_topic_pending(self, topic: str, op_id: str = None, seo_title: str = None):
        """Persists a topic in PENDING status before initiating upload with unique operation ID and SEO title."""
        used_path = config.BASE_DIR / "used_topics.txt"
        timestamp = datetime.now().isoformat()
        import uuid
        op_id = op_id or f"OP-{uuid.uuid4().hex[:8]}"
        title_part = f" | title={seo_title}" if seo_title else ""
        line = f"[PENDING] op_id={op_id} | topic={topic}{title_part} | {timestamp}\n"
        try:
            with open(used_path, "a", encoding="utf-8") as f:
                f.write(line)
            logger.info(f"Recorded PENDING status for topic: '{topic}' (Op ID: {op_id})")
        except Exception as e:
            logger.error(f"Failed to mark topic as pending: {e}")

    def mark_topic_review_required(self, topic: str, op_id: str = None, reason: str = ""):
        """Transitions an unverified PENDING upload to REVIEW_REQUIRED status."""
        used_path = config.BASE_DIR / "used_topics.txt"
        timestamp = datetime.now().isoformat()
        new_line = f"[REVIEW_REQUIRED] op_id={op_id or 'UNKNOWN'} | topic={topic} | reason={reason} | {timestamp}\n"
        if not used_path.exists():
            with open(used_path, "w", encoding="utf-8") as f:
                f.write(new_line)
            return

        try:
            with open(used_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            new_lines = []
            replaced = False
            for line in lines:
                line_clean = line.strip()
                if op_id and f"op_id={op_id}" in line_clean and (line_clean.startswith("[PENDING]") or line_clean.startswith("[REVIEW_REQUIRED]")):
                    new_lines.append(new_line)
                    replaced = True
                else:
                    new_lines.append(line)
            if not replaced:
                new_lines.append(new_line)
            with open(used_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            logger.info(f"Recorded REVIEW_REQUIRED status for op_id '{op_id}' (Topic: '{topic}')")
        except Exception as e:
            logger.error(f"Failed to record REVIEW_REQUIRED status: {e}")

    def mark_topic_failed(self, op_id: str, reason: str = ""):
        """Marks an unresolved operation as FAILED (e.g. after verifying video was never created on YouTube)."""
        used_path = config.BASE_DIR / "used_topics.txt"
        timestamp = datetime.now().isoformat()
        new_line = f"[FAILED] op_id={op_id} | reason={reason} | {timestamp}\n"
        if not used_path.exists():
            return

        try:
            with open(used_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            new_lines = []
            for line in lines:
                line_clean = line.strip()
                if f"op_id={op_id}" in line_clean and (line_clean.startswith("[PENDING]") or line_clean.startswith("[REVIEW_REQUIRED]")):
                    new_lines.append(new_line)
                else:
                    new_lines.append(line)
            with open(used_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            logger.info(f"Recorded FAILED status for op_id '{op_id}'")
        except Exception as e:
            logger.error(f"Failed to record FAILED status: {e}")

    def mark_topic_completed(self, topic: str, video_id: str, op_id: str = None):
        """Reconciles a pending topic into COMPLETED status with video URL and operation ID."""
        used_path = config.BASE_DIR / "used_topics.txt"
        norm_topic = self.normalize_topic(topic)
        op_part = f" | op_id={op_id}" if op_id else ""
        completed_line = f"{topic} | https://youtu.be/{video_id}{op_part}\n"
        if not used_path.exists():
            with open(used_path, "w", encoding="utf-8") as f:
                f.write(completed_line)
            return

        try:
            with open(used_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            new_lines = []
            replaced = False
            for line in lines:
                line_clean = line.strip()
                if line_clean.startswith("[PENDING]") or line_clean.startswith("[REVIEW_REQUIRED]"):
                    match_op = op_id and f"op_id={op_id}" in line_clean
                    match_topic = self.normalize_topic(line_clean) == norm_topic
                    if match_op or match_topic:
                        # Defensive: If caller provided a generic or empty topic, extract original topic from pending record
                        actual_topic = topic
                        if match_op and (not actual_topic or actual_topic == "ManualTopic"):
                            for part in line_clean.split("|"):
                                part_clean = part.strip()
                                if part_clean.startswith("topic="):
                                    actual_topic = part_clean[len("topic="):].strip()
                                    break
                        rec_line = f"{actual_topic} | https://youtu.be/{video_id}{op_part}\n"
                        new_lines.append(rec_line)
                        replaced = True
                        continue
                new_lines.append(line)

            if not replaced:
                new_lines.append(completed_line)

            with open(used_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            logger.info(f"Updated topic '{topic}' to COMPLETED status (Video ID: {video_id}).")
        except Exception as e:
            logger.error(f"Failed to update topic status to completed: {e}")

    @staticmethod
    def reconcile_topic_history(remote_lines: list, local_lines: list) -> list:
        """
        Reconciles remote and local topic records safely:
        1. Strips any git conflict markers (<<<<<<<, =======, >>>>>>>, [conflict]).
        2. Merges entries by operation ID (op_id) and topic name.
        3. Preserves completed records with video URLs from both sides.
        4. Gives COMPLETED (https://youtu.be/) precedence over PENDING and REVIEW_REQUIRED.
        5. Gives FAILED precedence over PENDING and REVIEW_REQUIRED.
        6. Preserves all unique historical topic entries without duplicates.
        """
        conflict_marker_prefixes = ("<<<<<<<", "=======", ">>>>>>>", "[conflict]")

        def is_valid_line(l: str) -> bool:
            clean = l.strip()
            if not clean:
                return False
            return not any(clean.startswith(p) for p in conflict_marker_prefixes)

        valid_remote = [l.strip() for l in remote_lines if is_valid_line(l)]
        valid_local = [l.strip() for l in local_lines if is_valid_line(l)]

        def parse_entry(line: str) -> dict:
            op_id = None
            topic = None
            status = "COMPLETED" if "https://youtu.be/" in line else "UNKNOWN"
            clean_line = line
            if clean_line.startswith("[PENDING]"):
                status = "PENDING"
                clean_line = clean_line[len("[PENDING]"):].strip()
            elif clean_line.startswith("[REVIEW_REQUIRED]"):
                status = "REVIEW_REQUIRED"
                clean_line = clean_line[len("[REVIEW_REQUIRED]"):].strip()
            elif clean_line.startswith("[FAILED]"):
                status = "FAILED"
                clean_line = clean_line[len("[FAILED]"):].strip()

            parts = [p.strip() for p in clean_line.split("|")]
            for p in parts:
                if p.startswith("op_id="):
                    op_id = p[len("op_id="):].strip()
                elif p.startswith("topic="):
                    topic = p[len("topic="):].strip()
            if not topic and parts:
                clean_first = parts[0].strip()
                if clean_first and not clean_first.startswith("op_id="):
                    topic = clean_first

            return {
                "raw": line,
                "status": status,
                "op_id": op_id,
                "topic": topic
            }

        status_rank = {
            "PENDING": 1,
            "REVIEW_REQUIRED": 2,
            "FAILED": 3,
            "COMPLETED": 4,
            "UNKNOWN": 0
        }

        op_map = {}
        standalone_lines = []

        all_entries = [parse_entry(l) for l in valid_remote] + [parse_entry(l) for l in valid_local]

        for ent in all_entries:
            oid = ent["op_id"]
            if oid:
                if oid not in op_map:
                    op_map[oid] = ent
                else:
                    curr = op_map[oid]
                    if status_rank.get(ent["status"], 0) > status_rank.get(curr["status"], 0):
                        op_map[oid] = ent
                    elif status_rank.get(ent["status"], 0) == status_rank.get(curr["status"], 0):
                        if "https://youtu.be/" in ent["raw"] and "https://youtu.be/" not in curr["raw"]:
                            op_map[oid] = ent
            else:
                if ent["raw"] not in standalone_lines:
                    standalone_lines.append(ent["raw"])

        reconciled = []
        for oid, ent in op_map.items():
            reconciled.append(ent["raw"])

        for sl in standalone_lines:
            if sl not in reconciled:
                reconciled.append(sl)

        return reconciled

    def save_used_topic(self, topic: str):
        """Legacy helper for recording completed topic."""
        self.mark_topic_completed(topic, "legacy")

    def run_pipeline(self, target_topic: str = None, privacy_status: str = "private", format_type: str = "short", category: str = None, custom_instructions: str = None) -> bool:
        """
        Runs the full video automation pipeline:
        Trend Discovery -> Script -> Voiceover -> Video Download -> Subtitles -> Thumbnail -> FFmpeg Render -> Upload.
        Supports format_type='short' (1080x1920) or 'long' (1920x1080).
        Supports category specification and custom AI instructions for Android integration.
        """
        # Configure aspect ratios dynamically
        if format_type == "long":
            self.video_builder.width = 1920
            self.video_builder.height = 1080
            self.media_downloader.width = 1920
            self.media_downloader.height = 1080
            self.thumbnail_creator.width = 1280
            self.thumbnail_creator.height = 720
        else:
            self.video_builder.width = 1080
            self.video_builder.height = 1920
            self.media_downloader.width = 1080
            self.media_downloader.height = 1920
            self.thumbnail_creator.width = 1080
            self.thumbnail_creator.height = 1920

        # Create a unique temporary directory for this run
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_dir = config.TEMP_DIR / f"run_{run_id}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"--- Starting Automation Pipeline ({format_type.upper()} Format, Run ID: {run_id}) ---")
        logger.info(f"Temporary workspace: {temp_dir}")
        
        try:
            # Ambiguous Upload Protection: Check for any unconfirmed PENDING uploads from prior runs
            pending_ops = self.get_pending_operations()
            if pending_ops:
                for pending_op in pending_ops:
                    op_id = pending_op.get("op_id")
                    seo_title = pending_op.get("title")
                    topic_name = pending_op.get("topic")
                    op_status = pending_op.get("status", "PENDING")
                    logger.warning(
                        f"Ambiguous upload detected: Operation '{op_id}' in {op_status} (Topic: '{topic_name}', Title: '{seo_title}'). "
                        f"Attempting reconciliation with channel evidence..."
                    )
                    confirmed_id = None
                    if op_id:
                        confirmed_id = self.uploader.reconcile_pending_upload(
                            operation_id=op_id,
                            expected_title=seo_title
                        )

                    if confirmed_id:
                        logger.info(f"Reconciliation SUCCESS: Confirmed Video ID '{confirmed_id}' on YouTube for '{topic_name}'. Marking COMPLETED.")
                        self.mark_topic_completed(topic_name, confirmed_id, op_id=op_id)
                    else:
                        if op_status == "PENDING" and op_id:
                            self.mark_topic_review_required(
                                topic_name,
                                op_id=op_id,
                                reason="Video could not be verified on YouTube channel during automated reconciliation."
                            )
                        err_msg = (
                            f"AMBIGUOUS UPLOAD BLOCKED: Operation '{op_id}' (Topic: '{topic_name}') is in PENDING/REVIEW_REQUIRED status and completion cannot be verified. "
                            f"Preserving PENDING status. Aborting pipeline to prevent duplicate video creation."
                        )
                        logger.critical(err_msg)
                        raise RuntimeError(err_msg)

            # Step 1: Trend Discovery & True Topic Deduplication
            used_topics_set = {self.normalize_topic(t) for t in self.load_used_topics()}
            discovery_source = "UNKNOWN"

            if target_topic:
                discovery_source = "USER_DEFINED"
                norm_target = self.normalize_topic(target_topic)
                if norm_target in used_topics_set:
                    error_msg = f"Duplicate Topic Rejected: User-provided topic '{target_topic}' has already been used or is pending."
                    logger.critical(error_msg)
                    raise ValueError(error_msg)
                logger.info(f"Using verified user-defined topic: '{target_topic}' (Provenance: USER_DEFINED)")
            else:
                # Automated mode: First attempt live science trend discovery via TrendFinder
                selected_topic = None
                try:
                    logger.info("Discovering live trending science topics from real sources via TrendFinder...")
                    live_trends = self.trend_finder.get_trending_science_topics(max_results=10)
                    for trend in live_trends:
                        cand_title = trend.get("title", "").strip()
                        if cand_title and len(cand_title.split()) <= 15:
                            if self.normalize_topic(cand_title) not in used_topics_set:
                                # Validate topic relevance and factual suitability
                                prelim_check = self.fact_checker.verify_claim(cand_title, fetch_live_sources=False)
                                if prelim_check.get("verified") and prelim_check.get("status") == "VERIFIED":
                                    selected_topic = cand_title
                                    discovery_source = "LIVE_TREND"
                                    logger.info(
                                        f"Selected verified LIVE_TREND from {trend.get('source', 'Web')}: '{selected_topic}' "
                                        f"(Provenance: LIVE_TREND, Traffic: {trend.get('traffic', 'Active')}, Score: {trend.get('score', 0)})"
                                    )
                                    break
                                else:
                                    logger.info(f"Discovered trend '{cand_title}' was unverified or unsuitable. Skipping...")
                            else:
                                logger.info(f"Trending topic '{cand_title}' was already used. Skipping...")
                except Exception as trend_err:
                    logger.warning(f"Trend discovery failed or yielded no unused science topics: {trend_err}. Falling back to niche exploration.")

                # If no live science trend was selected, brainstorm and select from unused niches
                import random
                import requests

                max_attempts = 5
                attempt = 0
                unused_niches = [n for n in config.NICHES if self.normalize_topic(n) not in used_topics_set]

                while not selected_topic and attempt < max_attempts:
                    attempt += 1
                    active_niche = category if category else (random.choice(unused_niches) if unused_niches else random.choice(config.NICHES))
                    logger.info(f"Deduplication Selection Attempt {attempt}/{max_attempts}: Exploring niche '{active_niche}'")

                    brainstormed_topic = None
                    try:
                        brainstorm_prompt = f"""
Brainstorm a single, highly engaging, trending video topic under the niche '{active_niche}' specifically for an Indian audience.
Respond with ONLY the topic name (under 10 words, no quotes, no introduction, e.g. 'How UPI auto-debits secretly drain your bank account').
"""
                        headers = {
                            "Authorization": f"Bearer {self.script_writer.api_key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://github.com/google/antigravity",
                            "X-Title": "Antigravity YouTube Automation"
                        }
                        data = {
                            "model": self.script_writer.model,
                            "messages": [{"role": "user", "content": brainstorm_prompt}],
                            "max_tokens": 50
                        }
                        response = requests.post(f"{self.script_writer.base_url}/chat/completions", headers=headers, json=data, timeout=15)
                        if response.status_code == 200:
                            result = response.json()
                            candidate = result['choices'][0]['message']['content'].strip().strip('"\'')
                            if candidate and len(candidate.split()) < 15:
                                brainstormed_topic = candidate
                    except Exception as e:
                        logger.warning(f"Brainstorming attempt {attempt} failed: {e}")

                    candidate_topic = brainstormed_topic or active_niche
                    if self.normalize_topic(candidate_topic) not in used_topics_set:
                        selected_topic = candidate_topic
                        discovery_source = "LLM_BRAINSTORMED"
                        logger.info(f"Selected genuinely unique topic: '{selected_topic}' (Provenance: LLM_BRAINSTORMED - Niche exploration, not live trend)")
                        break
                    else:
                        logger.warning(f"Topic candidate '{candidate_topic}' was already used. Rejecting duplicate and retrying...")

                if not selected_topic:
                    # Fallback to any niche template that has never been processed
                    for n in config.NICHES:
                        if self.normalize_topic(n) not in used_topics_set:
                            selected_topic = n
                            discovery_source = "LLM_BRAINSTORMED"
                            logger.info(f"Selected unused fallback niche template: '{selected_topic}' (Provenance: LLM_BRAINSTORMED)")
                            break

                if not selected_topic:
                    error_msg = "True Deduplication Gate: All candidate topics and niches have been exhausted. Aborting safely to prevent duplicate video."
                    logger.critical(error_msg)
                    raise RuntimeError(error_msg)

                target_topic = selected_topic

            # Step 1.5: Scientific Fact-Checking Gate
            logger.info(f"Initiating scientific fact-checking for topic: '{target_topic}'...")
            verification_record = self.fact_checker.enforce_verification(target_topic)
            logger.info(
                f"Scientific Fact Verification PASSED: Status={verification_record['status']}, "
                f"Confidence={verification_record.get('confidence', 1.0):.2f}, "
                f"Sources={verification_record.get('source_urls', [])}"
            )
            self.fact_checker.save_verification_log(verification_record, temp_dir / "fact_check_verification.json")

            # Step 2: Script Writing & Language Validation
            logger.info("Writing Hindi Devanagari script and SEO metadata...")
            script = self.script_writer.generate_script(
                target_topic,
                format_type=format_type,
                language="hi",
                verified_facts=verification_record,
                custom_instructions=custom_instructions
            )
            # Validate script language before TTS
            self.script_writer.validate_script_language(script, target_language="hi", format_type=format_type)
            # Verify every individual segment claim against retrieved source evidence
            self.fact_checker.enforce_script_verification(script, verification_record)
            logger.info(f"Generated Script Title: {script['title']}")
            
            # Step 3: Voice Generation
            logger.info(f"Generating Hindi voice narration ({self.voice_generator.voice}) for segments...")
            segments_with_audio = self.voice_generator.generate_segment_audios(
                script["segments"],
                temp_dir,
                validate_language=True
            )
            if not segments_with_audio:
                raise ValueError("Voice generation failed.")

            # Step 4: Video Media Download
            logger.info("Downloading stock video footage...")
            segments_with_media = self.media_downloader.download_media_for_segments(segments_with_audio, temp_dir)
            if not segments_with_media:
                raise ValueError("Media downloading/generation failed.")

            # Step 5: Subtitle Captioning
            logger.info("Generating subtitles...")
            srt_path = temp_dir / "subtitles.srt"
            sub_success = self.subtitle_generator.generate_srt(segments_with_media, srt_path)
            if not sub_success:
                raise ValueError("Subtitle generation failed.")

            # Step 6: Thumbnail Generation
            logger.info("Creating thumbnail...")
            thumbnail_path = temp_dir / "thumbnail.jpg"
            # Try to use first video clip as thumbnail background frame if possible, or fall back to gradient
            first_clip = Path(segments_with_media[0]["video_path"]) if segments_with_media else None
            # Extract single frame as thumbnail image using FFmpeg
            first_frame_path = temp_dir / "first_frame.jpg"
            if first_clip and first_clip.exists():
                cmd = [
                    "ffmpeg", "-y",
                    "-ss", "0.5",  # Seek 0.5s to avoid black frame
                    "-i", str(first_clip),
                    "-vframes", "1",
                    str(first_frame_path)
                ]
                creation_flags = os.name == 'nt'
                # Run frame extraction silently
                subprocess.run(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE, 
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
            
            bg_image = first_frame_path if first_frame_path.exists() else None
            thumb_success = self.thumbnail_creator.generate_thumbnail(script["title"], bg_image, thumbnail_path)
            if not thumb_success:
                logger.warning("Thumbnail generation failed. Will upload without custom thumbnail.")

            # Step 7: Video Assembly & Subtitle Burn
            output_filename = f"video_{run_id}.mp4"
            output_video_path = config.OUTPUT_DIR / output_filename
            logger.info(f"Rendering final video to: {output_video_path}")
            
            build_success = self.video_builder.build_video(
                segments=segments_with_media,
                srt_path=str(srt_path),
                output_video_path=output_video_path,
                temp_dir=temp_dir
            )
            
            if not build_success or not output_video_path.exists():
                raise ValueError("FFmpeg video rendering failed.")
                
            logger.info(f"Video created successfully! File saved at: {output_video_path}")

            # Step 8: Upload to YouTube
            logger.info("Uploading video to YouTube...")
            seo = script["seo"]
            tags_str = ", ".join(seo["tags"])
            description = f"{seo['description']}\n\nTags: {tags_str}\nHashtags: {' '.join(seo['hashtags'])}"
            
            # Ambiguous Upload Protection: Generate unique operation ID and persist before initiating upload call
            import uuid
            upload_op_id = f"FACTS-AI-OP-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
            self.mark_topic_pending(target_topic, op_id=upload_op_id, seo_title=seo["title"])

            try:
                video_id = self.uploader.upload_video(
                    video_path=output_video_path,
                    title=seo["title"],
                    description=description,
                    tags=seo["tags"],
                    thumbnail_path=thumbnail_path if thumbnail_path.exists() else None,
                    privacy_status=privacy_status,
                    operation_id=upload_op_id
                )
                if video_id:
                    logger.info(f"Successfully automated video upload! Video URL: https://youtu.be/{video_id}")
                    self.mark_topic_completed(target_topic, video_id, op_id=upload_op_id)
                    return True
                else:
                    logger.error(f"YouTube Upload outcome uncertain (no video ID returned). Preserving PENDING/REVIEW_REQUIRED status for '{target_topic}'.")
                    self.mark_topic_review_required(target_topic, op_id=upload_op_id, reason="No video ID returned from upload call.")
                    return False
            except Exception as upload_err:
                logger.error(
                    f"\n------------------------------------------------------\n"
                    f"YOUTUBE UPLOAD SKIPPED OR FAILED: {upload_err}\n"
                    f"The video was generated successfully and saved locally!\n"
                    f"You can find it here: {output_video_path}\n"
                    f"Topic '{target_topic}' transitioned to REVIEW_REQUIRED until verified.\n"
                    f"------------------------------------------------------"
                )
                self.mark_topic_review_required(target_topic, op_id=upload_op_id, reason=f"Upload error: {upload_err}")
                return False

        except (RuntimeError, ValueError, FactCheckError, LanguageValidationError, FontMissingError) as critical_err:
            logger.critical(f"Pipeline execution halted: {critical_err}")
            raise
        except Exception as e:
            logger.critical(f"Pipeline crashed during execution: {e}", exc_info=True)
            return False
            
        finally:
            # Clean up temp folder to conserve storage
            if temp_dir.exists():
                logger.info(f"Cleaning up temporary folder: {temp_dir}")
                try:
                    shutil.rmtree(temp_dir)
                except Exception as cleanup_err:
                    logger.warning(f"Failed to delete temp directory: {cleanup_err}")
            logger.info("--- Pipeline Execution Finished ---")

    # Alias for run_pipeline
    run = run_pipeline

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="YouTube Daily Shorts & Long-form Automation System")
    parser.add_argument("--topic", type=str, default=None, help="Custom topic to write video script on")
    parser.add_argument("--privacy", type=str, default=os.getenv("PRIVACY_STATUS", "public"), choices=["private", "unlisted", "public"], help="YouTube video privacy status")
    parser.add_argument("--format", type=str, default="short", choices=["short", "long"], help="Video format: short (1080x1920) or long (1920x1080)")
    parser.add_argument("--voice", type=str, default=os.getenv("EDGE_VOICE", "hi-IN-MadhurNeural"), choices=["hi-IN-MadhurNeural", "hi-IN-SwaraNeural"], help="Edge TTS voice (default: hi-IN-MadhurNeural, alternate: hi-IN-SwaraNeural)")
    parser.add_argument("--reconcile-pending", action="store_true", help="Attempt manual reconciliation of all pending/review_required operations")
    parser.add_argument("--mark-failed", type=str, default=None, metavar="OP_ID", help="Manually mark an operation ID as FAILED (releasing lock)")
    parser.add_argument("--mark-confirmed", nargs=2, default=None, metavar=("OP_ID", "VIDEO_ID"), help="Manually mark an operation ID as CONFIRMED with VIDEO_ID")
    parser.add_argument("--reconcile-history", type=str, default=None, metavar="LOCAL_FILE", help="Reconcile local history file with repository used_topics.txt")
    parser.add_argument("--category", type=str, default=None, help="Video category / niche (for Android / custom categories)")
    parser.add_argument("--instructions", type=str, default=os.getenv("AI_INSTRUCTIONS", None), help="Custom AI instructions (global or category-specific)")

    args = parser.parse_args()

    try:
        pipeline = AutomationPipeline(voice=args.voice)

        # Manual Recovery CLI Operations
        if args.reconcile_pending:
            logger.info("Starting manual reconciliation of pending operations...")
            ops = pipeline.get_pending_operations()
            if not ops:
                logger.info("No pending or review_required operations found.")
            for op in ops:
                op_id = op["op_id"]
                title = op["title"]
                topic = op["topic"]
                vid = pipeline.uploader.reconcile_pending_upload(operation_id=op_id, expected_title=title)
                if vid:
                    pipeline.mark_topic_completed(topic, vid, op_id=op_id)
                    logger.info(f"Reconciled and CONFIRMED: Op ID '{op_id}' -> Video ID '{vid}'")
                else:
                    pipeline.mark_topic_review_required(topic, op_id=op_id, reason="Manual reconciliation could not find video on YouTube.")
                    logger.warning(f"Op ID '{op_id}' remains unconfirmed. Set to REVIEW_REQUIRED.")
            import sys
            sys.exit(0)

        if args.mark_failed:
            op_id = args.mark_failed
            matching_ops = [op for op in pipeline.get_pending_operations() if op.get("op_id") == op_id]
            if not matching_ops:
                logger.error(
                    f"REJECTED: Operation ID '{op_id}' was not found in pending or review_required operations. "
                    f"Cannot mark unknown operation as failed."
                )
                import sys
                sys.exit(1)
            if len(matching_ops) > 1:
                logger.error(
                    f"REJECTED: Ambiguous Operation ID '{op_id}'. Found {len(matching_ops)} matching operations."
                )
                import sys
                sys.exit(1)
            pipeline.mark_topic_failed(op_id, reason="Manually marked FAILED by operator after verifying video does not exist.")
            logger.info(f"Operation '{op_id}' marked FAILED.")
            import sys
            sys.exit(0)

        if args.mark_confirmed:
            op_id, video_id = args.mark_confirmed
            matching_ops = [op for op in pipeline.get_pending_operations() if op.get("op_id") == op_id]
            if not matching_ops:
                logger.error(
                    f"REJECTED: Operation ID '{op_id}' was not found in pending or review_required operations. "
                    f"Cannot mark unknown operation as confirmed."
                )
                import sys
                sys.exit(1)
            if len(matching_ops) > 1:
                logger.error(
                    f"REJECTED: Ambiguous Operation ID '{op_id}'. Found {len(matching_ops)} matching operations."
                )
                import sys
                sys.exit(1)

            matched_op = matching_ops[0]
            original_topic = matched_op.get("topic")
            if not original_topic:
                logger.error(
                    f"REJECTED: Operation '{op_id}' has no associated topic in record."
                )
                import sys
                sys.exit(1)

            pipeline.mark_topic_completed(original_topic, video_id, op_id=op_id)
            logger.info(f"Operation '{op_id}' (Topic: '{original_topic}') marked CONFIRMED with Video ID '{video_id}'.")
            import sys
            sys.exit(0)

        if args.reconcile_history:
            local_path = Path(args.reconcile_history)
            used_path = config.BASE_DIR / "used_topics.txt"
            if not local_path.exists():
                logger.error(f"Local history file not found: {local_path}")
                import sys
                sys.exit(1)
            remote_lines = []
            if used_path.exists():
                with open(used_path, "r", encoding="utf-8") as f:
                    remote_lines = f.readlines()
            with open(local_path, "r", encoding="utf-8") as f:
                local_lines = f.readlines()
            reconciled = AutomationPipeline.reconcile_topic_history(remote_lines, local_lines)
            with open(used_path, "w", encoding="utf-8") as f:
                for line in reconciled:
                    f.write(line.strip() + "\n")
            logger.info(f"Successfully reconciled {len(reconciled)} topic history records.")
            import sys
            sys.exit(0)

        success = pipeline.run_pipeline(
            target_topic=args.topic,
            privacy_status=args.privacy,
            format_type=args.format,
            category=args.category,
            custom_instructions=args.instructions
        )
        if not success:
            import sys
            sys.exit(1)
    except Exception as e:
        logger.critical(f"FATAL: Pipeline execution aborted: {e}")
        import sys
        sys.exit(1)
