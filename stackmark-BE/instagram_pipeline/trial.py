"""Quick trial script for instaloader.

Usage:
    uv run python instagram_pipeline/trial.py "https://www.instagram.com/p/SHORTCODE/"
    uv run python instagram_pipeline/trial.py "https://www.instagram.com/reel/SHORTCODE/" --download
"""

import os
import re
import sys

import instaloader


def extract_shortcode(url: str) -> str:
    """Extract shortcode from an Instagram URL."""
    match = re.search(r"instagram\.com/(?:p|reel)/([A-Za-z0-9_-]+)", url)
    if not match:
        print(f"Could not extract shortcode from: {url}")
        sys.exit(1)
    return match.group(1)



def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: uv run python instagram_pipeline/trial.py <instagram-url> [--download] [--comments]")
        sys.exit(1)

    url = sys.argv[1]
    shortcode = extract_shortcode(url)
    print(f"Shortcode: {shortcode}\n")

    L = instaloader.Instaloader()
    post = instaloader.Post.from_shortcode(L.context, shortcode)

    print(f"Type:      {post.typename}")
    print(f"Date:      {post.date}")
    print(f"Owner:     {post.owner_username}")
    print(f"Likes:     {post.likes}")
    print(f"Comments:  {post.comments}")
    print(f"Media URL: {post.url}")
    print(f"Hashtags:  {post.caption_hashtags}")
    print(f"Is video:  {post.is_video}")
    if post.is_video:
        print(f"Video URL: {post.video_url}")
    print(f"\nCaption:\n{post.caption}")

    # If it's a carousel (multiple images/videos), list all nodes
    if post.typename == "GraphSidecar":
        print(f"\nCarousel items:")
        for i, node in enumerate(post.get_sidecar_nodes(), 1):
            print(f"  {i}. {node.typename} — {node.display_url}")

    # Download media into organized subfolder
    if "--download" in sys.argv:
        download_dir = os.path.join("instagram_pipeline", "downloads", f"{post.owner_username}_{shortcode}")
        print(f"\nDownloading media to {download_dir}/...")
        L.download_post(post, target=download_dir)
        print("Done!")


if __name__ == "__main__":
    main()
