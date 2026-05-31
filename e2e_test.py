"""
End-to-end test of the Multimodal RAG pipeline using FastAPI TestClient.
Runs the full app in-process: real parsing, real embeddings, real Groq calls.
"""
import io
import sys
from fastapi.testclient import TestClient
from app.main import app

# Use as context manager so the lifespan startup (embedding warmup) runs.
client = None  # set in __main__

SEP = "=" * 70


def banner(title):
    print(f"\n{SEP}\n  {title}\n{SEP}")


# A small synthetic "company doc" so we control the ground truth.
SAMPLE_DOC = """ACME ROBOTICS - INTERNAL PROJECT BRIEF

Project Atlas was led by Maria Chen, who joined ACME in 2021.
Atlas is a warehouse automation platform built with Python, ROS2, and PostgreSQL.
It reduced order-picking time by 38% across three distribution centers.

Project Borealis was led by James Okafor, who joined ACME in 2019.
Borealis is a computer-vision quality-inspection system using PyTorch and OpenCV.
It detects manufacturing defects with 96.4% accuracy on the production line.

The company headquarters is in Austin, Texas.
ACME Robotics was founded in 2015 by Dr. Elena Vasquez.
"""


def test_health():
    banner("TEST 1: Health check")
    r = client.get("/health")
    print("Status:", r.status_code)
    print("Body:", r.json())
    assert r.status_code == 200
    assert r.json()["groq_connected"] is True
    assert r.json()["embedding_model_loaded"] is True
    print("PASS: server healthy, Groq connected, embeddings loaded")


def test_upload():
    banner("TEST 2: Upload a .txt document")
    files = {"file": ("acme_brief.txt", io.BytesIO(SAMPLE_DOC.encode()), "text/plain")}
    r = client.post("/documents/upload", files=files)
    print("Status:", r.status_code)
    print("Body:", r.json())
    assert r.status_code == 200, f"Upload failed: {r.text}"
    body = r.json()
    assert body["chunk_count"] > 0
    print(f"PASS: ingested {body['chunk_count']} chunks, doc_id={body['doc_id']}")
    return body["doc_id"]


def test_list_documents():
    banner("TEST 3: List documents")
    r = client.get("/documents/")
    print("Status:", r.status_code)
    for d in r.json():
        print(f"  - {d['filename']} ({d['chunk_count']} chunks) id={d['doc_id']}")
    assert r.status_code == 200
    print("PASS: document list returned")


def test_single_query():
    banner("TEST 4: Single factual query")
    payload = {"question": "Who led Project Atlas and what technologies did it use?"}
    r = client.post("/query", json=payload)
    body = r.json()
    print("Answer:\n", body["answer"])
    print("\nStrategy:", body["strategy"])
    print("Confidence:", body["confidence"])
    print("Evaluation:", body["evaluation"])
    print("Session ID:", body["session_id"])
    assert r.status_code == 200
    assert "Maria Chen" in body["answer"], "Expected 'Maria Chen' in answer"
    assert body["session_id"], "Expected a session_id in response"
    print("PASS: correct answer with citations, session_id assigned")
    return body["session_id"]


def test_multiturn(session_id):
    banner("TEST 5: Multi-turn follow-up (pronoun resolution)")
    print(f"Reusing session_id: {session_id}")
    # 'she' should resolve to Maria Chen from the previous turn
    payload = {
        "session_id": session_id,
        "question": "What year did she join the company?",
    }
    r = client.post("/query", json=payload)
    body = r.json()
    print("Follow-up question: 'What year did she join the company?'")
    print("Answer:\n", body["answer"])
    print("Same session?", body["session_id"] == session_id)
    assert r.status_code == 200
    assert "2021" in body["answer"], "Expected '2021' (Maria Chen's join year)"
    assert body["session_id"] == session_id, "Session ID should be preserved"
    print("PASS: agent resolved 'she' -> Maria Chen and answered 2021 from history")


def test_dedup(doc_id):
    banner("TEST 6: Dedup — re-upload same file, expect existing record back")
    files = {"file": ("acme_brief.txt", io.BytesIO(SAMPLE_DOC.encode()), "text/plain")}
    r = client.post("/documents/upload", files=files)
    body = r.json()
    print("Status:", r.status_code)
    print("Body:", body)
    assert r.status_code == 200
    assert body["doc_id"] == doc_id, f"Expected same doc_id {doc_id}, got {body['doc_id']}"
    assert "already ingested" in body["message"]
    print("PASS: duplicate upload returned existing record without re-ingesting")


def test_doc_filter(doc_id):
    banner("TEST 6: Document filter (doc_ids)")
    payload = {
        "question": "Who founded the company and when?",
        "doc_ids": [doc_id],
    }
    r = client.post("/query", json=payload)
    body = r.json()
    print("Answer:\n", body["answer"])
    citing = {c["doc_id"] for c in body["citations"]}
    print("Cited doc_ids:", citing)
    assert r.status_code == 200
    assert citing <= {doc_id}, f"Filter leaked other docs: {citing}"
    print("PASS: results restricted to the requested document")


if __name__ == "__main__":
    try:
        with TestClient(app) as c:
            client = c
            test_health()
            doc_id = test_upload()
            test_list_documents()
            session_id = test_single_query()
            test_multiturn(session_id)
            test_dedup(doc_id)
            test_doc_filter(doc_id)
        banner("ALL TESTS PASSED")
    except AssertionError as e:
        print(f"\n!!! TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        import traceback
        print(f"\n!!! ERROR: {e}")
        traceback.print_exc()
        sys.exit(2)
