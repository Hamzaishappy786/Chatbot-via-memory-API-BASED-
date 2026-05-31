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

# Application code + the frontend build from stage 1
COPY app/ ./app/
COPY --from=frontend /frontend/dist ./frontend/dist

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
