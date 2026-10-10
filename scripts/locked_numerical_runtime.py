#!/usr/bin/env python3
"""Launch unchanged model scripts under a fixed numerical runtime.

Runtime controls are applied before NumPy/SciPy import. No fitted coefficients,
optimizer tolerances, observations or seeds in the original model are changed.
"""
import os, sys
from pathlib import Path
ENV={
    'PYTHONHASHSEED':'0','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1',
    'MKL_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1','OPENBLAS_CORETYPE':'NEHALEM',
    'NPY_DISABLE_CPU_FEATURES':'AVX,AVX2,FMA3,AVX512F,AVX512CD,AVX512_SKX,AVX512_CLX,AVX512_CNL,AVX512_ICL',
    'TZ':'UTC',
}
def main():
    if len(sys.argv)<2:raise SystemExit('Usage: locked_numerical_runtime.py SCRIPT [ARGS...]')
    script=Path(sys.argv[1]).resolve();root=Path(__file__).resolve().parents[1]
    if root not in script.parents or script.suffix!='.py':raise SystemExit('Only repository Python scripts are allowed')
    env=dict(os.environ);env.update(ENV)
    os.execve(sys.executable,[sys.executable,str(script),*sys.argv[2:]],env)
if __name__=='__main__':main()
