#!/bin/bash
# Quick start script for WhatsApp Bot with serveo.net tunnel

# echo "🤖 Starting WhatsApp Bot Setup..."

# # Check if .env exists
# if [ ! -f .env ]; then
#     echo "⚠️  .env file not found!"
#     if [ -f env.example ]; then
#         echo "📝 Creating .env from env.example..."
#         cp env.example .env
#         echo "⚠️  Please edit .env file with your credentials before running the bot"
#         echo "   Required: WHATSAPP_TOKEN, WHATSAPP_PHONE_ID, OPENAI_API_KEY"
#         exit 1
#     else
#         echo "❌ env.example not found. Please create .env file manually."
#         echo "   See README.md for required environment variables."
#         exit 1
#     fi
# fi

# # Install dependencies
# echo "📦 Installing dependencies..."
# uv sync

# Start the FastAPI application in the background
echo "🚀 Starting WhatsApp Bot on port 8000..."
uv run uvicorn app.main:app --host 0.0.0.0 --port 7349 &
APP_PID=$!

# Wait for the app to start
echo "⏳ Waiting for server to start..."
sleep 3

# Check if app is running
if ! kill -0 $APP_PID 2>/dev/null; then
    echo "❌ Failed to start the application"
    exit 1
fi

echo "✅ Application is running on http://localhost:7349"
echo "📚 API Docs: http://localhost:7349/docs"
echo ""
echo "🌐 Creating public tunnel..."
echo "   This will expose your local server to the internet for WhatsApp webhook"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Your public URL will appear below - use it for WhatsApp webhook!"
echo "Example: https://your-name.serveo.net/webhook"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Try serveo.net first
timeout 10 ssh -R 80:localhost:7349 serveo.net 2>/dev/null
SERVEO_EXIT=$?

# If serveo.net fails, try localtunnel (lt)
if [ $SERVEO_EXIT -ne 0 ]; then
    echo ""
    echo "⚠️  serveo.net connection failed"
    echo "🔄 Falling back to localtunnel..."
    echo ""
    
    # Check if localtunnel is installed
    if command -v lt &> /dev/null; then
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "Starting localtunnel..."
        echo "Your webhook URL: https://YOUR-URL.loca.lt/webhook"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        lt --port 7349
        LT_EXIT=$?
        
        # If localtunnel fails, fall back to ngrok
        if [ $LT_EXIT -ne 0 ]; then
            echo ""
            echo "⚠️  localtunnel connection failed"
            echo "🔄 Falling back to ngrok..."
            echo ""
            
            # Check if ngrok is installed
            if command -v ngrok &> /dev/null; then
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                echo "Starting ngrok tunnel..."
                echo "Your webhook URL: https://YOUR-URL.ngrok.io/webhook"
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                echo ""
                ngrok http 7349
            else
                echo ""
                echo "❌ All tunnel options failed. Please install one of:"
                echo ""
                echo "  localtunnel: npm install -g localtunnel"
                echo "  ngrok: https://ngrok.com/download"
                echo ""
                echo "Or manually expose with:"
                echo "  ssh -R 80:localhost:7349 serveo.net"
                echo ""
                echo "App is still running on http://localhost:7349"
                echo "Press Ctrl+C to stop..."
                wait $APP_PID
            fi
        fi
    else
        echo "⚠️  localtunnel not found, trying ngrok..."
        echo ""
        
        # Check if ngrok is installed
        if command -v ngrok &> /dev/null; then
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "Starting ngrok tunnel..."
            echo "Your webhook URL: https://YOUR-URL.ngrok.io/webhook"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo ""
            ngrok http 7349
        else
            echo ""
            echo "❌ No tunnel tools available. Please install one of:"
            echo ""
            echo "  localtunnel: npm install -g localtunnel"
            echo "  ngrok: https://ngrok.com/download"
            echo ""
            echo "Or manually expose with:"
            echo "  ssh -R 80:localhost:7349 serveo.net"
            echo ""
            echo "App is still running on http://localhost:7349"
            echo "Press Ctrl+C to stop..."
            wait $APP_PID
        fi
    fi
fi

# If tunnel is closed, also stop the app
echo ""
echo "🛑 Stopping WhatsApp Bot..."
kill $APP_PID 2>/dev/null
echo "✅ Done!"

