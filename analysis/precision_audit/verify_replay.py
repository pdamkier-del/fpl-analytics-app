"""Compare a separately rerun subset with sealed audit draws, by full identity."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

def main():
    p=argparse.ArgumentParser();p.add_argument('--actual',type=Path,required=True);p.add_argument('--reference',type=Path,required=True);a=p.parse_args();keys=['season','fixture_uuid','player_uuid','draws','seed','mask'];x=pd.read_csv(a.actual,low_memory=False);y=pd.read_csv(a.reference,low_memory=False);z=x.merge(y,on=keys,suffixes=('_new','_saved'),validate='one_to_one')
    assert len(z)==len(x)>0,'Missing reference rows'
    for c in ['points','minutes','goals','assists','clean_sheet','bonus','p_goal','p_assist','p60','p90']:
        assert np.allclose(z[c+'_new'],z[c+'_saved'],rtol=0,atol=1e-12),c
    print('Independent replay matches saved draws:',len(z),'rows')
if __name__=='__main__':main()
