# ─────────────────────────────────────────────────────────────
# Stage 1 — build the React frontend into static assets
# ─────────────────────────────────────────────────────────────
FROM node:20-alpine AS frontend
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build          # → /frontend/dist


# ─────────────────────────────────────────────────────────────
# Stage 2 — Python backend that also serves the built frontend
# ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS backend

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/app/.cache/huggingface

WORKDIR /app

# Install CPU-only torch FIRST so sentence-transformers doesn't pull the
# multi-GB CUDA build. Keeps the image dramatically smaller.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the embedding + reranker models so the first request is fast
# and the container works without reaching Hugging Face at runtime.
RUN python -c "from sentence_transformers import SentenceTransformer, CrossEncoder; \
SentenceTransformer('all-MiniLM-L6-v2'); \
CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

# Models are now baked in — load them straight from the local cache at runtime
# instead of doing slow (and rate-limited) Hub metadata checks on every startup.
# Set AFTER the download above so the build still had network access.
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

# Application code + the frontend build from stage 1
COPY app/ ./app/
COPY --from=frontend /frontend/dist ./frontend/dist

# Hugging Face Spaces (and good practice) run the container as a non-root user
# with UID 1000. Create it and hand over ownership so the app can write its
# SQLite DB / Chroma store / uploads under /app/data and read the model cache.
RUN useradd -m -u 1000 user && chown -R user:user /app
ENV HOME=/home/user
USER user

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
