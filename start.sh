#!/bin/bash
# Quick start script for WhatsApp Bot with tunnel support

# Configuration
PORT=${PORT:-7349}
TUNNEL_METHOD=${TUNNEL_METHOD:-"auto"}  # auto, ngrok, serveo, localtunnel, cloudflared
NGROK_DOMAIN=${NGROK_DOMAIN:-""}  # Set your ngrok reserved domain here
SERVEO_SUBDOMAIN=${SERVEO_SUBDOMAIN:-""}  # Set your preferred serveo subdomain
CLOUDFLARED_TUNNEL=${CLOUDFLARED_TUNNEL:-""}  # Set your cloudflared tunnel name

# Start the FastAPI application in the background
echo "🚀 Starting WhatsApp Bot on port $PORT..."
uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT &
APP_PID=$!

# Wait for the app to start
echo "⏳ Waiting for server to start..."
sleep 3

# Check if app is running
if ! kill -0 $APP_PID 2>/dev/null; then
    echo "❌ Failed to start the application"
    exit 1
fi

echo "✅ Application is running on http://localhost:$PORT"
echo "📚 API Docs: http://localhost:$PORT/docs"
echo ""
echo "🌐 Creating public tunnel..."
echo "   This will expose your local server to the internet for WhatsApp webhook"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📍 Tunnel Method: $TUNNEL_METHOD"
if [ -n "$NGROK_DOMAIN" ]; then
    echo "📍 ngrok Domain: $NGROK_DOMAIN"
fi
if [ -n "$SERVEO_SUBDOMAIN" ]; then
    echo "📍 Serveo Subdomain: $SERVEO_SUBDOMAIN"
fi
if [ -n "$CLOUDFLARED_TUNNEL" ]; then
    echo "📍 Cloudflare Tunnel: $CLOUDFLARED_TUNNEL"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Function to start ngrok with fixed domain
start_ngrok() {
    # Authenticate ngrok if authtoken is provided
    if [ -n "$NGROK_AUTHTOKEN" ]; then
        echo "🔐 Authenticating ngrok..."
        ngrok config add-authtoken $NGROK_AUTHTOKEN
    fi
    
    if [ -n "$NGROK_DOMAIN" ]; then
        echo "🔗 Starting ngrok with fixed domain: $NGROK_DOMAIN"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "✅ Your FIXED webhook URL: https://$NGROK_DOMAIN/webhook"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        ngrok http --domain=$NGROK_DOMAIN $PORT
    else
        echo "🔗 Starting ngrok (random domain)..."
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "⚠️  Using random domain. Set NGROK_DOMAIN for fixed URL"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo ""
        ngrok http $PORT
    fi
}

# Function to start serveo with custom subdomain
start_serveo() {
    if [ -n "$SERVEO_SUBDOMAIN" ]; then
        echo "🔗 Starting serveo with custom subdomain: $SERVEO_SUBDOMAIN"
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "✅ Your FIXED webhook URL: https://$SERVEO_SUBDOMAIN.serveo.net/webhook"
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                echo ""
        ssh -R $SERVEO_SUBDOMAIN:80:localhost:$PORT serveo.net
            else
        echo "🔗 Starting serveo (random subdomain)..."
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "⚠️  Using random subdomain. Set SERVEO_SUBDOMAIN for fixed URL"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                echo ""
        ssh -R 80:localhost:$PORT serveo.net
    fi
}

# Function to start localtunnel
start_localtunnel() {
    echo "🔗 Starting localtunnel..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "⚠️  localtunnel uses random domains"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                echo ""
    lt --port $PORT
}

# Function to start cloudflared
start_cloudflared() {
    if [ -n "$CLOUDFLARED_TUNNEL" ]; then
        echo "🔗 Starting Cloudflare Tunnel: $CLOUDFLARED_TUNNEL"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "✅ Your FIXED webhook URL: https://$CLOUDFLARED_TUNNEL/webhook"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                echo ""
        cloudflared tunnel --url localhost:$PORT run $CLOUDFLARED_TUNNEL
    else
        echo "🔗 Starting Cloudflare Quick Tunnel..."
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "⚠️  Using quick tunnel (random domain)"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                echo ""
        cloudflared tunnel --url localhost:$PORT
    fi
}

# Main tunnel logic based on TUNNEL_METHOD
case "$TUNNEL_METHOD" in
    ngrok)
        if command -v ngrok &> /dev/null; then
            start_ngrok
        else
            echo "❌ ngrok not found. Install: https://ngrok.com/download"
            echo "App is still running on http://localhost:$PORT"
                wait $APP_PID
            fi
        ;;
    serveo)
        start_serveo
        ;;
    localtunnel)
        if command -v lt &> /dev/null; then
            start_localtunnel
    else
            echo "❌ localtunnel not found. Install: npm install -g localtunnel"
            echo "App is still running on http://localhost:$PORT"
            wait $APP_PID
        fi
        ;;
    cloudflared)
        if command -v cloudflared &> /dev/null; then
            start_cloudflared
        else
            echo "❌ cloudflared not found. Install: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/"
            echo "App is still running on http://localhost:$PORT"
            wait $APP_PID
        fi
        ;;
    auto)
        # Try ngrok first (best for fixed domains)
        if command -v ngrok &> /dev/null; then
            start_ngrok
        # Try cloudflared (also supports fixed domains)
        elif command -v cloudflared &> /dev/null; then
            start_cloudflared
        # Try serveo (supports custom subdomains)
        elif timeout 10 ssh -o ConnectTimeout=5 serveo.net exit 2>/dev/null; then
            start_serveo
        # Try localtunnel
        elif command -v lt &> /dev/null; then
            start_localtunnel
        else
            echo ""
            echo "❌ No tunnel tools available. Please install one of:"
            echo ""
            echo "  ngrok (recommended): https://ngrok.com/download"
            echo "  cloudflared: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/"
            echo "  localtunnel: npm install -g localtunnel"
            echo ""
            echo "Or manually expose with:"
            echo "  ssh -R 80:localhost:$PORT serveo.net"
            echo ""
            echo "App is still running on http://localhost:$PORT"
            echo "Press Ctrl+C to stop..."
            wait $APP_PID
        fi
        ;;
    *)
        echo "❌ Invalid TUNNEL_METHOD: $TUNNEL_METHOD"
        echo "Valid options: auto, ngrok, serveo, localtunnel, cloudflared"
        echo "App is still running on http://localhost:$PORT"
        wait $APP_PID
        ;;
esac

# If tunnel is closed, also stop the app
echo ""
echo "🛑 Stopping WhatsApp Bot..."
kill $APP_PID 2>/dev/null
echo "✅ Done!"

