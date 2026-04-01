# StackMark — EC2 + RDS Deployment Guide

## Overview
- **EC2** — runs the FastAPI app
- **RDS** — PostgreSQL with pgvector for vector storage

---

## Step 1: Set up RDS PostgreSQL

### Create the instance
1. Go to **AWS Console → RDS → Create database**
2. Choose **PostgreSQL** (version 15 or higher — required for pgvector)
3. Pick **Free tier** or **Single-AZ** for a personal project
4. Settings:
   - DB instance identifier: `stackmark-db`
   - Master username: `stackmark`
   - Master password: choose a strong password
5. Instance config: `db.t3.micro` (free tier eligible)
6. Storage: 20 GB gp3 (default is fine)
7. Connectivity:
   - VPC: use the same VPC as your EC2 instance
   - Public access: **No** (EC2 will connect privately)
   - Create a new security group or use an existing one
8. Database name: `stackmark`
9. Click **Create database**

### Configure the security group
1. Go to the RDS instance → **Security group**
2. Edit inbound rules → **Add rule**:
   - Type: PostgreSQL
   - Port: 5432
   - Source: your EC2 instance's security group (or its private IP)
3. Save

### Enable pgvector
Once the RDS instance is available, connect from your EC2 instance and enable the extension:

```bash
psql -h <your-rds-endpoint> -U stackmark -d stackmark
```

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

That's it. pgvector is available as a trusted extension on RDS PostgreSQL 15+.

### Run the Alembic migration
From your EC2 instance (after app setup in Step 2):

```bash
cd ~/stackmark-BE
uv run alembic upgrade head
```

This creates the `embeddings` table with the HNSW vector index.

---

## Step 2: Set up EC2

### Launch the instance
1. Go to **AWS Console → EC2 → Launch instance**
2. Settings:
   - Name: `stackmark-server`
   - AMI: **Ubuntu 24.04 LTS**
   - Instance type: `t3.small` (2 vCPU, 2 GB RAM — Playwright needs this)
   - Key pair: create or select one for SSH
3. Network:
   - Same VPC as RDS
   - Auto-assign public IP: **Enable**
4. Security group — allow:
   - SSH (port 22) from your IP
   - HTTP (port 8000) from anywhere (or restrict to your IP for now)
5. Storage: 20 GB gp3
6. Launch

### SSH into the instance

```bash
ssh -i your-key.pem ubuntu@<ec2-public-ip>
```

### Install system dependencies

```bash
# Update packages
sudo apt update && sudo apt upgrade -y

# Python build deps + ffmpeg + postgres client
sudo apt install -y ffmpeg postgresql-client curl git

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
```

### Clone and set up the app

```bash
cd ~
git clone <your-repo-url> stackmark-BE
cd stackmark-BE

# Install Python dependencies
uv sync

# Install Playwright Chromium
uv run playwright install chromium
uv run playwright install-deps chromium
```

### Configure environment

```bash
cp .env.example .env
nano .env
```

Set these values (use the RDS endpoint as DB_HOST):

```
OPENROUTER_API_KEY=your-key
X_API_BEARER_TOKEN=your-token

DB_USER=stackmark
DB_PASSWORD=your-rds-password
DB_HOST=stackmark-db.xxxxxxxxxxxx.us-east-1.rds.amazonaws.com
DB_PORT=5432
DB_NAME=stackmark
```

### Verify RDS connection

```bash
psql -h <your-rds-endpoint> -U stackmark -d stackmark -c "SELECT 1;"
```

### Run the migration

```bash
uv run alembic upgrade head
```

### Test the app

```bash
uv run uvicorn app:app --host 0.0.0.0 --port 8000
```

From your local machine:

```bash
curl http://<ec2-public-ip>:8000/health
```

---

## Step 3: Keep the app running with systemd

Create a service file so the app starts on boot and restarts on crash:

```bash
sudo nano /etc/systemd/system/stackmark.service
```

```ini
[Unit]
Description=StackMark FastAPI Server
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/stackmark-BE
ExecStart=/home/ubuntu/.local/bin/uv run uvicorn app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
Environment=PATH=/home/ubuntu/.local/bin:/usr/bin:/bin

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable stackmark
sudo systemctl start stackmark

# Check status
sudo systemctl status stackmark

# View logs
sudo journalctl -u stackmark -f
```

---

## Quick reference

| What | Where |
|------|-------|
| App | `http://<ec2-public-ip>:8000` |
| Health check | `GET /health` |
| Ingest a URL | `POST /ingest` with `{"url": "..."}` |
| Search | `POST /search` with `{"query": "...", "top_k": 3}` |
| App logs | `sudo journalctl -u stackmark -f` |
| Restart app | `sudo systemctl restart stackmark` |
| RDS endpoint | `stackmark-db.xxxxxxxxxxxx.<region>.rds.amazonaws.com` |
| SSH | `ssh -i your-key.pem ubuntu@<ec2-public-ip>` |
