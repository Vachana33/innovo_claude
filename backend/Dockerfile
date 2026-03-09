
# Use Python 3.10 slim image for smaller size
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy requirements file first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend application code
COPY . .

# Expose port 8000
EXPOSE 8000

# Create startup script that runs migrations then starts server
RUN echo '#!/bin/sh\n\
set -e\n\
echo "Running database migrations..."\n\
alembic upgrade head\n\
echo "Starting server..."\n\
exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}\n\
' > /app/start.sh && chmod +x /app/start.sh

# Run migrations and start server
CMD ["/app/start.sh"]