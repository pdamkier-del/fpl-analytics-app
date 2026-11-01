from pathlib import Path
import shutil
import pytest
from check_locked_gk_default import REVIEWED,require_reviewed_default_sources


def test_reviewed_default_source_pins_match():
    require_reviewed_default_sources()


def test_arbitrary_default_source_edits_fail_closed(tmp_path):
    root=Path(__file__).resolve().parents[1]
    for name in REVIEWED:
        target=tmp_path/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(root/name,target)
    require_reviewed_default_sources(tmp_path)
    point=tmp_path/'src/fpl_v1_1_model/point_accounting.py'
    point.write_text(point.read_text()+'\n# unexpected change\n')
    with pytest.raises(AssertionError,match='Unreviewed default source change'):
        require_reviewed_default_sources(tmp_path)
