"""Use the same maintained research helpers in local and CI test runs."""
from pathlib import Path
import sys

# Several maintained regression cases exercise the offline research scripts.
# Keep their legacy sibling imports available without requiring a different
# PYTHONPATH in every test runner; this does not import or activate a model.
analysis = str(Path(__file__).resolve().parents[1] / 'analysis')
if analysis not in sys.path:
    sys.path.append(analysis)
