"""Instagram data fetching — URL parsing, post metadata, and media download."""

import os
import re
import sys

import instaloader

from .constants import IG_URL_PATTERN


def extract_shortcode(url: str) -> str:
    """Extract shortcode from an Instagram URL."""
    match = re.search(IG_URL_PATTERN, url)
    if not match:
        print(f"Could not extract shortcode from: {url}")
        sys.exit(1)
    return match.group(1)


def fetch_post(shortcode: str) -> instaloader.Post:
    """Fetch post metadata via instaloader."""
    L = instaloader.Instaloader()
    return instaloader.Post.from_shortcode(L.context, shortcode)


def download_media(post: instaloader.Post, shortcode: str) -> str:
    """Download post media into instagram_pipeline/downloads/. Returns the download directory path."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    downloads_dir = os.path.join(script_dir, "downloads")
    target_name = f"{post.owner_username}_{shortcode}"
    download_dir = os.path.join(downloads_dir, target_name)
    os.makedirs(downloads_dir, exist_ok=True)
    original_cwd = os.getcwd()
    os.chdir(downloads_dir)
    L = instaloader.Instaloader()
    L.download_post(post, target=target_name)
    os.chdir(original_cwd)
    return download_dir
