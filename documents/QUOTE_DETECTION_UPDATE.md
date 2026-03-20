# Quote Tweet Detection Update

## Overview
This update improves quote tweet handling in the StackMark ingestion pipeline. The system now uses deterministic tweet relationship data from the X API first, then falls back to model-based detection only when needed.

## What Changed
- Added deterministic quote tweet detection using X API v2 metadata.
- Kept the existing Grok + x_search quote detection as a fallback path.
- Updated detection flow to prefer X API and only fall back when X API is unavailable or fails.
- Improved quote handling so a detected quoted tweet ID can still be processed even if a canonical quoted URL is not returned.
- Extended URL classification to support `x.com/i/web/status/...` links.
- Kept merge behavior as a single bookmark record, combining main tweet and quoted tweet enrichment.

## Configuration
- Added support for `X_API_BEARER_TOKEN` from environment variables.
- Added `requests` dependency for X API calls.

## Validation Performed
- Verified deterministic detection using the provided quote tweet URL.
- Confirmed the quoted tweet was correctly identified through X API.
- Added and ran unit tests for quote parsing and URL classification behavior.
- Verified pipeline compiles successfully after changes.

## Expected Impact
- Fewer false negatives when detecting quote tweets.
- Better enrichment quality for “comment-only” quote tweets (for example, short text like "LOL").
- More reliable merged bookmark records for downstream search and retrieval.
