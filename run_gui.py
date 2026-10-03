"""OfflineMind Native GUI Launcher."""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "src"))
sys.path.insert(0, str(BASE_DIR))

from offlinemind.ui.gui_app import main

if __name__ == "__main__":
    main()
