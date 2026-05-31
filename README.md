---
title: Multimodal RAG Agent
emoji: 📚
colorFrom: blue
colorTo: green
sdk: docker
app_port: 8000
pinned: false
---

# 📚 Multimodal RAG Agent

A production-grade Retrieval-Augmented Generation system that ingests PDFs,
images, and Office documents, then answers questions about them with citations —
or falls back to general knowledge when your documents aren't relevant.

**Live demo:** open the Space and start chatting. Upload a document in the
sidebar, or just ask anything in **General** mode.

## Features

- **Multimodal ingestion** — PDF, DOCX, PPTX, XLSX, images, and text. Embedded
  images are described by a vision model (Llama 4 Scout) so charts and figures
  are searchable too.
- **Hybrid retrieval** — dense vector search + BM25 keyword search fused with
  Reciprocal Rank Fusion, then re-ranked by a cross-encoder for precision.
- **HyDE** — generates a hypothetical answer and embeds *that* for stronger
  semantic recall.
- **Parent-document context** — retrieved chunks are expanded with their
  neighbours so the model sees full context while citations stay pinpoint.
- **Self-evaluation** — answers are scored on relevance / faithfulness /
  completeness, with automatic query reformulation + retry on low scores.
- **Three modes** — *Auto* (use docs when relevant, else general knowledge),
  *Documents* (grounded only), *General* (pure assistant). Ungrounded answers are
  clearly labelled.
- **Streaming** — answers stream token-by-token over SSE.
- **Background ingestion** — uploads return instantly and process in the
  background, with live status in the UI.

## Tech stack

| Layer | Tech |
|-------|------|
| API | FastAPI + uvicorn |
| LLM / VLM | Groq (Llama 3.1 8B + Llama 4 Scout) |
| Embeddings | `all-MiniLM-L6-v2` (local, CPU) |
| Reranker | `ms-marco-MiniLM-L-6-v2` cross-encoder (local, CPU) |
| Vector store | ChromaDB |
| Metadata | SQLite |
| Frontend | React + Vite + Tailwind |
| Packaging | Docker (multi-stage) |

## Configuration

Set **`GROQ_API_KEY`** as a Space secret (Settings → Variables and secrets).
Get a free key at <https://console.groq.com>.

## Run locally

```bash
docker compose up -d --build   # then open http://localhost:8000
```

See [DEPLOY.md](DEPLOY.md) for details.

> **Note:** on the free Space tier the filesystem is ephemeral, so uploaded
> documents reset when the Space restarts. The app and all features work fully
> within a session.
