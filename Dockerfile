# ==============================================================================
# Multi-Stage Containerfile / Dockerfile
# Encloses Angular Frontend & FastAPI Backend into a Single Production Container
# Optimized for maximum build speed, BuildKit caching, and minimal footprint
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Build Angular Frontend Static Assets
# ------------------------------------------------------------------------------
FROM node:22-alpine AS frontend-builder

WORKDIR /app/frontend

# Install dependencies using clean install with BuildKit npm cache mount.
# Keep optional dependencies: Angular's build toolchain uses platform-specific
# native packages on Linux.
COPY frontend/package*.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --prefer-offline --no-audit --no-fund

# Production build with a bounded Node heap sized for the 2 GB WSL2 VM this
# image is built in (see %USERPROFILE%\.wslconfig). Going higher risks an
# out-of-memory kill from the Linux OOM reaper during the Angular/esbuild
# compile. Analytics disabled via NG_CLI_ANALYTICS.
ENV NODE_ENV=production \
    NODE_OPTIONS=--max-old-space-size=1024 \
    NG_CLI_ANALYTICS=0

# Copy frontend source and build optimized distribution with Angular persistent disk cache
COPY frontend/ ./
RUN --mount=type=cache,target=/app/frontend/.angular/cache \
    npm run build

# ------------------------------------------------------------------------------
# Stage 2: Unified Python Runtime & Static Host
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

WORKDIR /app

# Optimize python output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install python backend dependencies with BuildKit pip wheel cache
COPY backend/requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Copy backend source code
COPY backend/ ./

# Copy compiled Angular distribution from Stage 1 into backend static directory
COPY --from=frontend-builder /app/frontend/dist/frontend/browser ./static

# Expose unified web application port
EXPOSE 8000

# Zero-overhead healthcheck using Python standard library (no curl/apt install needed)
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)" || exit 1

# Start FastAPI server serving both API and Frontend SPA
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
