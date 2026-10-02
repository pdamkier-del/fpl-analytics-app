"""Run this project's no-argument assertion tests, including when pytest is absent."""
from pathlib import Path
import runpy
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
failures = []
passed = 0
for path in sorted((ROOT / 'tests').glob('test_*.py')):
    namespace = runpy.run_path(str(path))
    for name, function in namespace.items():
        if name.startswith('test_') and callable(function):
            try:
                function()
                passed += 1
                print('PASS', path.name, name)
            except Exception:
                failures.append((path.name, name))
                traceback.print_exc()
print(f'{passed} passed, {len(failures)} failed')
raise SystemExit(bool(failures))
