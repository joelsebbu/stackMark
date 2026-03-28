# StackMark — Twitter DM Bot Setup Guide

## What We're Building

StackMark is a personal bookmark manager. We already have working ingestion pipelines that take a URL, scrape it, run it through an AI model for enrichment, generate an embedding, and store it in PostgreSQL with pgvector for semantic search. We have pipelines for X/Twitter, Instagram, YouTube, and generic web pages.

Right now, all pipelines are triggered manually from the CLI:

```
uv run -m x_pipeline.pipeline "https://x.com/someone/status/123456"
```

**The next step:** build a Twitter bot so that when I DM a link to my bot account on Twitter, it picks up that link and forwards it to the backend for processing. This turns Twitter DMs into a convenient mobile-friendly input method — I can share any link to my bot from my phone and it gets bookmarked automatically.

For now, the bot just needs to:
1. Poll for new DMs sent to the bot account
2. Extract any URLs from those messages
3. Forward the URL to our backend (initially just print/console it — we'll wire it to the correct pipeline later)

## Why a Twitter Bot?

- Twitter's share sheet on mobile makes it trivial to share links via DM
- No need to build a separate mobile app or web frontend for link ingestion
- The bot account already exists (or will be created) on the same platform as one of our main content sources
- Simple polling architecture — no webhooks, no public server needed

## What We Need from the Twitter Developer Portal

The bot needs to **read DMs** sent to it. Twitter's DM endpoints require **user-context authentication** (OAuth 1.0a), not just an app-only bearer token. The bearer token we already have (`X_API_BEARER_TOKEN`) is app-only and can only access public data like tweets — it cannot read DMs.

### Credentials Required

We need **4 credentials** from the Twitter Developer Portal (https://developer.x.com):

| Credential | Also Called | Where to Find |
|---|---|---|
| `X_API_KEY` | Consumer Key, API Key | App Settings > Keys and Tokens > Consumer Keys |
| `X_API_SECRET` | Consumer Secret, API Secret Key | Same section as above |
| `X_ACCESS_TOKEN` | Access Token | App Settings > Keys and Tokens > Authentication Tokens |
| `X_ACCESS_TOKEN_SECRET` | Access Token Secret | Same section as above |

### Step-by-Step Setup

#### 1. Twitter Developer Account & Project

- Go to https://developer.x.com and sign in with the Twitter account that will act as the bot
- If you don't have a developer account yet, apply for one. The **Free tier** gives you access to the v2 API with DM read capability
- Create a **Project** (if you don't have one) and an **App** inside it

#### 2. App Permissions

This is critical. The app must have the right permissions enabled:

- Go to your App Settings > **User authentication settings** > Edit
- Set **App permissions** to **Read and Write and Direct Messages** (all three — we need DM read access)
- Set **Type of App** to whatever fits (likely "Web App, Automated App or Bot")
- Set a **Callback URL** — can be `https://localhost` if you don't need OAuth web flow (we don't, since we're using the bot's own tokens)
- Set a **Website URL** — can be anything, e.g., `https://example.com`
- Save changes

**Important:** If you change permissions AFTER generating tokens, you must **regenerate** the Access Token and Access Token Secret. The old tokens will still carry the old permission scope.

#### 3. Generate All 4 Credentials

- Go to **Keys and Tokens** tab
- Under **Consumer Keys**: Generate (or Regenerate) the API Key and API Secret. Copy them immediately — they're only shown once.
- Under **Authentication Tokens**: Generate the Access Token and Access Token Secret. Copy them immediately.
- Make sure the Access Token says it was generated with **Read, Write, and Direct Messages** permissions. If it says "Read only" or "Read and Write", go back to step 2 and fix permissions, then regenerate.

#### 4. Verify Access Level

The Free tier of the Twitter API v2 should include:
- `GET /2/dm_events` — list DM events (this is what our bot will poll)
- `dm.read` scope

If you're on the Free tier and DM access is restricted, you may need the **Basic** tier ($100/month) which explicitly includes DM read/write. Check current pricing and access at https://developer.x.com/en/portal/products.

#### 5. Add Credentials to Our Project

Once you have all 4 values, they need to go in our `.env` file at `stackmark-BE/.env`:

```env
# Existing
X_API_BEARER_TOKEN=AAAA...   (already have this)

# New — for DM bot (OAuth 1.0a user context)
X_API_KEY=your_consumer_key_here
X_API_SECRET=your_consumer_secret_here
X_ACCESS_TOKEN=your_access_token_here
X_ACCESS_TOKEN_SECRET=your_access_token_secret_here
```

## How the Bot Will Work (Architecture)

```
[You DM a link to @YourBotAccount on Twitter]
        │
        v
[Bot polls GET /2/dm_events every N seconds]
        │
        v
[New DM detected → extract URL from message text]
        │
        v
[Forward URL to backend → console.log for now]
        │
        v
[Later: route to correct pipeline based on URL pattern]
```

### Technical Details

- **Polling, not webhooks** — simpler setup, no public server needed. We poll the `GET /2/dm_events` endpoint periodically (e.g., every 30 seconds)
- **OAuth 1.0a signing** — every request to the DM endpoint must be signed with all 4 credentials. We'll use the `requests-oauthlib` Python library for this
- **Deduplication** — we track the last seen DM event ID so we only process new messages
- **URL extraction** — simple regex to pull URLs from DM text
- **Rate limits** — Free tier allows ~15 requests per 15 minutes on the DM endpoint, so polling every 60 seconds is safe

### What Already Exists in the Project

- **Python backend** at `stackmark-BE/` managed with `uv`
- **Working pipelines** for X/Twitter, Instagram, YouTube, and web pages
- **Database** (PostgreSQL + pgvector) with embeddings table
- **Environment config** via `.env` and `python-dotenv`
- **Existing Twitter API usage** in `x_pipeline/pipeline.py` (uses bearer token for public tweet data)

The bot will be a new module (e.g., `twitter_bot/`) alongside the existing pipelines.

## Quick Test to Verify Credentials Work

Once the credentials are set up, here's a quick test to verify DM access works:

```python
import os
from requests_oauthlib import OAuth1Session
from dotenv import load_dotenv

load_dotenv()

twitter = OAuth1Session(
    os.getenv("X_API_KEY"),
    client_secret=os.getenv("X_API_SECRET"),
    resource_owner_key=os.getenv("X_ACCESS_TOKEN"),
    resource_owner_secret=os.getenv("X_ACCESS_TOKEN_SECRET"),
)

# Fetch recent DM events
response = twitter.get("https://api.x.com/2/dm_events", params={"max_results": 5})
print(response.status_code)
print(response.json())
```

If this returns `200` with DM data (or an empty list), the credentials are working. If it returns `401` or `403`, the permissions or tokens are wrong — revisit the steps above.

## Summary

| What | Status |
|---|---|
| Twitter Developer Account | Need to verify / create |
| App with DM permissions | Need to configure |
| OAuth 1.0a credentials (4 keys) | Need to generate |
| Add to `.env` | Do after generating keys |
| Build the bot module | Do after credentials are verified |
