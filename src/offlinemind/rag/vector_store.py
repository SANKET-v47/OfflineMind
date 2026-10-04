"""SQLite-backed vector store for local document RAG."""

from __future__ import annotations
import contextlib
import json
import logging
import sqlite3
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any

from offlinemind.rag.document_loader import DocumentLoader
from offlinemind.rag.chunker import TextChunker
from offlinemind.rag.embeddings import (
    EmbeddingProvider,
    LocalHashEmbeddingProvider,
    cosine_similarity,
)

logger = logging.getLogger(__name__)


class RAGSearchResult:
    """Retrieved document chunk with similarity score and metadata."""

    def __init__(
        self,
        chunk_id: str,
        doc_id: str,
        doc_name: str,
        text: str,
        score: float,
        chunk_index: int,
        metadata: Dict[str, Any],
    ):
        self.chunk_id = chunk_id
        self.doc_id = doc_id
        self.doc_name = doc_name
        self.text = text
        self.score = score
        self.chunk_index = chunk_index
        self.metadata = metadata

    def __repr__(self) -> str:
        return f"<RAGSearchResult doc='{self.doc_name}' score={self.score:.3f}>"


class LocalVectorStore:
    """Persistent embedded vector database using SQLite and dense embeddings."""

    def __init__(
        self,
        db_path: Path | str,
        embedding_provider: Optional[EmbeddingProvider] = None,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
    ):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.embedder = embedding_provider or LocalHashEmbeddingProvider()
        self.chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self._init_tables()

    @contextlib.contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def close(self) -> None:
        """Closes any resources."""
        pass

    def _init_tables(self) -> None:
        with self._get_conn() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS rag_documents (
                doc_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                path TEXT NOT NULL,
                extension TEXT,
                char_count INTEGER,
                chunk_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS rag_chunks (
                chunk_id TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL,
                doc_name TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                text TEXT NOT NULL,
                embedding TEXT NOT NULL,
                metadata TEXT,
                FOREIGN KEY (doc_id) REFERENCES rag_documents(doc_id) ON DELETE CASCADE
            );
            """)

    def add_document(self, file_path: Path | str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Loads, chunks, embeds, and stores a document in the vector store."""
        loaded = DocumentLoader.load(file_path)
        meta = metadata or {}
        meta.update({
            "source_path": loaded["file_path"],
            "file_name": loaded["file_name"],
            "extension": loaded["extension"],
        })

        chunks = self.chunker.chunk_text(loaded["text"], metadata=meta)
        if not chunks:
            raise ValueError(f"No extractable text found in {file_path}")

        doc_id = str(uuid.uuid4())
        chunk_texts = [c["text"] for c in chunks]
        embeddings = self.embedder.embed_batch(chunk_texts)

        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO rag_documents (doc_id, name, path, extension, char_count, chunk_count)
                   VALUES (?, ?, ?, ?, ?, ?);""",
                (doc_id, loaded["file_name"], loaded["file_path"], loaded["extension"], loaded["char_count"], len(chunks)),
            )

            for i, chunk in enumerate(chunks):
                chunk_id = f"{doc_id}_{i}"
                conn.execute(
                    """INSERT INTO rag_chunks (chunk_id, doc_id, doc_name, chunk_index, text, embedding, metadata)
                       VALUES (?, ?, ?, ?, ?, ?, ?);""",
                    (
                        chunk_id,
                        doc_id,
                        loaded["file_name"],
                        i,
                        chunk["text"],
                        json.dumps(embeddings[i]),
                        json.dumps(chunk),
                    ),
                )

        logger.info("Ingested document '%s' with %d chunks into RAG store.", loaded["file_name"], len(chunks))
        return doc_id

    def search(self, query: str, top_k: int = 3) -> List[RAGSearchResult]:
        """Performs vector similarity search across all stored document chunks."""
        q_emb = self.embedder.embed_text(query)
        if not q_emb:
            return []

        with self._get_conn() as conn:
            rows = conn.execute("SELECT chunk_id, doc_id, doc_name, chunk_index, text, embedding, metadata FROM rag_chunks;").fetchall()

        scored: List[RAGSearchResult] = []
        for r in rows:
            try:
                emb = json.loads(r["embedding"])
                score = cosine_similarity(q_emb, emb)
                meta = json.loads(r["metadata"]) if r["metadata"] else {}
                scored.append(
                    RAGSearchResult(
                        chunk_id=r["chunk_id"],
                        doc_id=r["doc_id"],
                        doc_name=r["doc_name"],
                        text=r["text"],
                        score=score,
                        chunk_index=r["chunk_index"],
                        metadata=meta,
                    )
                )
            except Exception as e:
                logger.debug("Error computing similarity for chunk %s: %s", r["chunk_id"], e)

        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:top_k]

    def list_documents(self) -> List[Dict[str, Any]]:
        """Lists all ingested documents."""
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM rag_documents ORDER BY created_at DESC;").fetchall()
            return [dict(r) for r in rows]

    def delete_document(self, doc_id: str) -> bool:
        """Deletes a document and its associated chunks."""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM rag_chunks WHERE doc_id = ?;", (doc_id,))
            cursor = conn.execute("DELETE FROM rag_documents WHERE doc_id = ?;", (doc_id,))
            return cursor.rowcount > 0

    def clear_all(self) -> None:
        """Wipes all documents and chunks from the store."""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM rag_chunks;")
            conn.execute("DELETE FROM rag_documents;")
