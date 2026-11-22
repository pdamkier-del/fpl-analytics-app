from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'integration/research-data'),str(ROOT/'tests/research_data')]
