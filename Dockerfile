FROM python:3.13-slim
# Copy the uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
# Set working directory
WORKDIR /app

# Install system dependencies including ngrok
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    openssh-client \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install ngrok
RUN curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc \
|  tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null \
&& echo "deb https://ngrok-agent.s3.amazonaws.com buster main" \
|  tee /etc/apt/sources.list.d/ngrok.list \
&&  apt update \
&&  apt install ngrok

# Copy application files
COPY . .

# Install Python dependencies using uv
RUN uv sync --frozen

# Make start script executable
RUN chmod +x start.sh

# Expose port
EXPOSE 7349

# Run the application with tunneling support
CMD ["./start.sh"]

