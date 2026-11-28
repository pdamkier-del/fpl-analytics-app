# Research E · Dynamisk transferoptimering

[Matematisk formulering](MODEL.md) · [Resultater og TS v3-audit](REPORT.md) · [Forskningslog](LOG.md)

## Reproduktion

De seks små scenarietræer ligger i `cases.json` og bruger kun Pythons standardbibliotek. De modellerer 1–2 ejede spillere med de samme køb/salg- og transferregler. Pointtabellerne er allerede reduceret til den relevante startplads, så holdstørrelse, formation og kaptajnsvalg er ikke en del af de eksakte cases. Den historiske del bruger de arkiverede researchfunktioner til XI, kaptajn, autosubs og hits.

Alt køres fra denne mappe. Arkivet findes på den offentlige researchgren `ts-six-gw-validation-20261015` ved det pinnede commit. Brug Python 3.12 til den historiske del. Se `results/source-verification.json` for biblioteks­versioner og bytekontrol.

```bash
python -m unittest -v test_small
python small.py > results/exact.json

git clone --branch ts-six-gw-validation-20261015 --single-branch \
  https://github.com/pdamkier-del/fpl-analytics-app.git /tmp/fpl-e-source
git -C /tmp/fpl-e-source checkout --detach 6d875a65251fb62f691dc0386ea81aeb29d27c0f
python -m pip install pandas==2.2.3 numpy==2.3.5 scipy==1.17.0 scikit-learn==1.8.0 matplotlib==3.10.8
python -m unittest -v test_replay
python verify_source.py /tmp/fpl-e-source

for arm in tsv3 equal6 mpc10 terminal8; do
  OPENBLAS_NUM_THREADS=1 python replay.py /tmp/fpl-e-source results "$arm"
done
python audit_replay.py /tmp/fpl-e-source results
MPLCONFIGDIR=/tmp/fpl-e-mpl python plots.py results
```

`audit_replay.py` genafspiller de gennemførte transfers, efterprøver hits, bank, FT, trup og point samt scorer en særskilt TC-overlay. `results/historical-weekly.csv` indeholder kontrol mod at rulle fra den enkelte strategis egen starttilstand i runden. `results/historical-summary.json` og de fire rå armlogs indeholder point, hits, tid og parvise følsomhedsmål. Observeret køretid afhænger af maskine og samtidige processer. Både prognose- og resultathashes kan kontrolleres mod det pinnede arkiv. Den historiske TS-kontrol genbruger koden fra Research-grenen med de frosne konfigurationsværdier fra main.
