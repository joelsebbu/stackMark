"""LLM message building — constructs multimodal payloads for OpenRouter."""

import os
from typing import Any

from .constants import FRAME_INTERVAL_SECONDS
from .media import encode_file_base64


def build_photo_messages(
    caption: str, image_paths: list[str], prompt: str
) -> list[dict[str, Any]]:
    """Build multimodal messages for photo/carousel posts."""
    content: list[dict[str, Any]] = []

    for img_path in image_paths:
        img_b64 = encode_file_base64(img_path)
        content.append({"type": "text", "text": "[IMAGE]"})
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
        })

    content.append({
        "type": "text",
        "text": f'Caption: "{caption}"\n\n{prompt}',
    })
    return [{"role": "user", "content": content}]


def build_video_messages(
    caption: str, video_path: str, prompt: str
) -> list[dict[str, Any]]:
    """Build multimodal messages with full base64 video."""
    video_b64 = encode_file_base64(video_path)
    ext = os.path.splitext(video_path)[1].lstrip(".")
    mime = f"video/{ext}" if ext else "video/mp4"

    content = [
        {"type": "text", "text": "[VIDEO]"},
        {
            "type": "video_url",
            "video_url": {"url": f"data:{mime};base64,{video_b64}"},
        },
        {
            "type": "text",
            "text": f'Caption: "{caption}"\n\n{prompt}',
        },
    ]
    return [{"role": "user", "content": content}]


def build_frames_messages(
    caption: str, frame_paths: list[str], prompt: str
) -> list[dict[str, Any]]:
    """Build multimodal messages from extracted video frames."""
    content: list[dict[str, Any]] = []

    for frame_path in frame_paths:
        frame_b64 = encode_file_base64(frame_path)
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{frame_b64}"},
        })

    content.append({
        "type": "text",
        "text": (
            f"These are {len(frame_paths)} frames extracted at "
            f"{FRAME_INTERVAL_SECONDS}-second intervals from a video.\n\n"
            f'Caption: "{caption}"\n\n{prompt}'
        ),
    })
    return [{"role": "user", "content": content}]
