# ──────────────────────────────────────────────
# Base image with Playwright browsers pre-installed
# ──────────────────────────────────────────────
FROM mcr.microsoft.com/playwright/python:v1.52.0-noble

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Ensure data and logs directories exist
RUN mkdir -p /app/data /app/logs

# Run the job hunter
CMD ["python", "-m", "src"]
