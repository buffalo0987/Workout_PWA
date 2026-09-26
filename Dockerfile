# ==============================================================================
# Stage 1: Build & Asset Preparation (Node stage for linting, frontend bundling)
# ==============================================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /build

# Copy frontend source assets
COPY public ./public
# If future builds introduce package.json/vite:
# COPY frontend/package*.json ./
# RUN npm ci && npm run build

# Verify PWA files are ready
RUN ls -la public

# ==============================================================================
# Stage 2: Minimal Production Runtime (Python Alpine)
# ==============================================================================
FROM python:3.12-alpine AS runner

WORKDIR /app

# Set production environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    DB_PATH=/app/data/workout_app.db

# Install runtime dependencies (sqlite, ca-certificates for HTTPS calls)
RUN apk add --no-cache ca-certificates tzdata sqlite

# Create application directories and unprivileged user
RUN mkdir -p /app/data /app/public && \
    addgroup -g 1001 -S appgroup && \
    adduser -u 1001 -S appuser -G appgroup

# Copy backend application source and database migration schema
COPY --chown=appuser:appgroup backend /app/backend
COPY --chown=appuser:appgroup src /app/src

# Copy static frontend & PWA assets from build stage
COPY --from=frontend-builder --chown=appuser:appgroup /build/public /app/public

# Set permissions for persistent database volume
RUN chown -R appuser:appgroup /app/data

# Switch to unprivileged user
USER appuser

EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:' + str(os.environ.get('PORT', 8000)) + '/health')" || exit 1

# Start the unified API and PWA server
CMD ["python3", "-m", "backend.app.server"]
