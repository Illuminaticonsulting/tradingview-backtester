#!/bin/bash
set -e

# TradingView AI Backtester - VPS Deployment Script
# Usage: ./deploy.sh [--setup|--update|--logs|--restart]

VPS_HOST="159.89.195.109"
VPS_USER="root"
SSH_KEY="~/.ssh/kps_vps"
REMOTE_DIR="/opt/kps/tradingview-backtester"
REPO_URL="https://github.com/Illuminaticonsulting/tradingview-backtester.git"

SSH_CMD="ssh -i $SSH_KEY $VPS_USER@$VPS_HOST"
SCP_CMD="scp -i $SSH_KEY"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[x]${NC} $1"; exit 1; }

# Generate secure secrets
generate_secrets() {
    log "Generating secure secrets..."
    SECRET_KEY=$(openssl rand -hex 32)
    ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || openssl rand -base64 32)
    DB_PASSWORD=$(openssl rand -hex 16)
    echo "BACKTESTER_SECRET_KEY=$SECRET_KEY"
    echo "BACKTESTER_ENCRYPTION_KEY=$ENCRYPTION_KEY"
    echo "POSTGRES_PASSWORD=$DB_PASSWORD"
}

# Initial setup on VPS
setup() {
    log "Setting up VPS..."
    
    # Install Docker if not present
    $SSH_CMD << 'ENDSSH'
set -e

# Update system
apt-get update && apt-get upgrade -y

# Install Docker
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

# Install Docker Compose
if ! command -v docker-compose &> /dev/null; then
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# Create app directory
mkdir -p /opt/kps/tradingview-backtester
mkdir -p /opt/kps/tradingview-backtester/nginx/ssl

# Generate self-signed SSL cert for dev (replace with Let's Encrypt for prod)
if [ ! -f /opt/kps/tradingview-backtester/nginx/ssl/cert.pem ]; then
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout /opt/kps/tradingview-backtester/nginx/ssl/key.pem \
        -out /opt/kps/tradingview-backtester/nginx/ssl/cert.pem \
        -subj "/CN=localhost"
fi

echo "VPS setup complete!"
ENDSSH
    
    log "VPS setup complete!"
}

# Deploy/update application
deploy() {
    log "Deploying to VPS..."
    
    # Push latest code to GitHub
    log "Pushing to GitHub..."
    git add -A
    git commit -m "Deploy $(date +%Y-%m-%d_%H:%M:%S)" || true
    git push origin main || warn "Push failed or nothing to push"
    
    # Pull and deploy on VPS
    $SSH_CMD << ENDSSH
set -e
cd $REMOTE_DIR

# Pull latest code
if [ -d .git ]; then
    git pull origin main
else
    git clone $REPO_URL .
fi

# Check for .env file
if [ ! -f .env ]; then
    echo "ERROR: .env file not found!"
    echo "Create .env from .env.example and set your secrets"
    exit 1
fi

# Build and deploy
docker-compose down || true
docker-compose build --no-cache
docker-compose up -d

# Wait for services to be healthy
echo "Waiting for services..."
sleep 10
docker-compose ps

echo "Deployment complete!"
ENDSSH
    
    log "Deployment complete!"
    log "Access the app at: https://$VPS_HOST"
}

# Copy .env file to VPS
copy_env() {
    if [ ! -f .env ]; then
        error ".env file not found locally. Create it from .env.example first."
    fi
    log "Copying .env to VPS..."
    $SCP_CMD .env $VPS_USER@$VPS_HOST:$REMOTE_DIR/.env
    log ".env copied!"
}

# View logs
logs() {
    SERVICE=${1:-""}
    log "Fetching logs..."
    $SSH_CMD "cd $REMOTE_DIR && docker-compose logs -f --tail=100 $SERVICE"
}

# Restart services
restart() {
    SERVICE=${1:-""}
    log "Restarting services..."
    $SSH_CMD "cd $REMOTE_DIR && docker-compose restart $SERVICE"
}

# Stop services
stop() {
    log "Stopping services..."
    $SSH_CMD "cd $REMOTE_DIR && docker-compose down"
}

# Quick status check
status() {
    $SSH_CMD "cd $REMOTE_DIR && docker-compose ps"
}

# Setup SSL with Let's Encrypt
ssl() {
    DOMAIN=${1:-""}
    if [ -z "$DOMAIN" ]; then
        error "Usage: ./deploy.sh ssl yourdomain.com"
    fi
    
    log "Setting up SSL for $DOMAIN..."
    $SSH_CMD << ENDSSH
set -e
apt-get install -y certbot

# Stop nginx temporarily
cd $REMOTE_DIR
docker-compose stop nginx

# Get certificate
certbot certonly --standalone -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN

# Copy certificates
cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem $REMOTE_DIR/nginx/ssl/cert.pem
cp /etc/letsencrypt/live/$DOMAIN/privkey.pem $REMOTE_DIR/nginx/ssl/key.pem

# Restart nginx
docker-compose up -d nginx

echo "SSL setup complete for $DOMAIN"
ENDSSH
}

# Print usage
usage() {
    echo "TradingView AI Backtester - Deployment Script"
    echo ""
    echo "Usage: ./deploy.sh <command>"
    echo ""
    echo "Commands:"
    echo "  setup       Initial VPS setup (Docker, directories)"
    echo "  deploy      Deploy/update application"
    echo "  copy-env    Copy .env file to VPS"
    echo "  secrets     Generate secure secrets for .env"
    echo "  logs [svc]  View logs (optional: api, worker, frontend)"
    echo "  restart     Restart all services"
    echo "  stop        Stop all services"
    echo "  status      Show service status"
    echo "  ssl domain  Setup Let's Encrypt SSL"
    echo ""
}

# Main
case "${1:-}" in
    setup)    setup ;;
    deploy)   deploy ;;
    copy-env) copy_env ;;
    secrets)  generate_secrets ;;
    logs)     logs "${2:-}" ;;
    restart)  restart "${2:-}" ;;
    stop)     stop ;;
    status)   status ;;
    ssl)      ssl "${2:-}" ;;
    *)        usage ;;
esac
