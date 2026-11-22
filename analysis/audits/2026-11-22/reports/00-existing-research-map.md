# Fase 1 — Eksisterende forskning og testgrundlag

178 forsøgsmapper og 2471 filer er indekseret fra den eksisterende forskningscheckout. Dens mappeindhold er ikke lig med 178 uafhængige eksperimenter; nogle mapper indeholder datarecovery, UI-kontroller og samme genbrugte testperioder. Fuld fil-/hashoversigt: `../research-inventory.json`. Kurateret modelkort: `../research-map.csv`. Pinned test-/browserkontroloversigt: `../test-inventory.csv` (236 filer; “listed” betyder ikke “passed”).

## Evidensklasser

1. **Oprindeligt publiceret før deadline:** GW8–10-evalueringen; ingen ny forecastberegning. Politik/version varierer.
2. **Kronologisk rekonstrueret input, men senere valgte modelregler:** blandt andet GW6–8-backtest; ingen påstand om uafhængig live-test.
3. **Development/reused diagnostic:** en stor del af GW22–38-forsøgene, dynamiske filtre, rolle- og budget-ablationer. Må bruges til fejlsøgning og prioritering, ikke som ny validering hver gang.
4. **Oracle/hindsight:** faktiske start/minutbins, bedste XI eller perfekt komponent; illustrerer følsomhed, men er ikke deployerbare modeller.
5. **Mekanik-/kontrakt-/UI-test:** dokumenterer lovlighed, identitet og softwarekorrekthed, ikke scoregevinst.

## Vigtigste allerede prøvede retninger

MM: workload/role, exact-XI, availability-caps, sekvens/HMM, starter-/cameo-duration, match importance og Europa-rolle-recovery. PM: teamfilter, finishing/shot quality, role-performance/shrunk xG/xA-allokering, budgetfordeling, keeper-SOT/save-buckets, DC-thresholds, BPS-middel/varians og delt penaltyhændelse. TS: horizon weights, hit buffers, v2/v3, FT-policy, stateful replays og chipmekanik. Ingen af disse bør genfremsættes som uprøvede idéer.

Den kuraterede CSV angiver konkret afvisningsgrund eller begrænsning pr. studie. Alle performanceudsagn skal læses med deres forecast-provider, regler/sæson, population og scoremål. Det højeste sæsonpointtal eller den laveste reused-MAE er ikke i sig selv valgbart som produktionsmodel.

## Kendte uløste forhold

- For få forventede indskiftninger og for høj P90 i nyere arkiver; lovlig fælles proces testes allerede.
- DC og BPS-baggrund er ikke betinget koblet i den enkelte kamp.
- Legacy BPS-target/proxy og nye bonusregler bruger forskellige enheder/definitioner; kræver kontrolleret retargetering.
- Redningers inside-/big-chance-subtyper mangler eksplicit; noget rådata findes allerede.
- Præcise substitutions-/injury-/cup-kalenderklokker og historiske forventede XI er ikke fuldt certificeret.
- Den historiske TS-horisont er ufuldstændig, og chips er ikke valideret af chips-off replaytal.

## Faktisk kørsel i denne audit

Nye scripts genberegner scores og tabeller fra arkiverede data og gemte scenarier. Scoringsoracle genafspiller faktiske labels gennem uændrede regelscorere. Ingen dyr model-, PM- eller TS-simulation genkøres. De store historiske eksperimentresultater genbruges med hashes. Afgrænsede correctness-regressionstests og audit-tests står i testkvitteringen; øvrige tests er kun kortlagt.
