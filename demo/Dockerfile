# Dockerfile for HF Spaces - FastHTML Demo App
# State Swap Explorer: Interactive visualization of circuit steering experiments

FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY static/ ./static/
COPY main.py .

# Copy data (bundled with the app)
# Note: Data is copied to /app/data/ and loader.py expects ../output/usa_states_batch/
# So we create symlink or adjust path
COPY data/ ./data/

# Expose FastHTML port (HF Spaces expects 7860)
EXPOSE 7860

# Health check
HEALTHCHECK CMD curl --fail http://localhost:7860/ || exit 1

# Run FastHTML app
CMD ["python", "main.py", "--port", "7860"]



