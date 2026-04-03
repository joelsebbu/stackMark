# StackMark — Exposing the Backend to the Internet

## The Problem

The StackMark frontend is hosted on **AWS Amplify** (public HTTPS URL). The backend is a **FastAPI server** running locally — first on a laptop for testing, eventually on a **Raspberry Pi 4B** at home.

The frontend needs to reach the backend API over the internet. This means:
1. The backend needs a **public URL with HTTPS** (browsers block HTTP requests from HTTPS pages — mixed content policy)
2. The backend needs **CORS headers** so the browser allows cross-origin requests from the Amplify domain
3. The URL should ideally be **stable** so the frontend doesn't need constant redeployment

### Why not just use the public IP?

- Home routers block incoming traffic by default — requires port forwarding setup
- Most ISPs assign **dynamic IPs** that change without notice
- No HTTPS — Amplify is HTTPS, so the browser will block plain HTTP API calls (mixed content)
- Exposes your home IP and an open port directly to the internet

---

## What Was Changed in Code

### Backend — CORS middleware (`stackmark-BE/app.py`)

Added `CORSMiddleware` to FastAPI, configured via the `CORS_ORIGINS` environment variable (comma-separated list of allowed origins):

```python
allowed_origins = os.getenv("CORS_ORIGINS", "").split(",")
allowed_origins = [o.strip() for o in allowed_origins if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Usage:
```bash
CORS_ORIGINS="https://your-app.amplifyapp.com" uv run uvicorn app:app --host 0.0.0.0 --port 8000
```

### Frontend — configurable API base URL (`stackmark-FE`)

Both `src/pages/index.astro` and `src/pages/search.astro` were updated from:
```js
const API_BASE = "http://localhost:8000";
```
to:
```js
const API_BASE = import.meta.env.PUBLIC_API_BASE || "http://localhost:8000";
```

Set `PUBLIC_API_BASE` as an environment variable in Amplify Console (Environment variables section), then redeploy. Falls back to `localhost:8000` for local development.

---

## Proposal 1: Cloudflare Quick Tunnel (for testing)

**No account needed. One command.**

### Setup
```bash
# Install
sudo apt install cloudflared
# or download from https://github.com/cloudflare/cloudflared/releases

# Start the tunnel
cloudflared tunnel --url http://localhost:8000
```

Prints a URL like `https://random-words.trycloudflare.com` that proxies to your local server.

### Pros
- Zero config, no account, completely free
- HTTPS included automatically
- No port forwarding or networking knowledge needed

### Cons
- URL is **random and changes every restart** — must update `PUBLIC_API_BASE` in Amplify and redeploy each time
- Cloudflare sees your traffic (they terminate TLS)
- Only suitable for testing, not permanent

---

## Proposal 2: Cloudflare Named Tunnel (permanent, free)

Requires a **free Cloudflare account** and moving the domain's nameservers from Route 53 to Cloudflare.

### Setup
1. Add your domain to Cloudflare (free plan)
2. Change nameservers at Hostinger from Route 53 to Cloudflare's
3. Create a named tunnel:
   ```bash
   cloudflared tunnel login
   cloudflared tunnel create stackmark-api
   cloudflared tunnel route dns stackmark-api api.yourdomain.com
   ```
4. Run it:
   ```bash
   cloudflared tunnel run stackmark-api
   ```

### Pros
- Stable subdomain (`api.yourdomain.com`)
- Free, auto-HTTPS, no port forwarding
- Works great on Pi — runs as a systemd service

### Cons
- Must move DNS away from Route 53 to Cloudflare — breaks the current Amplify + Route 53 setup unless you migrate everything
- Cloudflare sees all traffic

---

## Proposal 3: Caddy + DuckDNS + Port Forwarding (permanent, self-hosted)

Keeps DNS on Route 53. Best for the Raspberry Pi permanent setup.

### Setup
1. **DuckDNS** (free dynamic DNS): register a subdomain like `stackmark-api.duckdns.org`, set up a cron to update your home IP
2. **Port forward** port 443 on your router to the Pi's local IP
3. **Caddy** reverse proxy on the Pi (auto-HTTPS via Let's Encrypt):
   ```
   stackmark-api.duckdns.org {
       reverse_proxy localhost:8000
   }
   ```
4. Optionally, add a CNAME in Route 53: `api.yourdomain.com → stackmark-api.duckdns.org`

### Pros
- No third party sees your traffic — you own the TLS termination
- Stable URL, works with Route 53
- Caddy handles HTTPS certificates automatically

### Cons
- Requires port forwarding on the router (one-time setup)
- DuckDNS cron must keep the IP updated (or use Route 53 dynamic DNS with a script)
- More moving parts than a tunnel

---

## Proposal 4: AWS EC2 (fully managed, paid)

There's already a guide for this: [`ec2-rds-deployment-guide.md`](ec2-rds-deployment-guide.md).

### Pros
- Everything stays in AWS (Amplify, Route 53, EC2, RDS)
- Static IP, HTTPS via a load balancer or Caddy on EC2
- No home network exposure

### Cons
- Costs money (~$5-10/month for t3.micro + RDS free tier)
- Playwright + ffmpeg + yt-dlp need a decently sized instance
- Defeats the purpose of running it on the Pi

---

## Recommendation

| Phase | Approach | Why |
|-------|----------|-----|
| **Now (testing on laptop)** | Cloudflare Quick Tunnel | Zero setup, instant HTTPS URL |
| **Later (Pi, permanent)** | Caddy + port forwarding (Proposal 3) or Cloudflare Named Tunnel (Proposal 2) | Stable URL, auto-HTTPS, reliable |

Start with the quick tunnel. Once things work end-to-end, decide between Proposals 2 and 3 based on whether you want to move DNS to Cloudflare or keep it on Route 53.
