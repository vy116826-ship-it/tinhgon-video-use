#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Video-Use Platform — VPS Deployment Script
# Run this on the VPS: bash deploy.sh
# ═══════════════════════════════════════════════════════════════

set -e

PROJECT_DIR="/root/projects/video-use"
REPO_URL="https://github.com/vy116826-ship-it/tinhgon-video-use.git"

echo "══════════════════════════════════════════════════"
echo "  Video-Use Platform — Deploying..."
echo "══════════════════════════════════════════════════"

# 1. Clone or pull
if [ -d "$PROJECT_DIR/.git" ]; then
    echo "→ Pulling latest code..."
    cd "$PROJECT_DIR"
    git pull origin main
else
    echo "→ Cloning repository..."
    mkdir -p "$PROJECT_DIR"
    git clone "$REPO_URL" "$PROJECT_DIR"
    cd "$PROJECT_DIR"
fi

# 2. Create .env if not exists
if [ ! -f ".env" ]; then
    echo "→ Creating .env from template..."
    cp .env.example .env
    # Generate a random secret key
    SECRET=$(openssl rand -hex 32)
    sed -i "s/SECRET_KEY=.*/SECRET_KEY=$SECRET/" .env
    echo "→ ⚠️  Edit .env to add your API keys: nano .env"
fi

# 3. Create data directories
echo "→ Creating data directories..."
mkdir -p data/{uploads,projects,outputs,db}

# 4. Build and start containers
echo "→ Building Docker images..."
docker compose build --no-cache

echo "→ Starting services..."
docker compose up -d

# 5. Verify
echo ""
echo "→ Checking container status..."
sleep 5
docker compose ps

echo ""
echo "══════════════════════════════════════════════════"
echo "  ✅ Deployment Complete!"
echo ""
echo "  Access: http://$(hostname -I | awk '{print $1}'):8880"
echo ""
echo "  Next steps:"
echo "  1. Edit API keys:  nano /root/projects/video-use/.env"
echo "  2. Restart:         docker compose restart"
echo "  3. View logs:       docker compose logs -f"
echo "══════════════════════════════════════════════════"
