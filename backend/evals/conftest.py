import sys
from pathlib import Path

# Permite `from app...` al correr pytest desde la raíz del repo o desde backend/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
