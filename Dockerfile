# ==============================================================================
# Stage 1: Build React 18+ TypeScript SPA
# ==============================================================================
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install

COPY frontend/ ./
RUN npm run build

# ==============================================================================
# Stage 2: Lean Python 3.11 Runtime with CPU PyTorch
# ==============================================================================
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app" \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    TORCH_NUM_THREADS=1 \
    PORT=8000

WORKDIR /app

# Install minimal OS runtime packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch first (saves ~2GB CUDA binaries)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install remaining Python production dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Create unprivileged application user
RUN useradd -u 1000 -m appuser && \
    mkdir -p /app/models /app/data /app/frontend/dist && \
    chown -R appuser:appuser /app

# Copy application codebases
COPY --chown=appuser:appuser ml /app/ml
COPY --chown=appuser:appuser backend /app/backend

# Copy production model artifacts
COPY --chown=appuser:appuser models/bundle.joblib /app/models/bundle.joblib
COPY --chown=appuser:appuser models/lstm_fcn.pt /app/models/lstm_fcn.pt
COPY --chown=appuser:appuser models/autoencoder.pt /app/models/autoencoder.pt
COPY --chown=appuser:appuser models/replay_sample.parquet /app/models/replay_sample.parquet
COPY --chown=appuser:appuser models/metrics.json /app/models/metrics.json

# Copy compiled React frontend assets from Stage 1
COPY --from=frontend-builder --chown=appuser:appuser /app/frontend/dist /app/frontend/dist

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
