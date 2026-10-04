"""Unit tests for Phase 4: Local RAG, Document Extraction, and Vector Search."""

import tempfile
from pathlib import Path
import pytest

from offlinemind.rag.document_loader import DocumentLoader
from offlinemind.rag.chunker import TextChunker
from offlinemind.rag.embeddings import LocalHashEmbeddingProvider, cosine_similarity
from offlinemind.rag.vector_store import LocalVectorStore


def test_chunker_sliding_window():
    chunker = TextChunker(chunk_size=100, chunk_overlap=20)
    sample_text = (
        "Artificial intelligence is transforming industries. "
        "Offline models allow private, secure computation. "
        "Local RAG retrieves information from user files without internet access."
    )
    chunks = chunker.chunk_text(sample_text)
    assert len(chunks) >= 2
    for c in chunks:
        assert len(c["text"]) > 0


def test_embeddings_and_cosine_similarity():
    embedder = LocalHashEmbeddingProvider(dimension=64)
    v1 = embedder.embed_text("artificial intelligence and machine learning")
    v2 = embedder.embed_text("machine learning and neural networks")
    v3 = embedder.embed_text("chocolate cake recipe baking instructions")

    sim_related = cosine_similarity(v1, v2)
    sim_unrelated = cosine_similarity(v1, v3)

    assert sim_related > sim_unrelated
    assert -1.0 <= sim_related <= 1.0


def test_vector_store_ingestion_and_search():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_rag.db"
        doc_file = Path(tmpdir) / "ai_safety.md"
        doc_file.write_text(
            "# AI Safety Guidelines\n\n"
            "Local AI systems protect user privacy by running models on-device.\n\n"
            "Quantum cryptography provides theoretical resistance against quantum computer decryption attacks.",
            encoding="utf-8"
        )

        store = LocalVectorStore(db_path=db_path)
        doc_id = store.add_document(doc_file)
        assert doc_id is not None

        docs = store.list_documents()
        assert len(docs) == 1
        assert docs[0]["name"] == "ai_safety.md"

        # Search for quantum cryptography
        results = store.search("quantum computer decryption", top_k=2)
        assert len(results) >= 1
        assert "quantum" in results[0].text.lower()

        # Delete document
        deleted = store.delete_document(doc_id)
        assert deleted is True
        assert len(store.list_documents()) == 0
