import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from individual_mm_evidence import encode_frame,load_frame

def test_evidence_roundtrip_preserves_prediction_bits_and_missing_categories():
 f=pd.DataFrame(dict(player=['a','b',None,'a'],mode=['baseline','role','role','baseline'],p=[.123456789012345,.5,0.,1.],minutes=[90,0,13,88]))
 g=load_frame(encode_frame(f))
 pd.testing.assert_frame_equal(f,g,check_dtype=False,check_exact=True)
