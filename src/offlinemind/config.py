"""Configuration settings for OfflineMind.
Loads from environment variables or .env file with safe production-ready defaults.
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Data and Storage Paths
DATA_DIR = Path(os.getenv("OFFLINEMIND_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = Path(os.getenv("OFFLINEMIND_DB_PATH", DATA_DIR / "offlinemind.db"))
BACKUP_DIR = Path(os.getenv("OFFLINEMIND_BACKUP_DIR", DATA_DIR / "backups"))
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

SEED_DATA_PATH = Path(os.getenv("OFFLINEMIND_SEED_DATA", DATA_DIR / "seed_knowledge.json"))

# Connectivity Monitor
CONNECTIVITY_CHECK_INTERVAL_SEC: float = float(os.getenv("OFFLINEMIND_CHECK_INTERVAL", "5.0"))
# Reliable ping endpoints (DNS IP:port or HTTP health)
DEFAULT_PING_HOSTS: List[str] = [
    "1.1.1.1:53",
    "8.8.8.8:53",
    "http://www.google.com",
]
CONNECTIVITY_PROBE_TIMEOUT_SEC: float = float(os.getenv("OFFLINEMIND_PROBE_TIMEOUT", "2.0"))

# Sync Engine Settings
AUTO_SYNC_ON_CONNECT: bool = os.getenv("OFFLINEMIND_AUTO_SYNC", "true").lower() in ("true", "1", "yes")
ALLOW_INSECURE_HTTP: bool = os.getenv("OFFLINEMIND_ALLOW_INSECURE_HTTP", "true").lower() in ("true", "1", "yes")
SYNC_TIMEOUT_SEC: float = float(os.getenv("OFFLINEMIND_SYNC_TIMEOUT", "10.0"))
MAX_BACKUP_RETENTION: int = int(os.getenv("OFFLINEMIND_MAX_BACKUPS", "10"))

# LLM / Model Provider Settings
MODEL_PROVIDER: str = os.getenv("MODEL_PROVIDER", "ollama")
MODEL_NAME: str = os.getenv("MODEL_NAME", os.getenv("OLLAMA_MODEL", "llama3.2:3b"))
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str = MODEL_NAME
OLLAMA_TIMEOUT_SEC: float = float(os.getenv("OLLAMA_TIMEOUT", "60.0"))

# Mock Server Settings (for local demo & test)
MOCK_SERVER_HOST: str = os.getenv("MOCK_SERVER_HOST", "127.0.0.1")
MOCK_SERVER_PORT: int = int(os.getenv("MOCK_SERVER_PORT", "8765"))
MOCK_SERVER_URL: str = f"http://{MOCK_SERVER_HOST}:{MOCK_SERVER_PORT}"

# Logging
LOG_LEVEL: str = os.getenv("OFFLINEMIND_LOG_LEVEL", "INFO")
LOG_FILE: Path = DATA_DIR / "offlinemind.log"
