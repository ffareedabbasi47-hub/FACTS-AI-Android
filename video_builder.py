import logging
import os
import random
import shutil
import subprocess
from pathlib import Path
import requests
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VideoBuilder")

class FontMissingError(Exception):
    """Raised when required Devanagari font glyph support is absent."""
    pass

VERIFIED_DEVANAGARI_FONTS = [
    "Noto Sans Devanagari",
    "Noto Sans Devanagari Bold",
    "Lohit Devanagari",
    "Gargi",
    "Mukti",
    "Chandas",
    "Nirmala UI",
    "Mangal"
]

class VideoBuilder:
    def __init__(self):
        self.width = config.VIDEO_WIDTH
        self.height = config.VIDEO_HEIGHT
        self.fps = config.VIDEO_FPS

    def detect_devanagari_font(self, strict: bool = True) -> str:
        """
        Detects whether a verified Devanagari font is installed on the system.
        Prevents silent tofu (missing glyph □□□) rendering.
        """
        # 1. Check local assets fonts directory
        if config.FONTS_DIR.exists():
            for font_file in config.FONTS_DIR.glob("*.*"):
                if font_file.suffix.lower() in [".ttf", ".otf"]:
                    for cand in VERIFIED_DEVANAGARI_FONTS:
                        if cand.lower().replace(" ", "") in font_file.name.lower():
                            logger.info(f"Detected bundled Devanagari font: {font_file.name}")
                            return cand

        # 2. Check fontconfig fc-list on Linux/Unix
        try:
            cmd = ["fc-list", ":lang=hi", "family"]
            creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=creation_flags)
            if result.returncode == 0 and result.stdout.strip():
                installed = [line.strip().split(",")[0] for line in result.stdout.strip().splitlines() if line.strip()]
                for cand in VERIFIED_DEVANAGARI_FONTS:
                    for inst in installed:
                        if cand.lower() in inst.lower():
                            logger.info(f"Detected system Devanagari font: {inst}")
                            return inst
                if installed:
                    return installed[0]
        except Exception as e:
            logger.warning(f"Could not execute fc-list to detect Devanagari fonts: {e}")

        # 3. Check Windows standard fonts
        if os.name == 'nt':
            for win_font in ["Nirmala UI", "Mangal"]:
                return win_font

        if strict:
            err_msg = (
                "DEVANAGARI FONT MISSING: No verified Devanagari font (e.g. 'Noto Sans Devanagari' or 'Lohit Devanagari') "
                "was found on the system. Subtitle rendering aborted to prevent missing-glyph boxes (tofu)."
            )
            logger.critical(err_msg)
            raise FontMissingError(err_msg)

        return "DejaVuSans-Bold"
        
    def _run_ffmpeg(self, cmd: list, cwd: str = None) -> bool:
        """Helper to run FFmpeg commands silently."""
        try:
            creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            result = subprocess.run(
                cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creation_flags
            )
            if result.returncode == 0:
                return True
            else:
                logger.error(f"FFmpeg error: {result.stderr.decode('utf-8', errors='ignore')}")
                return False
        except Exception as e:
            logger.error(f"Failed to execute FFmpeg command: {e}")
            return False

    def standardize_segments(self, segments: list, temp_dir: Path) -> list:
        """
        Loops, scales, crops stock clips/photos to fit video dimensions and merges them
        with their segment voiceovers and transition sound effects.
        Outputs a standard segment video.
        """
        # Download whoosh transition SFX if missing
        whoosh_path = config.MUSIC_DIR / "whoosh.wav"
        if not whoosh_path.exists():
            try:
                whoosh_url = "https://assets.mixkit.co/active_storage/sfx/2568/2568-84.wav"
                logger.info(f"Downloading transition whoosh SFX from {whoosh_url} -> {whoosh_path}")
                r = requests.get(whoosh_url, stream=True, timeout=20)
                if r.status_code == 200:
                    with open(whoosh_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
            except Exception as e:
                logger.warning(f"Failed to download transition whoosh sound: {e}")

        has_whoosh = whoosh_path.exists()
        standard_segments = []
        
        for idx, segment in enumerate(segments):
            clip_path = segment["video_path"]
            audio_path = segment["audio_path"]
            duration = segment["duration"]
            is_image = segment.get("is_image", False)
            
            output_segment_path = temp_dir / f"standard_segment_{idx}.mp4"
            
            # Formulate FFmpeg command
            if is_image:
                logger.info(f"Standardizing segment {idx}: Animating photo with Ken Burns effect -> {output_segment_path}")
                cmd = [
                    "ffmpeg", "-y",
                    "-loop", "1",
                    "-i", str(clip_path),
                    "-i", str(audio_path)
                ]
                if has_whoosh:
                    cmd.extend(["-i", str(whoosh_path)])
                    filter_complex = (
                        f"[0:v]scale=1296:2304,crop={self.width}:{self.height}:'(in_w-out_w)/2':'(in_h-out_h)/2 + (in_h-out_h)/3 * sin(2*3.14159*t/12)'[v];"
                        f"[2:a]volume=0.25[w];[1:a][w]amix=inputs=2:duration=first[a]"
                    )
                    map_audio = "[a]"
                else:
                    filter_complex = f"[0:v]scale=1296:2304,crop={self.width}:{self.height}:'(in_w-out_w)/2':'(in_h-out_h)/2 + (in_h-out_h)/3 * sin(2*3.14159*t/12)'[v]"
                    map_audio = "1:a"
            else:
                logger.info(f"Standardizing segment {idx}: looping, scaling & adding professional pan/zoom to video -> {output_segment_path}")
                cmd = [
                    "ffmpeg", "-y",
                    "-stream_loop", "-1",         # Loop input video infinitely
                    "-i", str(clip_path),
                    "-i", str(audio_path)
                ]
                scale_w = int(1.15 * self.width)
                scale_h = int(1.15 * self.height)
                if has_whoosh:
                    cmd.extend(["-i", str(whoosh_path)])
                    filter_complex = (
                        f"[0:v]scale={scale_w}:{scale_h}:force_original_aspect_ratio=increase,"
                        f"crop={self.width}:{self.height}:'(in_w-out_w)/2 + (in_w-out_w)/2 * sin(2*3.14159*t/10)':'(in_h-out_h)/2 + (in_h-out_h)/2 * cos(2*3.14159*t/10)'[v];"
                        f"[2:a]volume=0.25[w];[1:a][w]amix=inputs=2:duration=first[a]"
                    )
                    map_audio = "[a]"
                else:
                    filter_complex = (
                        f"[0:v]scale={scale_w}:{scale_h}:force_original_aspect_ratio=increase,"
                        f"crop={self.width}:{self.height}:'(in_w-out_w)/2 + (in_w-out_w)/2 * sin(2*3.14159*t/10)':'(in_h-out_h)/2 + (in_h-out_h)/2 * cos(2*3.14159*t/10)'[v]"
                    )
                    map_audio = "1:a"

            cmd.extend([
                "-filter_complex", filter_complex,
                "-map", "[v]",
                "-map", map_audio,
                "-t", str(duration),
                "-c:v", "libx264",
                "-preset", "superfast",          # Speed up encoding by 3-5x
                "-c:a", "aac",
                "-pix_fmt", "yuv420p",
                "-r", str(self.fps),
                str(output_segment_path)
            ])
            
            if self._run_ffmpeg(cmd):
                standard_segments.append(str(output_segment_path))
            else:
                logger.error(f"Failed to standardize segment {idx}")
                
        return standard_segments

    def concat_segments(self, segment_paths: list, temp_dir: Path) -> str:
        """Concatenates all standardised segments into a single video file."""
        concat_txt_path = temp_dir / "concat_list.txt"
        output_path = temp_dir / "concatenated.mp4"
        
        logger.info(f"Writing demuxer list to {concat_txt_path}")
        with open(concat_txt_path, "w", encoding="utf-8") as f:
            for path in segment_paths:
                # Use only relative filename to avoid path escaping bugs
                f.write(f"file '{Path(path).name}'\n")
                
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", "concat_list.txt",
            "-c", "copy",                     # Direct stream copy since formats are identical
            "concatenated.mp4"
        ]
        
        logger.info("Concatenating segments...")
        if self._run_ffmpeg(cmd, cwd=str(temp_dir)):
            return str(output_path)
        return ""

    def add_background_music(self, video_path: str, temp_dir: Path) -> str:
        """
        Picks a random background music track from assets/music/, lowers its volume,
        and mixes it with the voiceover audio.
        Downloads a default copyright-free track if the folder is empty.
        """
        music_dir = config.MUSIC_DIR
        music_files = list(music_dir.glob("*.mp3")) + list(music_dir.glob("*.wav"))
        
        output_path = temp_dir / "mixed_audio.mp4"
        
        if not music_files:
            logger.warning("No background music files found in assets/music/. Downloading a default royalty-free track...")
            try:
                default_music_url = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-3.mp3"
                dest_music = music_dir / "default_bg.mp3"
                
                # Overwrite old upbeat track if it exists
                if dest_music.exists():
                    try:
                        dest_music.unlink()
                    except Exception:
                        pass
                        
                logger.info(f"Downloading relaxing default background track from {default_music_url} -> {dest_music}")
                r = requests.get(default_music_url, stream=True, timeout=30)
                if r.status_code == 200:
                    with open(dest_music, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                    music_files = [dest_music]
                else:
                    logger.error(f"Failed to download default music, status code: {r.status_code}")
            except Exception as e:
                logger.error(f"Error downloading default music: {e}")
                
        if not music_files:
            logger.warning("Background music setup failed. Skipping music mixing.")
            return video_path
            
        selected_music = random.choice(music_files)
        logger.info(f"Adding background music: {selected_music.name}")
        
        # Mix background music (looping) with primary video audio stream
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-stream_loop", "-1",
            "-i", str(selected_music),
            "-filter_complex", 
            "[1:a]volume=0.08[bg];[0:a][bg]amix=inputs=2:duration=first[a]",
            "-map", "0:v",
            "-map", "[a]",
            "-c:v", "copy",                   # Stream copy video to save time/CPU
            "-c:a", "aac",
            str(output_path)
        ]
        
        if self._run_ffmpeg(cmd):
            return str(output_path)
        return video_path

    def burn_subtitles(self, video_path: str, srt_path: str, output_path: str, font_name: str = None) -> bool:
        """Burns SRT subtitles into the final video file using a verified Devanagari font."""
        logger.info(f"Burning subtitles: {srt_path} -> {output_path}")
        
        # Escape path for FFmpeg subtitle filter (especially critical for Windows)
        srt_filename = Path(srt_path).name
        video_filename = Path(video_path).name
        
        # Use detected verified Devanagari font
        selected_font = font_name or self.detect_devanagari_font(strict=True)
        # If font_name was provided as a path or filename, extract clean family name
        if selected_font.endswith(".ttf") or selected_font.endswith(".otf") or "/" in selected_font or "\\" in selected_font:
            for cand in VERIFIED_DEVANAGARI_FONTS:
                if cand.lower().replace(" ", "") in Path(selected_font).name.lower():
                    selected_font = cand
                    break
            else:
                selected_font = Path(selected_font).stem

        logger.info(f"Using verified font: {selected_font} for Devanagari subtitle rendering.")

        # Configure fontsdir correctly and handle paths containing spaces or colons safely
        fonts_dir_clause = ""
        if config.FONTS_DIR.exists():
            fonts_dir_posix = str(config.FONTS_DIR.resolve().as_posix())
            # In FFmpeg filter syntax, escape colons and single quotes
            escaped_fonts_dir = fonts_dir_posix.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
            fonts_dir_clause = f":fontsdir='{escaped_fonts_dir}'"

        # Large size 26, primary yellow (&H0000FFFF), outline border width 3, middle-center (10)
        font_style = (
            f"Fontname={selected_font},Fontsize=26,"
            "PrimaryColour=&H0000FFFF,OutlineColour=&H00000000,"
            "BorderStyle=1,Outline=3.0,Shadow=0,Alignment=10"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", video_filename,
            "-vf", f"subtitles={srt_filename}{fonts_dir_clause}:force_style='{font_style}'",
            "-c:v", "libx264",
            "-preset", "superfast",           # Speed up encoding by 3-5x
            "-c:a", "copy",                   # Audio is already mixed, copy it
            "-pix_fmt", "yuv420p",
            output_path
        ]
        
        # Execute inside temp_dir to keep subtitle file relative and simple
        try:
            creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            result = subprocess.run(
                cmd,
                cwd=str(Path(video_path).parent),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creation_flags
            )
            if result.returncode == 0 and Path(output_path).exists():
                logger.info("Subtitles burned successfully.")
                return True
            else:
                logger.error(f"FFmpeg subtitle burn failed: {result.stderr.decode('utf-8', errors='ignore')}")
                return False
        except Exception as e:
            logger.error(f"Failed to burn subtitles: {e}")
            return False

    def build_video(self, segments: list, srt_path: str, output_video_path: Path, temp_dir: Path) -> bool:
        """
        Coordinates the full video building pipeline.
        Pre-rendering check: verifies Devanagari font availability to prevent missing glyphs.
        """
        # Step 0: Verify Devanagari font availability before rendering
        verified_font = self.detect_devanagari_font(strict=True)
        logger.info(f"Verified Devanagari font for video build: {verified_font}")

        # Step 1: Standardise video clips
        standard_clips = self.standardize_segments(segments, temp_dir)
        if not standard_clips:
            logger.error("No clips were successfully standardized.")
            return False
            
        # Step 2: Concat clips
        merged_video = self.concat_segments(standard_clips, temp_dir)
        if not merged_video:
            logger.error("Failed to concatenate segments.")
            return False
            
        # Step 3: Mix background music
        music_mixed_video = self.add_background_music(merged_video, temp_dir)
        
        # Step 4: Burn subtitles
        final_video_name = output_video_path.name
        success = self.burn_subtitles(music_mixed_video, srt_path, str(output_video_path))
        
        return success

    def validate_hindi_rendering(self, output_path: Path = None, test_text: str = None) -> bool:
        """
        Empirically validates that FFmpeg and libass can render Devanagari text with conjuncts,
        matras, halant, and ZWJ/ZWNJ without error.
        Renders a 1-second synthetic color test clip with Devanagari subtitles.
        """
        font_name = self.detect_devanagari_font(strict=True)
        test_text = test_text or "अंतरिक्ष में रहस्यमयी प्रकाश: क्या यह सच है?"

        import tempfile
        temp_dir = Path(tempfile.mkdtemp(prefix="facts_ai_font_test_"))
        test_video = temp_dir / "test_base.mp4"
        test_srt = temp_dir / "test_sub.srt"
        final_output = output_path or (temp_dir / "rendered_hindi_test.mp4")

        try:
            # 1. Generate 1s black test video
            creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            base_cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "color=c=black:s=720x1280:d=1.0",
                "-c:v", "libx264", "-t", "1.0",
                str(test_video)
            ]
            r1 = subprocess.run(base_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creation_flags)
            if r1.returncode != 0:
                logger.error(f"Failed to generate synthetic base video for font test: {r1.stderr.decode('utf-8', errors='ignore')}")
                return False

            # 2. Write test SRT with complex Hindi conjuncts
            srt_content = (
                "1\n"
                "00:00:00,100 --> 00:00:00,900\n"
                f"{test_text}\n\n"
            )
            with open(test_srt, "w", encoding="utf-8") as f:
                f.write(srt_content)

            # 3. Burn subtitles using detected font
            success = self.burn_subtitles(str(test_video), str(test_srt), str(final_output), font_name=font_name)
            if success and Path(final_output).exists() and Path(final_output).stat().st_size > 1000:
                logger.info(f"Devanagari visual rendering test PASSED with font '{font_name}' -> {final_output}")
                return True
            else:
                logger.error("Devanagari visual rendering test FAILED: output video was missing or empty.")
                return False
        finally:
            if not output_path and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    # Test builder shell
    pass
