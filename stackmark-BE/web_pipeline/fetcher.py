"""Web page fetching and HTML parsing.

Primary: lightweight httpx fetch (fast, Lambda-friendly).
Fallback: Playwright headless Chromium for JS-rendered pages (React, SPAs)
that return empty/minimal content from a plain HTTP request.
"""

import re
from typing import Any

from bs4 import BeautifulSoup
import httpx

from .constants import MAX_CONTENT_LENGTH, REQUEST_TIMEOUT

# Minimum chars of extracted text to consider the page "good enough"
# without falling back to Playwright
MIN_CONTENT_LENGTH = 200

_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def fetch_page(url: str) -> str:
    """Fetch a web page, trying httpx first and Playwright as fallback.

    Returns rendered HTML. Falls back to Playwright only if the httpx
    response yields too little text content (likely a JS-rendered SPA).
    """
    # Try lightweight httpx fetch up to 3 times before falling back
    print("   Trying lightweight HTTP fetch...")
    for attempt in range(1, 4):
        try:
            html = _fetch_with_httpx(url)
            main_text = _extract_main_text(BeautifulSoup(html, "html.parser"))

            if len(main_text) >= MIN_CONTENT_LENGTH:
                print(f"   Got {len(main_text)} chars of content — using HTTP response")
                return html

            print(f"   Attempt {attempt}/3: only {len(main_text)} chars of content")
        except Exception as e:
            print(f"   Attempt {attempt}/3 failed: {e}")

    # Fallback to Playwright for JS-rendered or blocked pages
    print("   All HTTP attempts returned insufficient content — falling back to headless browser...")
    return _fetch_with_playwright(url)


def _fetch_with_httpx(url: str) -> str:
    """Fast HTTP fetch using httpx."""
    response = httpx.get(
        url,
        headers={"User-Agent": _USER_AGENT},
        timeout=REQUEST_TIMEOUT / 1000,  # convert ms to seconds
        follow_redirects=True,
    )
    response.raise_for_status()
    return response.text


def _fetch_with_playwright(url: str) -> str:
    """Render page with headless Chromium via Playwright."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=_USER_AGENT)
        page.goto(url, timeout=REQUEST_TIMEOUT, wait_until="networkidle")
        html = page.content()
        browser.close()
    return html


def extract_metadata(html: str) -> dict[str, Any]:
    """Parse rendered HTML and extract page metadata + main text content."""
    soup = BeautifulSoup(html, "html.parser")

    # Page title
    title = soup.title.string.strip() if soup.title and soup.title.string else ""

    # Meta description
    meta_desc_tag = soup.find("meta", attrs={"name": "description"})
    meta_description = meta_desc_tag["content"].strip() if meta_desc_tag and meta_desc_tag.get("content") else ""

    # Open Graph tags
    def og(prop: str) -> str:
        tag = soup.find("meta", attrs={"property": f"og:{prop}"})
        return tag["content"].strip() if tag and tag.get("content") else ""

    # Extract main text content
    main_text = _extract_main_text(soup)

    return {
        "title": title,
        "meta_description": meta_description,
        "og_title": og("title"),
        "og_description": og("description"),
        "og_image": og("image"),
        "og_type": og("type"),
        "og_site_name": og("site_name"),
        "main_text": main_text,
    }


def _extract_main_text(soup: BeautifulSoup) -> str:
    """Extract and clean the main text content from a page."""
    # Work on a copy to avoid mutating the original
    soup_copy = BeautifulSoup(str(soup), "html.parser")

    # Remove non-content elements
    for tag_name in ["script", "style", "nav", "footer", "header", "aside", "noscript"]:
        for element in soup_copy.find_all(tag_name):
            element.decompose()

    # Prefer <main> or <article> if present, otherwise fall back to <body>
    target = soup_copy.find("main") or soup_copy.find("article") or soup_copy.find("body")
    if not target:
        return ""

    text = target.get_text(separator="\n", strip=True)

    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Truncate to max length
    if len(text) > MAX_CONTENT_LENGTH:
        text = text[:MAX_CONTENT_LENGTH] + "\n[truncated]"

    return text
