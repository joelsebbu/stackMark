"""Media helpers — base64 encoding, file discovery, and ffmpeg frame extraction."""

import base64
import os
import subprocess

from .constants import FRAME_INTERVAL_SECONDS


def encode_file_base64(file_path: str) -> str:
    """Read a file and return its base64-encoded string."""
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def find_files(directory: str, extensions: tuple[str, ...]) -> list[str]:
    """Find files with given extensions in a directory, sorted by name."""
    return sorted(
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if f.lower().endswith(extensions)
    )


def get_video_duration(video_path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def extract_frames(video_path: str, output_dir: str) -> list[str]:
    """Extract frames from video at regular intervals using ffmpeg.

    Returns list of frame file paths sorted by time.
    """
    duration = get_video_duration(video_path)
    frame_count = max(1, int(duration / FRAME_INTERVAL_SECONDS))
    print(f"   Duration: {duration:.1f}s — extracting ~{frame_count} frames")

    subprocess.run(
        [
            "ffmpeg", "-i", video_path,
            "-vf", f"fps=1/{FRAME_INTERVAL_SECONDS}",
            "-q:v", "2",
            os.path.join(output_dir, "frame_%04d.jpg"),
        ],
        capture_output=True,
    )

    frames = sorted(
        os.path.join(output_dir, f)
        for f in os.listdir(output_dir)
        if f.startswith("frame_") and f.endswith(".jpg")
    )
    print(f"   Extracted {len(frames)} frames")
    return frames
