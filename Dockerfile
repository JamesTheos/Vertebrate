# Use a lightweight Python base image
FROM python:3.11-slim

# Create app directory
WORKDIR /app

# Install system deps if needed (none for now)
# Copy requirements and install
COPY Requirements.txt ./
RUN pip install --no-cache-dir -r Requirements.txt

# Copy application code
COPY code ./code

# Set working directory to the app code
WORKDIR /app/code

# Environment
ENV PYTHONUNBUFFERED=1

# Expose Flask port used by run.py
EXPOSE 5001

# Default command
CMD ["python", "run.py"]
