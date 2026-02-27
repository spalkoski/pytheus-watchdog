#!/bin/bash
# Pytheus Watchdog Deployment Script
# This script automates the initial deployment process

set -e  # Exit on error

echo "🛡️  Pytheus Watchdog Deployment Script"
echo "========================================"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

echo "✓ Docker and Docker Compose are installed"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from .env.example..."
    cp .env.example .env
    echo "✓ Created .env file"
    echo ""
    echo "⚠️  IMPORTANT: Please edit .env and fill in your credentials:"
    echo "   - SECRET_KEY (generate with: openssl rand -hex 32)"
    echo "   - API_TOKEN_SECRET (generate with: openssl rand -hex 32)"
    echo "   - ADMIN_PASSWORD"
    echo "   - SLACK_WEBHOOK_URL"
    echo "   - TELEGRAM_BOT_TOKEN"
    echo "   - TELEGRAM_CHAT_ID"
    echo ""
    read -p "Press Enter after editing .env to continue..."
fi

# Check if config/watchdog.yaml exists
if [ ! -f config/watchdog.yaml ]; then
    echo "❌ config/watchdog.yaml not found. Please create it first."
    exit 1
fi

echo "✓ Configuration files found"
echo ""

# Generate secrets if needed
if grep -q "your-secret-key-here" .env; then
    echo "⚠️  Generating random secrets..."
    SECRET_KEY=$(openssl rand -hex 32)
    API_TOKEN_SECRET=$(openssl rand -hex 32)

    # Update .env file (macOS compatible)
    sed -i.bak "s/SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" .env
    sed -i.bak "s/API_TOKEN_SECRET=.*/API_TOKEN_SECRET=$API_TOKEN_SECRET/" .env
    rm .env.bak

    echo "✓ Generated secrets"
    echo ""
fi

# Create data directory
mkdir -p data
echo "✓ Created data directory"
echo ""

# Build Docker image
echo "📦 Building Docker image..."
docker compose build
echo "✓ Docker image built"
echo ""

# Start containers
echo "🚀 Starting containers..."
docker compose up -d
echo "✓ Containers started"
echo ""

# Wait for health check
echo "⏳ Waiting for application to be healthy..."
sleep 10

for i in {1..12}; do
    if curl -f http://localhost:8000/api/health > /dev/null 2>&1; then
        echo "✓ Application is healthy!"
        break
    fi

    if [ $i -eq 12 ]; then
        echo "❌ Health check failed. Check logs with: docker compose logs"
        exit 1
    fi

    echo "   Attempt $i/12..."
    sleep 5
done

echo ""
echo "✅ Deployment Complete!"
echo ""
echo "Next steps:"
echo "1. Configure Nginx reverse proxy:"
echo "   sudo cp nginx/watchdog.conf /etc/nginx/sites-available/"
echo "   sudo ln -s /etc/nginx/sites-available/watchdog.conf /etc/nginx/sites-enabled/"
echo "   sudo nginx -t"
echo "   sudo systemctl reload nginx"
echo ""
echo "2. Set up SSL with Let's Encrypt:"
echo "   sudo certbot --nginx -d watchdog.pytheus.com"
echo ""
echo "3. Access your dashboard:"
echo "   Local: http://localhost:8000"
echo "   Production: https://watchdog.pytheus.com"
echo ""
echo "4. View logs:"
echo "   docker compose logs -f"
echo ""
echo "5. Get dead man's switch webhook URLs from the dashboard"
echo ""
