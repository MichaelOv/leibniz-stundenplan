import os
import sys
from pathlib import Path

# fetch_and_build.py liest ISERV_USER/PASS beim Import und beendet sich sonst.
os.environ.setdefault("ISERV_USER", "test")
os.environ.setdefault("ISERV_PASS", "test")

# scripts/ importierbar machen (kein Package)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
