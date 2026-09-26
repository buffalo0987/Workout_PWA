FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy the entire project into the container
COPY . /app/

# Expose the port the server runs on
EXPOSE 8000

# Run the Python server
CMD ["python3", "backend/app/server.py"]
