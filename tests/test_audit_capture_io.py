import gzip
import pytest
from audit_capture_io import checked_records,write_records


def test_atomic_capture_has_reproducible_complete_gzip_trailer(tmp_path):
    a=tmp_path/'a.jsonl.gz';b=tmp_path/'b.jsonl.gz';rows=[{'fixture':'source-fixture','value':.123456789}]
    write_records(a,rows);write_records(b,rows)
    assert a.read_bytes()==b.read_bytes()
    assert checked_records(a)==rows


def test_truncated_capture_is_rejected_before_simulation(tmp_path):
    p=tmp_path/'capture.gz';write_records(p,[{'fixture':i} for i in range(3)])
    p.write_bytes(p.read_bytes()[:-8])
    with pytest.raises(EOFError):checked_records(p)


def test_failed_write_preserves_existing_valid_capture(tmp_path):
    p=tmp_path/'capture.gz';write_records(p,[{'value':1}]);before=p.read_bytes()
    with pytest.raises(AttributeError):write_records(p,[{'value':object()}])
    assert p.read_bytes()==before and checked_records(p)==[{'value':1}]
    assert not p.with_name(p.name+'.tmp').exists()


def test_atomic_csv_preserves_previous_on_failed_serialization(tmp_path):
    import pandas as pd
    from audit_capture_io import write_frame
    p=tmp_path/'frame.csv.gz'
    frame=pd.DataFrame({'player':['verified-player'],'minutes':[79]})
    write_frame(p,frame);before=p.read_bytes()
    write_frame(p,frame)
    assert p.read_bytes()==before
    assert pd.read_csv(p).to_dict('list')==frame.to_dict('list')
    class Broken:
        def to_csv(self,stream,index):
            stream.write('partial')
            raise ValueError('interrupted serializer')
    with pytest.raises(ValueError):write_frame(p,Broken())
    assert p.read_bytes()==before
    assert not p.with_name(p.name+'.tmp').exists()
