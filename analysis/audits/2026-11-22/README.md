# FPL — Comprehensive Model Performance Audit

22. november 2026 · separat evidens-PR · ingen app-/modelændring.

## Rapporter

- [Fase 1: eksisterende forskning og tests](reports/00-existing-research-map.md)
- [A. Model Performance Report](reports/A-model-performance-report.md)
- [B. Error Atlas](reports/B-error-atlas.md)
- [C. External Benchmark Report](reports/C-external-benchmark-report.md)
- [D. Data Gap Report](reports/D-data-gap-report.md)
- [E. Improvement Roadmap](reports/E-improvement-roadmap.md)

## Reproduktion

Fra repositoryroden, Python 3.12:

```sh
python -m venv /tmp/fpl-audit-venv
/tmp/fpl-audit-venv/bin/pip install -r analysis/audits/2026-11-22/requirements-audit.txt
OPENBLAS_NUM_THREADS=1 /tmp/fpl-audit-venv/bin/python analysis/audits/2026-11-22/code/run_audit.py
OPENBLAS_NUM_THREADS=1 /tmp/fpl-audit-venv/bin/python -m pytest -q analysis/audits/2026-11-22/tests
```

Med dependencies installeret er reproduktionen offline. Scriptet verificerer frosne inputs og genberegner tabeller fra gemte scenarier og officielle resultater. Ingen model trænes eller simuleres, ingen TS-søgning køres, og ingen kilder eller publiceringer opdateres. Den kvalitative eksterne research er en dateret observation, ikke et numerisk kommercielt benchmark.

Originale JSON-filer er gemt tabsfrit som deterministisk gzip. Ukomprimerede filhashes kontrolleres mod de oprindelige index-kvitteringer. `input-integrity.json` er det frosne manifest; ændr det ikke for at få en fejl til at passere. `result-integrity.json` dokumenterer resultaterne. Genkørsel ændrer ikke de gemte Monte Carlo-stikprøver.

`code/collect_local_evidence.py` dokumenterer den oprindelige indsamling fra eksisterende checkouts og er ikke nødvendig for reproduktion. Inventarerne viser kortlagte filer, ikke at alle store eksperimenter og tests er genkørt. `code/reference/` indeholder byte-bevarede regelscorere til auditbrug; aktive produktionsmoduler er uændrede.

## Dækning

GW8–10: 2.007 oprindelige prognoser, 30 kampe. Modellen klarer den samtidige officielle `ep_next`-baseline bedre i denne stikprøve, men næsten nul samlet bias skjuler komponent-/positionsfejl. Klub-/spillergrupper er små. Krediterede spiller-mål kan aggregeres på 60 holdrækker; kun de 20 holdrækker i GW10 har den eksplicitte event-conservation-teammean. FPL-assists og efterkampens xA er forskellige targets.

GW11 er ikke finalt evalueret i det hentede report. Genbrugte historiske perioder, rekonstruerede backtests, oracles, mekaniktests og oprindeligt publicerede prognoser holdes særskilt. TS har ikke et certificeret nutidigt fuldt seks-GW-/chip-resultat. Ingen kommercielle sammenligningsresultater er opfundet.

Læs rapporterne for tal, datagab, kildevilkår og højst tre næste forsøg. Ingen automatisk integration er besluttet.
