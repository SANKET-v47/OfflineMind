"""Multi-format document text extractor supporting TXT, Markdown, Code, PDF, and DOCX."""

from __future__ import annotations
import logging
from pathlib import Path
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class DocumentLoader:
    """Extracts raw text and metadata from local files."""

    @classmethod
    def load(cls, file_path: Path | str) -> Dict[str, Any]:
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        ext = path.suffix.lower()
        if ext in (".txt", ".md", ".py", ".json", ".csv", ".yaml", ".yml", ".html", ".rst", ".sql"):
            text = cls._load_text(path)
        elif ext == ".pdf":
            text = cls._load_pdf(path)
        elif ext == ".docx":
            text = cls._load_docx(path)
        else:
            # Attempt generic UTF-8 text read
            try:
                text = cls._load_text(path)
            except Exception:
                raise ValueError(f"Unsupported file format: {ext}")

        return {
            "file_path": str(path),
            "file_name": path.name,
            "extension": ext,
            "text": text,
            "char_count": len(text),
        }

    @staticmethod
    def _load_text(path: Path) -> str:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    @staticmethod
    def _load_pdf(path: Path) -> str:
        # Try pypdf or PyPDF2 if installed
        try:
            import pypdf
            reader = pypdf.PdfReader(str(path))
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n\n".join(pages)
        except ImportError:
            pass

        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(str(path))
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n\n".join(pages)
        except ImportError:
            pass

        # Lightweight fallback: extract ASCII text sequences from PDF binary
        with open(path, "rb") as f:
            content = f.read()
        import re
        text_blocks = re.findall(rb"\(([\w\s.,!?-]{4,})\)", content)
        if text_blocks:
            return "\n".join(b.decode("latin-1", errors="ignore") for b in text_blocks)
        return f"[PDF document: {path.name} (Install pypdf for high-fidelity extraction)]"

    @staticmethod
    def _load_docx(path: Path) -> str:
        try:
            import docx
            doc = docx.Document(str(path))
            return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        except ImportError:
            pass

        # DOCX is a zip file containing word/document.xml
        try:
            import zipfile
            import xml.etree.ElementTree as ET
            with zipfile.ZipFile(str(path), "r") as z:
                xml_content = z.read("word/document.xml")
            root = ET.fromstring(xml_content)
            # Find all text elements
            texts = [node.text for node in root.iter() if node.text]
            return " ".join(texts)
        except Exception as e:
            logger.warning("DOCX extraction fallback failed: %s", e)
            return f"[DOCX document: {path.name}]"
