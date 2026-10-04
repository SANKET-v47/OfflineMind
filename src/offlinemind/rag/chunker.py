"""Text chunker with overlapping sliding window and semantic boundary awareness."""

from __future__ import annotations
import re
from typing import List, Dict, Any


class TextChunker:
    """Splits long text into contextual chunks suitable for vector retrieval."""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 100):
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be strictly less than chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(self, text: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Splits text into chunks preserving sentence/paragraph boundaries."""
        clean_text = text.strip()
        if not clean_text:
            return []

        # Split into paragraphs first
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", clean_text) if p.strip()]
        chunks: List[Dict[str, Any]] = []

        current_chunk = ""
        chunk_index = 0

        for p in paragraphs:
            # If paragraph itself is too large, split by sentences
            if len(p) > self.chunk_size:
                sentences = re.split(r"(?<=[.!?])\s+", p)
                for s in sentences:
                    if len(current_chunk) + len(s) + 1 <= self.chunk_size:
                        current_chunk = f"{current_chunk} {s}".strip()
                    else:
                        if current_chunk:
                            chunks.append(self._create_chunk(current_chunk, chunk_index, metadata))
                            chunk_index += 1
                            # Retain overlap from end of current chunk
                            current_chunk = current_chunk[-self.chunk_overlap:] + " " + s
                        else:
                            # Force cut if a single sentence is larger than chunk_size
                            chunks.append(self._create_chunk(s[:self.chunk_size], chunk_index, metadata))
                            chunk_index += 1
                            current_chunk = s[self.chunk_size - self.chunk_overlap:]
            else:
                if len(current_chunk) + len(p) + 2 <= self.chunk_size:
                    current_chunk = f"{current_chunk}\n\n{p}".strip()
                else:
                    if current_chunk:
                        chunks.append(self._create_chunk(current_chunk, chunk_index, metadata))
                        chunk_index += 1
                        current_chunk = current_chunk[-self.chunk_overlap:] + "\n\n" + p
                    else:
                        current_chunk = p

        if current_chunk.strip():
            chunks.append(self._create_chunk(current_chunk.strip(), chunk_index, metadata))

        return chunks

    def _create_chunk(self, text: str, index: int, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        chunk_data = {
            "chunk_id": f"chunk_{index}",
            "chunk_index": index,
            "text": text.strip(),
            "char_count": len(text.strip()),
        }
        if metadata:
            chunk_data.update(metadata)
        return chunk_data
