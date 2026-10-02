# Reproducerbar role-aware foundation, 2. oktober 2026

Fortsættelse på `audit-role-minutes-20261001` fra
`785e52b568def1847cf967fde7e125ee21e78f77`. Den aktive app/desktop-bridge er
ikke ændret. Dette er en ny, fuldt dokumenteret rekonstruktion af role-features,
ikke en påstand om bit-identisk reproduktion af den manglende gamle featurebygger.
Ingen parametre er valgt for at ramme de gamle rapporterede holdout-tal.

## 1. De 1.052 uenigheder

Alle 8.360 starter-slots er matchet til stabile spiller-ID'er og fixtures. De
strukturelle roller matcher den gendannede slot-fil præcist efter AM→CAM.
1.052 af 7.600 markspiller-startere er uenige: **13,84 %**.

| Diagnostisk forskel | Antal | Andel af uenigheder |
|---|---:|---:|
| Direkte venstre/højre-permutation af samme rolle | 209 | 19,87 % |
| Anden rækkefølge inden for samme formationslinje | 371 | 35,27 % |
| Rolle tilhører en anden formationslinje | 472 | 44,87 % |

Dette er mekanismegrupper, **ikke verificerede fejl-labels**. En kampgennemsnitlig
position kan afspejle legitim bevægelse, possession, game state eller formationsskift.
Data indeholder ikke tidsopdelte formationsskift, positionernes varians eller antal
touches. Derfor kan vi ikke ærligt fordele alle 1.052 i taktisk korrekt vs bug.

Den gamle geometry-importer beskyttede D/F-linjer, når source's brede
D/M/F-antal passede formationen, men delte stadig midfield-linjer med average x.
Når antallene ikke passede, sorterede den **alle ti markspillere efter average x**.
Denne globale fallback står for 394 uenigheder (37,45 %), heraf 256 cross-line;
658 uenigheder opstår også i den beskyttede sti, heraf 216 cross-line.
Det er dermed ikke bare én fælles left/right-fejl.

Konkrete dataproblemer:

- Fire startere mangler koordinater: Bornauw (CB→ST), Mainoo (LDM→ST),
  Hickey (LB→LCB), Berge (LDM→CAM). Geometry-rollen er ikke gyldig evidens dér;
  den nye classifier bevarer strukturrollen og markerer manglende/usikker position.
- Ved identisk average y gav en utilsigtet ændring fra numerisk til leksikografisk
  spiller-ID-sortering to ekstra Brentford-uenigheder (Ouattara/Jensen i GW37).
  Replay fastholder den gamle numeriske tie-break. Der er derfor præcis 1.052,
  ikke 1.054. Determinisme betyder også eksplicitte tie-breaks.
- Ti source-lineup-startere afviger fra Core's actual-start-label. De bevares i
  auditen, men Core's label styrer H's start-evidens og benchmark-targets.

Største konkrete rollepar (uordnet; fuld liste i CSV):

| Par | Antal | Andel |
|---|---:|---:|
| LDM ↔ RDM | 106 | 10,08 % |
| LCM ↔ RCM | 65 | 6,18 % |
| CAM ↔ LAM | 54 | 5,13 % |
| CAM ↔ RDM | 51 | 4,85 % |
| RAM ↔ ST | 50 | 4,75 % |
| CAM ↔ LDM | 49 | 4,66 % |
| CAM ↔ RAM | 49 | 4,66 % |

Der er ikke direkte RB↔RWB/LB↔LWB-par i denne sammenligning: begge metoder
bruger samme formationskapaciteter. Det beviser ikke, at fullback/wingback er
korrekt i alle kampe; sammenligningen kan ikke opdage en delt template-fejl.

Hold med flest uenigheder: Palace 123/380 (32,37 %), Man United 96/380
(25,26 %), Fulham 79/380 (20,79 %), West Ham 74/380 (19,47 %), Wolves
72/380 (18,95 %). Villa har 18/380 (4,74 %). Alle 20 hold findes i
`disagreements_by_team.csv`.

Formationer: 4-2-3-1 står for 458/1.052 (43,54 %), men kun 11,23 % af sine
4.080 markspiller-slots. 3-4-2-1 står for 323 (30,70 %) og har 36,29 %
uenighed blandt sine 890 slots. 4-4-1-1 har 38/80 (47,50 %; lille sample),
3-4-1-2 har 22/80 (27,50 %), 4-3-3 har 72/1.050 (6,86 %).
Alle 18 formationsgrupper samt hold×formation×rollepar findes i CSV.

`role_disagreements.csv` indeholder fixture, kamp, hold, spiller, formation,
slot, slot-role, x/y, position-role, valgt rolle, mekanisme, kvalitet/uncertainty,
begrundelse, samt q og evidens **før kampen** for hver af de 1.052 rækker.

## 2. Classifier v1: struktur først, forsigtig geometry

Kode: `src/fpl_v1_1_model/role_classifier.py`.

1. Parse en formation med ti markspillere; kræv elleve unikke slots og keeper
   i første slot. Source-rækkefølge er lineup-slot, ikke trøjenummer.
2. Tildel formationslinjernes roller i slot-rækkefølge. CAM er central 10'er
   i 4-2-3-1, 4-4-1-1 og 3-4-1-2. 3-4-2-1 har RAM/LAM, ikke en tvungen
   central CAM. Tre-back-strukturens brede midfield-slots er RWB/LWB.
   RAM/LAM/SS fra checkpointets finere taksonomi bevares ud over minimumrollerne.
3. Beregn geometry-alternativet med den gendannede, nu tilgængelige importer.
   Bevar det som audit-evidens, aldrig som target-kampens forecast-input.
4. En klar strukturrolle ændres kun ved en **hel permutation inden for samme
   formationslinje**: geometry-rollerne skal have præcis samme multiset som
   linjen; alle koordinater skal være gyldige; adjacent y-gap mindst 10;
   x-spread højst 20. For alle ændrede spillere kræves tidligere evidens ≥3,
   q(alternativ) ≥0,65 og q(alternativ)−q(slot) ≥0,25.
5. Ingen cross-line override følger af kampgennemsnitlig x alene. Ved ugyldig
   struktur bruges source-GK, ellers tidligere q, ellers geometry; lav confidence
   og manglende evidens er eksplicit. Koordinater alene er ikke ground truth.

Regler/grænser er faste, ikke OOS-tunede. På de aktuelle data giver de **nul
overrides**: endelige roller er slot-roller. Dermed er forecast-gevinsten nedenfor
fra historisk strukturel rolleevidens, **ikke** fra en demonstreret geometry-fix.
Reglen for prior-understøttede sidekorrektioner testes syntetisk, men er ikke
empirisk valideret her. Den konservative løsning gør tvivlen synlig; den påstår
ikke at have løst alle 1.052 faktuelt. Prior kan selv arve slot-fejl.

## 3. q/H fra scratch og cutoff

Kode: `src/fpl_v1_1_model/role_history.py`.

Kun team-kampe med historisk effective-availability **strengt før cutoff** indgår.
Proxy er kickoff+3 timer: ikke source's reelle publication/ingest-timestamp.
Fast/slow halvlevetid er faste 3/10 holdkampe, ikke kalenderuger. Kun startere
med gyldig fine-role og Core-actual-start indgår i rolleevidensen; vi opfinder
ikke en sub-rolle ud fra en kort cameo.

- q: role-minute-mass = recency-weight × min(1,35, minutes/90), derefter
  smoothing 0,05 pr. outfield-rolle og normalisering. Keeper q er kun GK.
- H: recency-vægtet actual-start-mass pr. spiller/rolle, skaleret med holdets
  historiske kapacitet for rollen; smoothing 0,1 blandt observerede kandidater;
  cap 0,995. Ingen evidens i rollen giver H=0.
- Kapaciteter: recency-vægtet antal actual-startere i rollen pr. holdkamp.
- q/H er i denne v1 **spiller-ved-hold**, kun PL 2025/26. Rolleviden fra et
  tidligere hold eller tidligere sæson bæres endnu ikke over ved transfers.
- Ukendt fin rolle giver tom q/H og eksplicit UNKNOWN; ikke en skjult CM-label.
- For et GW bruges samme deadline-proxy for alle fixtures, også DGW.
  Target-lineup, target-average-position og actual-role bruges kun i posthoc-audit.

Core indeholder ikke de faktiske deadline-timestamps. Standardcutoff er derfor
første kickoff i GW minus 90 minutter. `--cutoffs` kan erstatte den med en
autoriseret CSV med `gw,cutoff`. **Cutoff-safe mod denne historiske proxy er
ikke det samme som certificeret live as-of/ingest-safe.** Fixtures er historisk
færdigspillede; præcis samtidens roster/cohort er heller ikke dokumenteret.

V2 er den uændrede GW-filtrerede comparator. `legacy_gw_cutoff_audit.json`
er tom: på denne sæsons kohorte findes ingen hold/GW hvor lavere-GW-kampe endnu
ikke var kendte, eller højere/samme-GW-kampe allerede var kendte før proxycutoff.
Det er en konkret kontrol, ikke en universel garanti om V2's andre inputfelter.

## 4. Features og frosset OOS

Script: `scripts/build_reproducible_role_benchmark.py`.

Udviklingsfit: GW6–21, 12.172 labels kendt før holdout-cutoff 17. januar 2026
kl. 11:00 UTC. Fit fryses; ingen GW22–38-label bruges til koefficienter eller
scaler. Historiske, senere afsluttede kampe må fortsat opdatere q/H før næste
cutoff, som ved en live model.

LogisticRegression C=1, StandardScaler, base_logit og ni role-features.
Efter prediction anvendes samme exact-11 hold/fixture-constraint som V2.
E[min|start], P(sub|bench) og E[min|sub] er **uændrede V2-inputs**; kun P(start)
udskiftes i minutes-identiteten. Aktuel minutes-decomposition er dermed bevaret,
ikke erstattet af et nyt duration-fit. Ingen workload/importance/cup-value-fit.

| GW22–38, n=13.987 | Brier | Log-loss | xMins MAE | xMins RMSE |
|---|---:|---:|---:|---:|
| V2 baseline | 0,077148 | 0,257716 | 11,958642 | 21,922479 |
| Baseline-logit-only kalibreringskontrol | 0,077150 | 0,257708 | 11,951054 | 21,923321 |
| Ny reproducerbar role-aware v1 | 0,076645 | 0,251343 | 11,823680 | 21,858693 |
| Uden H-features (ablation, ikke valgt vinder) | 0,076448 | 0,252070 | 11,904938 | 21,786628 |
| Kun H + baseline-logit (ablation) | 0,077268 | 0,258304 | 11,915889 | 21,967319 |
| Gammel rapporteret role-aware, ikke reproduceret | 0,076461 | 0,250914 | 11,640715 | 21,831759 |

Diff mod V2: −0,000503 Brier (−0,65 %), −0,006373 log-loss (−2,47 %),
−0,134962 minutter MAE (−1,13 %), −0,063785 RMSE (−0,29 %).
Forbedring pr. GW: 10/17 Brier, 14/17 log-loss, 15/17 MAE, 12/17 RMSE.
Pr. hold: 13/20, 18/20, 17/20, 13/20 i samme rækkefølge.
Det genskaber **ikke** den gamle påstand om 27/27 eller 19/20.

Paired GW-block-bootstrap (17 blokke, seed 20261002, 2.000 draws) er gemt:
log-loss/MAE-intervaller er negative; Brier/RMSE-intervaller inkluderer nul.
Der er kun én sæson/17 GWs og flere undersøgelser; ikke en universel garanti.

## 5. Sanity check: hvor hjælper rollerne?

| Posthoc target-role-gruppe | n | MAE V2 | MAE ny role-aware |
|---|---:|---:|---:|
| Slot/geometry agreement | 3.199 | 21,669712 | 21,685424 |
| Slot/geometry disagreement | 541 | 22,560827 | 22,674551 |
| Ingen target-starter-role (bench) | 10.247 | 8,367201 | 8,172071 |

Disagreement-gruppen får bedre Brier (0,175561→0,168757) og log-loss
(0,534694→0,525110), men **dårligere MAE**. Agreement-gruppen forbedrer
start-målene mere. Begge grupper er udvalgt ud fra target-startere, så de er
selection-biased diagnostik, ikke selvstændige prospektive populationstests.

Også i den cutoff-safe gruppe med tidligere uenighed stiger MAE
20,344562→20,816397 (n=4.184). Når role-features ændrer P(start) mindst
5 procentpoint mod kalibreringskontrollen, stiger MAE 26,040447→26,546922
(n=1.994); under 5pp falder MAE 9,617350→9,375741 (n=11.993).
5pp-gruppen defineres af prediction, ikke af label, men er stadig heterogen.

**Svaret på sanity-checket er derfor nej:** gevinsten er ikke dokumenteret som
større, hvor tvetydig rolleinfo gør mest forskel. Samlet MAE-gevinst kommer
især fra bench/små justeringer. Bevar kandidaten eksperimentel, indtil denne
mekanisme og næste uafhængige OOS-sæson er undersøgt.

## 6. Diff mod den gamle fil

Den oprindelige `role_augmented_holdout_predictions.csv` og dens featurebygger
er stadig ikke i de gendannede checkpoints. Vi har metrics JSON og downstream
manager-XI-kode, som **læser** filen. Det er ikke dens producerende kode.

| Feature | Ny definition | Gammel definition/status |
|---|---|---|
| base_logit | logit af uændret V2 post-constraint p | Navn og baseline kendt; original role-builder mangler |
| role_fit_fast/slow | sum q(r)×min(1, historisk kapacitet(r)) | Navne kendt, formel mangler |
| role_h_fast/slow | sum q(r)×H(r) | Navne kendt, H-beregning i featurebygger mangler |
| role_qmax_fast/slow | max q | Navne kendt, smoothing/halvlevetid i builder ukendt |
| role_evidence_fast/slow | log(1+weighted starter-minute-mass) | Navne kendt, skala ukendt |
| role_started_last_gw | actual-start i seneste afsluttede holdkamp | Navn kendt, præcis GW vs kamp-semantik ukendt |

Ny minus gammel rapporteret: +0,000184 Brier, +0,000429 log-loss,
+0,182965 MAE, +0,026934 RMSE. Start-målene er tæt på, minutes-MAE-gevinsten
er klart mindre. Mulige forklaringer er q/H-definition, smoothing, fast/slow
halvlevetid, starter-only-evidens, scaling, træningsvindue eller fit-protokol.
Vi kan **ikke** identificere hvilken forskel der er årsagen uden originalens
rækkevise features/koefficienter. Manager-XI's expanding-fit/C=0,3 er ikke bevis
for role-only-modellens fit. Der er ikke tunet mod de gamle tal.

## 7. Reproduktion og checkpoint

Fra repo-roden (Python + NumPy/pandas/SciPy/scikit-learn):

```bash
mkdir -p work
gzip -dc model/checkpoints/phase5e_core/fpl_v1_1.sqlite3.gz > work/core.sqlite3
python scripts/reproduce_pstart_v2_fixture_minutes.py --db work/core.sqlite3 --out analysis/results/v2-reproduced
python scripts/build_reproducible_role_benchmark.py --db work/core.sqlite3
python scripts/run_model_checks.py
```

Resultater under `analysis/results/reproducible-role-v1/`:
classifier-audit, hver disagreement, grupperinger, alle features/predictions,
q/H pr. rolle fast/slow, cutoff, expected-role, unchanged conditional minutes,
actuals, metrics pr. GW/hold/fine-role/agreement, modeller/scalers/koefficienter,
bootstrap og input/code/output SHA256-manifest. CSV.gz er almindelig gzip-CSV,
ikke et proprietært format. All-feature-filen markerer udviklingsrækker som
in-sample; holdout-filen indeholder kun frozen_oos.

Rådata, frosset Historical Core og baseline-kode er allerede versioneret i
samme repo. Appens UI/aktive forecasts og immutable checkpoint er bevaret.
GitHub branch creation blev igen afvist med HTTP 403, Resource not accessible
by integration. Checkpoint skal derfor leveres komplet som Git bundle/ZIP,
med instruktion til `git clone` og senere push af samme branch, ikke et nyt repo.

Næste faglige trin er målrettet gennemgang af high-impact rolleuenigheder og
uafhængig validering af rolleniveau/minutes-grupper før nyt duration/sub-model-fit.
Dette checkpoint åbner ikke Match Importance/cups endnu.
