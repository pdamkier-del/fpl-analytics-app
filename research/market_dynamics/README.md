# FPL Research A · Market Dynamics

[Resultater og konklusion](REPORT.md) · [Dataaudit](DATA_AUDIT.md) · [Matematik](METHOD.md) · [Forskningslogbog](LOG.md) · [Analyseprotokol](PROTOCOL.md)

Undersøgelsen afprøver prisforudsigelse, markedets reaktion på spiludfald og, på et mindre datagrundlag, markedets informationsværdi for MM/PM. Alle programmer ligger i denne forskningsmappe og læser fra separat rådatacache. Reproducerede CSV-, JSON- og PNG-resultater ligger i [results/](results/).

## Reproduktion

Kør fra repository-roden med Python 3.12, git og GitHub CLI. Tillad netværksadgang til GitHub. Rådata fylder omkring 200 MB med git-objekter og arkiver. Beregningen bruger to BLAS-tråde og kan tage flere minutter. Resultatfilerne er aggregerede forskningsudtræk. Rådata caches separat.

```sh
python -m venv /tmp/fpl-market-env
. /tmp/fpl-market-env/bin/activate
python -m pip install -r research/market_dynamics/requirements.txt pytest==8.4.2
python research/market_dynamics/fetch.py /tmp/fpl-market-inputs
MPLCONFIGDIR=/tmp/fpl-market-mpl OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 \
  python research/market_dynamics/run.py \
  --inputs /tmp/fpl-market-inputs --output /tmp/fpl-market-results
OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 python -m pytest -q research/market_dynamics/test_market.py
python research/tools/verify_current.py
```

Checksummer, originalt observationstidspunkt, deadlines og coverage ligger i [data_audit.json](results/data_audit.json). For de eksterne kilder er revisionerne låst i [fetch.py](fetch.py). [release-tags.txt](release-tags.txt) fastholder de 10 release-vintages i auditten. Ved genkørsel kan aggregerede numeriske resultater variere ved ændret Python- eller numerikstack. Brug friske input- og outputmapper ved uafhængig reproduktion.

## Resultatfiler

| Fil | Indhold |
| --- | --- |
| [price_metrics.csv](results/price_metrics.csv) | Syv arme, fire horisonter, fælles evalueringsrækker, samlet og pr. sæson med tidsblokintervaller |
| [calibration.csv](results/calibration.csv) | Frekvenser og antal pr. klasse, model og sandsynlighedsinterval |
| [dynamics.json](results/dynamics.json) | Forskudte rangkorrelationer, koncentration, feedback og matchede kohorter |
| [sports.json](results/sports.json) | Parret MAE, RMSE og blokintervaller for point og minutter over historisk sportslig reference |
| [frozen_mm_pm.csv](results/frozen_mm_pm.csv) | Diagnose pr. GW mod uændret, publiceret MM og PM |
| [replay_summary.csv](results/replay_summary.csv) · [replay_weeks.csv](results/replay_weeks.csv) | Faktisk score og transfer-/budgetforløb i samme afgrænsede politik |
| [kalibrering.png](results/kalibrering.png) · [lead-lag.png](results/lead-lag.png) · [saesonpoint.png](results/saesonpoint.png) | Figurer fra de samme aggregerede resultater |
