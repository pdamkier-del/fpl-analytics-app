FROM python:3.12-slim
WORKDIR /app
COPY requirements-model-checkpoint.txt .
RUN pip install --no-cache-dir -r requirements-model-checkpoint.txt Flask==3.1.2 gunicorn==23.0.0
COPY src src
COPY scripts scripts
COPY service service
COPY analysis/results/current-season-b-backtest-20261027/gw*.json.gz analysis/results/current-season-b-backtest-20261027/
ENV PORT=10000 PYTHONHASHSEED=0 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 OPENBLAS_CORETYPE=NEHALEM NPY_DISABLE_CPU_FEATURES=AVX,AVX2,FMA3,AVX512F,AVX512CD,AVX512_SKX,AVX512_CLX,AVX512_CNL,AVX512_ICL TZ=UTC
CMD gunicorn service.app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 60 --access-logfile /dev/null
