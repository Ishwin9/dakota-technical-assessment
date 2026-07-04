import sys
from pathlib import Path

INGESTION_ROOT = Path(__file__).resolve().parents[2] / "ingestion"
if str(INGESTION_ROOT) not in sys.path:
    sys.path.insert(0, str(INGESTION_ROOT))
