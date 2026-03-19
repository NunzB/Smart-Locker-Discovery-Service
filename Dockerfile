FROM python:3.11-slim

# Install socat which is necessary for the serial bridge
RUN apt-get update && apt-get install -y socat git && rm -rf /var/lib/apt/lists/*

WORKDIR /

# Copy the FastAPI source code
COPY src/ ./src/

# Copy python dependencies
COPY requirements.txt .

# Copy aux files for bridge client authentication
COPY aux/ ./aux/

# Copy the startup scripts
COPY start_service.sh .
COPY start_api_repl.sh .

RUN chmod +x start_service.sh
RUN chmod +x start_api_repl.sh

# Expose FastAPI's default port
EXPOSE 8000

# Set entrypoint to our custom unified startup script
CMD ["./start_service.sh"]
