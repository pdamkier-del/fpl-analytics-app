# TS v4 · Samlet forskning og validering

Den ændring, der har bedst grundlag for en afgrænset prospektiv test, er **tidsvægten i TS’ eksisterende seks-GW-mål**. Anbefalingen gælder en frossen forskningskandidat. De eksisterende studier støtter bevarelse af scorer, transferregler, hitbuffer og beam i baseline. Produktion og automatisk arkivering er uden for denne PR.

## Hvad de fem spor viser

| Spor | Dokumenteret effekt | Betydning for TS |
| --- | --- | --- |
| Fundamentel værdi | +£0,0072 mio. i tre-GW-prisændring pr. standardafvigelse i surplus. Alle fire transferheuristikker tabte til pointstrategien i begge evalueringssæsoner og ved alle tre holdetider. Prisspringet er £0,1 mio. | Prisassociation alene bærer ikke en transferpolitik. Priserne i den daværende replaystrategi var laggede, og fuld historisk TS v3 var uden for sammenligningen. [PR #61](https://github.com/pdamkier-del/fpl-analytics-app/pull/61) |
| Kapital og skyggepriser | Oprindelig GW12/GW13-prognose. Optimum fladt fra £98 til £102 mio., diskrete spring ved lavere budgetter. Wildcard gav +8,18 forventede GW13-point over én transfer ved samme £100 mio. | Kapital er en tilstandsafhængig mulighed. En fast pris i point pr. £1 mio. har ingen støtte her. Den empiriske terminalværdi er implementeret i en separat harness, og dens historiske sæsonmål afventer originale sammenhængende data. [PR #62](https://github.com/pdamkier-del/fpl-analytics-app/pull/62) |
| Korrelerede point | Fælles PM-træk gav retrospektiv variogram-score 0,815 mod 0,831 for uafhængige træk på 30 kampe. Risikopolitikker med syntetisk rival kunne koste middelpoint, og jagtvarianten tabte rivalchance i 38-GW-stresstesten. | Hold de originale fælles scenarier og den eksisterende lineupscorer fast. Foretag ingen ændring i rank- eller risikomålet på dette grundlag. [PR #63](https://github.com/pdamkier-del/fpl-analytics-app/pull/63) |
| Dynamisk optimering | Seks eksakte cases viser værdi af FT, bank, funding og tilpasning. I 2025/26-proxyen gav lige vægte +84 nettopoint med +60 hitpoint. Ti-GW-ekstrapolation og otte-GW-terminalrollout gav kun +12 og +6 med +140 og +128 hitpoint. | Den gamle ligevægtsarm lod både søgens shortlist og objektiv ændre sig med rho. Den nye sammenligning fastholder shortlistens vægte. Ingen gentagelse af ekstrapoleret hale, optimering af chips eller de seks småcases. [PR #64](https://github.com/pdamkier-del/fpl-analytics-app/pull/64) |
| Markedsdynamik | Ved GW +1 fik boosting Brier 0,0991 mod 0,1304. En prisvægtet proxy gav +23, −12 og +185 sæsonpoint. Fire originale MM/PM-GWs viste små, blandede pointresultater. | Marked kan give et sekundært budgetsignal, hvis sportslige alternativer allerede er næsten lige gode. En forbedret prisscore dokumenterer ikke sæsonpoint over TS v3. [PR #65](https://github.com/pdamkier-del/fpl-analytics-app/pull/65) |

## Tidsvægtning

Historisk kontrol er PR #64’s verificerede 38-GW-sti. De fire nye rho-arme genbruger samme historiske replay og samme starttrup, forecast-vintages, priser, klub- og formationsregler, FT-regler i harness, nomineringsscorer, udfald og beam-bredde. Med samme tilstand og GW får den lokale kandidatgenerator altid samme `0,60`-vægtvektor, inklusive den korrekte suffix ved senere søgetrin. Kun målets og beam-rangeringens pointvægt ændres. Efter første forskel i handling kan tilstandene og deres lovlige kandidatbundter divergere. `rho=1,00` her vurderer den samme shortlist som kontrol. PR #64’s +84 målte en bredere ændring med lige vægte begge steder.

Det uændrede hovedmål er `U(rho)=Σ_k [rho^k × forecast_score_k − 4 × paid_k − buffer × paid_k]`, hvor `k=0…5` og buffer er ét usikkerhedspoint pr. betalt transfer. For en isoleret fremtidig transfer med gevinst alene i det trin skal gevinsten overstige `5/rho^k`. Ved rho 0,60 og sjette trin er tærsklen 64,30 xP, heraf 51,44 fra de fire officielle hitpoint og 12,86 fra bufferpointet. Hvis gevinsten fortsætter i flere GWs, skal summen af dens vægtede gevinster i stedet dække omkostningen. Fremtidig billig adgang via en ekstra FT har derfor stor betydning i det frosne mål.

To kontraster ved rho 0,60 isolerer behandling af omkostninger. `discount_costs` bruger det eksisterende flag, som vægter de fire hitpoint og bufferpointet med samme rho som pointene. Tærsklen bliver 5 ved hvert trin. `zero_buffer` fjerner kun det femte point i planlægningen, hvilket giver `4/rho^k`. Begge replays fratrækker fortsat alle officielle hits ved realiseret scoring. De to kontraster er mekanismediagnostik.

| Rho | Brutto | Netto efter hits | Δ netto | Hitpoint | Transfers / roll | Δ GW1–19 / GW20–38 | Parret 5.–95. percentil | Median s/GW |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0,60 | 1.980 | 1.964 | 0 | 16 | 41 / 1 | 0 / 0 | [0, 0] | 13,1¹ |
| 0,70 | 2.007 | 1.987 | +23 | 20 | 42 / 1 | −9 / +32 | [−52, +105] | 8,4 |
| 0,80 | 2.016 | 1.976 | +12 | 40 | 47 / 1 | +21 / −9 | [−111, +138] | 6,9 |
| 0,90 | 2.104 | 2.052 | **+88** | 52 | 50 / 1 | +85 / +3 | [−15, +199] | 7,3 |
| 1,00 | 2.143 | 2.071 | **+107** | 72 | 55 / 1 | +80 / +27 | [−3, +229] | 10,7 |

¹ Baselineledger og dens køretid er fra PR #64. De parrede percentiler stammer fra 3.000 resamplinger af fire-GW-blokke inden for den samme sæson. Da hver arms efterfølgende tilstand også afhænger af dens tidligere handlinger, er intervallerne et deskriptivt følsomhedstjek.

**Anbefaling.** Test rho 0,90 som eneste prospektive kandidat. Den scorede højere i begge sæsonhalvdele og opnåede 88 af den ligevægtede arms 107 ekstra nettopoint med 20 færre hitpoint og fem færre transfers. Anden halvdel gav dog kun +3, og begge følsomhedsintervaller dækker nul. På den fælles originalcase betalte rho 0,90 otte flere hitpoint i første GW end TS v3 ved begge origins. Den lavere hitbyrde relativt til rho 1,00 i legacy-replayet kan derfor ikke antages at gælde for nye prognoser og starttrupper. Vælg rho 0,90 til at undersøge den ene mekanisme under den låste protokol.

| Omkostningsdiagnose ved rho 0,60 | Netto | Δ netto | Hitpoint | Transfers / roll | Første ændrede GW | Median s/GW |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Diskontér både planlagte hits og buffer | 1.935 | −29 | 16 | 41 / 1 | 6 | 6,9 |
| Buffer 0, officielle hits stadig udiskonterede | 1.949 | −15 | 20 | 42 / 1 | 18 | 6,5 |

Diskontér-planlægningsarmen ændrede rækkefølgen af handler uden at ændre det samlede transfer- og hittal. Nul buffer gav én ekstra transfer og fire ekstra hitpoint. Højere rho med fast buffer havde en større effekt på antallet af handler. Rho 0,90 brugte 36 ekstra hitpoint og solgte 13 køb igen inden for tre GWs mod fem for kontrol. Alle hovedarme rullede én gang. Den summede, samme-tilstand-forskel i realiserede point mod at rulle den aktuelle GW var −5 ved rho 0,90 og +30 i kontrol. Hver lokal sammenligning starter fra sin arms egen tilstand og udelader videre effekter af en alternativ rullebeslutning. Regnetiden for de seks nye legacy-arme summerer til ca. 1.975 sekunder af de loggede GW-tider, med parallelle processer. Den fulde audit afstemte alle 266 legacy-runder.

Tallene er fra de tidligere evaluerede 2025/26-data. Den historiske Phase5Q-prognose er rekonstrueret med estimerede deadlines og en endelig fixturekalender, så flyttede, blanke og dobbelte runder kan give restlookahead. Pris og klub efter det fælles seed kommer fra den seneste tidligere GW i denne harness. Den simulerede chipfri sti har ingen privat tilstands- eller udførelseslog og inkluderer ikke den særskilte administrative GW16-FT-top-up. Scoreren er det ældre arkivs xP- og spilchanceproxy. Udfald for point, minutter og hits bruges først efter låste beslutninger. Fælles datagrænser gør armene sammenlignelige i det samme replay og begrænser overførsel til den nuværende MM/PM-kæde. [Legacy-manifest og karantæne](https://github.com/pdamkier-del/fpl-analytics-app/blob/6d875a65251fb62f691dc0386ea81aeb29d27c0f/analysis/results/legacy-rolling-recovery-v1/manifest.json) · [PR #64’s replayaudit](https://github.com/pdamkier-del/fpl-analytics-app/blob/01bcaba225c111b222f3b329a3e18245a4f14835/research/dynamic_control/REPORT.md)

## Gratis transfers, bank og funding

TS v3 foreslår altid behold-truppen og bærer bank, købskurs, klubrestriktioner og FT frem i overgangen. Beamens rangering bruger akkumuleret score plus forventede point ved at beholde den efterfølgende trup. Værdien af en ny lovlig handling med flere FT, mere bank eller en fri klubplads får derfor kun kredit, hvis søgningen faktisk besøger den. Desuden kan et isoleret negativt fundingtrin forsvinde i fast-local, selv hvis den samlede lovlige bundle er værdifuld. Ingen af mekanismerne kræver, at den beregnede FPL-salgspris eller FT-overgang er forkert.

| Eksakt reference fra PR #64 | Fund |
| --- | --- |
| Roll for two | Rul for to FT. En grådig/narrow beam-sti taber 3, mens den eksakte ekstra FT ved start er 1 point værd. Rho 0,60 med fuld lille generator finder roll. |
| Funding bundle | Et fundingtrin med −2 isolerede point åbner en handel med +7. Et ekstra pengesteg er 3 point værd i den konkrete case. |
| Short-term trap | Et kort køb giver +2 nu, men blokerer senere genkøb. Den diskonterede lille policy taber 4 på førstevalget mod den eksakte fortsættelse. |
| Availability shock | Muligheden for at handle efter næste chok er 9,2 forventede point værd. Den modale beam finder førstevalget i denne case. |
| Bank threshold | £0,1 mio. åbner en mulighed på 9 forventede point. En ekstra FT ved samme tilstand har nul marginalværdi. |
| Value of adaptation | En bred modal beam har 4 points førstevalgs­gab, mens en eksakt scenariebaseret fortsættelse lukker det i casen. |

Den låste worker havde 11 positive søgegab i 30 deterministiske småcases. I den tidligere fuld-pool-test på original GW12 gav funding-udvidelsen samme utility i 10 afsluttede par og timede ud i de to andre ved 120 sekunder. Det adskiller en dokumenteret begrænsning i forslagslisten fra evidens for en praktisk forbedring. Kapitalresultaterne støtter, at tærskler er lokale og diskrete. Førstevalgs- og ressourcemekanismerne kan forklares med eksisterende cases, så denne PR tilføjer ingen separat fleksibilitetsalgoritme. [Eksakte cases og code paths](https://github.com/pdamkier-del/fpl-analytics-app/tree/01bcaba225c111b222f3b329a3e18245a4f14835/research/dynamic_control) · [PR #48](https://github.com/pdamkier-del/fpl-analytics-app/pull/48) · [PR #57](https://github.com/pdamkier-del/fpl-analytics-app/pull/57)

## Originale forecasts og et markedsvalg med roll

Rho-sammenligningen bruger to allerede publicerede releases, GW12 og GW13 i 2026/27, med seks GW og 400 fælles point- og minuttræk. Ved begge origins starter alle arme fra den samme før resultaterne eksisterende, offentliggjorte syntetiske case 01 fra PR #57. Den scores i hver originals udgivne spillerunivers og priser. Truppen er en fælles regnecase, og ingen privat brugerstate eller nye sportsprognoser indgår. De to origins måler plausibilitet og regnetid, da de endnu manglede officielle finalitetsflag ved gennemgangen. Utility kan sammenlignes mellem handlinger ved samme rho, og den skifter skala på tværs af rho.

Hold markedsvarianten til to førstehandlinger, den uændrede pointsøgnings vinder og roll. Roll beregnes ved at tillade hold som eneste førstehandling og køre den samme pointbeslutning resten af horisonten. Roll kan kun overtage ved et tab på højst 0,25 enheder i den samme seks-GW-utility, højere forventet likvidationsværdi og højst samme antal officielle hits. Ved en allerede valgt roll, uafgjort marked eller utilstrækkelig dokumentation vælges kontrolhandlingen. Udregn markedsleddet fra PR #65’s tre-dages boostingprognose. Genbrug foldet, som ved den samtidige snapshotdato udelukkende trænede på observerede, modne labels. Forvent ændringen i lovlig salgsværdi under hvert klasseudfald, med ét pristick som fast størrelsesproxy. Alle berørte spillere skal have en prognose, og deres priser skal matche mellem modelquote og original forecast-bootstrap, og market quote skal være taget højst 24 timer før forecastets cutoff. Legale FT, bank og hits kommer stadig fra TS-tilstanden.

| Original | Første transfers / hitpoint ved rho 0,60 / 0,70 / 0,80 / 0,90 / 1,00 | Point-utilitytab ved roll | Forventet likvidationsforskel for roll, i pristicks | Ændret handling |
| --- | --- | ---: | ---: | --- |
| GW12 `f54f651e` | 3/8 · 4/12 · 4/12 · 5/16 · 5/16 | 5,498 | Blokeret. Seneste dagsquote var ca. 25 t 27 min gammel. | Nej |
| GW12 `9e03db63` | 3/8 ved rho 0,60. Senere original med frisk dagsquote til markedstest. | 5,027 | −0,0763 | Nej |
| GW13 `98e2e695` | 3/8 · 4/12 · 5/16 · 5/16 · 5/16 | 4,572 | −0,0166 | Nej |

Den nyere GW12-revision blev kun brugt til den parrede markedstest, fordi dens ægte dagsquote ligger inden for vinduet. Begge prisberegninger med brugbar vintage bevarede pointhandlingen, og ingen arm fik markedsdrevne ekstra hits. Ingen af cases lå inden for 0,25-pointgrænsen, så materialet afgør ikke værdien af markeds-tiebreak ved et faktisk tæt valg. De to brugbare revisionschecks repræsenterer to origins og samme regnecase. PR #57’s femten startspillere, købspriser og bank er genbrugt uændret på tværs af de originale forecast-inputs.

Den gamle GW12-baseline reproducerede eksakt alle seks actions og utility 110,0124552 fra PR #57. I de nye originale runs blev 14 × 6 = 84 plantrin afstemt uafhængigt med lovlige trupper, bank, FT, hits og scenariescore. Beregningstid var 15,9–67,7 s pr. arm på en belastet maskine med genbrugt scorer-cache i samme vintage. Rækkefølgen og cache gør dette til en runtime-diagnose. Den kan ikke bruges til relative speedup- eller p90-claims. Seks-GW-timingen ændrede den første disposition og øgede hitmængden for denne starttilstand ved højere rho. Der foreligger ingen realiserede point. [Originale transferstier og markedsberegning](results/originals.json)

## Kontrol af eksisterende automatisk arkivering

- **Forecast og pris.** Main’s automatiske workflow leverer originale MM-/PM-scenarier, fixtureplan, bootstrap med pris og kumulative transferfelter, TS-konfiguration, checksums og prædeadline-kvittering. Blandt de seneste ti gennemgåede archive jobs var to succesfulde, begge naturligt trigget for GW13. De to anvendte originale releases blev genoprettet og kontrolleret byte for byte. De ti på det tidspunkt publicerede revisionsbundter omfatter otte GW12 og to GW13, altså to origins. Main-arkivet lover ingen jævn dagskadence for PR #65’s flowlags. Det låste analyseinput kan derfor kræve autentiske samtidige dagsudtræk fra den publicerede eksterne kilde. Den observerede planlagte fejl ramte trin for originalarkivering. Actions’ statusartefakt kunne ikke hentes på grund af HTTP 403 fra lageret, så den nøjagtige årsag er uverificeret. [Seneste succes](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/46137737470) · [Anden succes](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/46099511958) · [Planlagt fejl](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/46109840134)
- **Outcomes.** Forecastbundtet er en før-deadline-udgivelse. Officiel bootstrap viste `finished=false` og `data_checked=false` for GW12 og GW13 ved kontrollen. Producerede outcome-data skal høstes og hashes efter begge flag er sande. Main har den separate ugentlige review-kørsel, hvis seneste fire planlagte jobs fejlede. Den pinnede, automatiske C2-evaluering af primære labels afventer stadig integration i åben PR #55. Der er ikke verificeret et sammenhængende arkiv af endelige labels koblet til originale beslutningsorigins. [Main-arkivets datakontrakt](../../integration/research-data/C1_DATA_AVAILABILITY.md) · [Seneste weekly review](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/45468369366) · [PR #55](https://github.com/pdamkier-del/fpl-analytics-app/pull/55)
- **Transferstate.** Det offentlige arkiv udelukker privat trup, købskurser, bank, FT og chips. Main’s eksplicitte managerworkflow giver det anmodende browsermiljø et krypteret planresultat med 30-dages retention. Det leverer ikke en løbende, autoriseret forskningsjournal med plan, intention og verificeret udført transfer. PR #51 dokumenterer syntetisk privat recovery og en uløst real end-to-end-holdbarhed. Tilstandsreplay med virkelige managere afventer denne evidens. [Managerworkflow](../../.github/workflows/live-manager-plan.yml) · [PR #51](https://github.com/pdamkier-del/fpl-analytics-app/pull/51)

## Prospektiv protokol

1. **Arme.** Frys TS v3 med rho 0,60 som kontrol og **rho 0,90 med fast 0,60-shortlist** som eneste kandidat. Kilden fastlåses til den originale numeriske revision og samme konfigurationshash i begge arme. Eneste ændring er pointvægtene i målet og den tilsvarende beam-rangering. Fasthold fast-local-shortlisten med rho 0,60, hitbuffer 1, priser, scorer, transferregler og en fælles chipfri protokol. Markedsvarianten og omkostningsdiagnoserne er uden for bekræftelsesforsøget.
2. **Inklusion og fælles state.** Lås protokol, runtimehash, kohorte, startstate og scoringsregel før første nye issue. Udvælg seneste komplette, hashverificerede original, som er publiceret efter denne lås og senest 60 minutter før officiel deadline. Udvælg én origin pr. GW. Log offentlig forecast-receipt, samtidige priser og officiel fixtureplan. Gem autoriseret privat starttrup, købskurser, bank, FT og chipstatus separat. Begge arme forgrener sig fra samme prædeadline-tilstand ved start. Gem beregnede og eventuelt faktisk udførte handlinger separat.
3. **Fortsættelse og udfald.** Kør parrede skyggestier gennem 16 på forhånd fastlagte, sammenhængende GWs fra første kvalificerede origin. Begge arme følger samme eksplicitte regler for dokumenterede ændringer i FT-regimet og klubgrænser. Brug samme originalprognose og markedspriser ved hvert refit, og udfør kun første handling i de to simulerede tilstande. Scor XI, kaptajn og autosubs på officielle finaliserede spiller/minut- og fixturelabels efter `finished && data_checked`. Gem labelhash og revision. Lås datasættet 30 dage efter sidste planlagte deadline. En manglende forecast-, pris-, state- eller outcomeovergang afbryder primærstien og rapporteres som blokering. Der kan rapporteres parrede førstevalgsdiagnoser fra mindst 12 komplette enkeltorigins med verificeret fælles state. Det er et særskilt estimand.
4. **Endepunkter.** Primært er forskel i faktiske nettopoint efter hits på den 16-GW-sti. Rapportér gross point, hits, rolls, kort ejertid, bank og lovlighed pr. GW samt samlet vægttid, median og p90 af CPU-/wall-tid. Rapportér parrede fire-GW-blokintervaller og følsomhed med hver halvdel. Efficacy skal vise positiv nedre 95 %-grænse og mindst 4 nettopoints samlet. Alle overgange skal være legale, numerisk reproducerbare og uden ændringer af runtime-inputs. Planner-p90 må højst være 30 s og kandidatens median højst dobbelt kontrol under samme ressourcer. En enkelt 16-GW-sti siger ikke i sig selv noget sikkert om næste hele sæson.
5. **Stop.** Ingen tuning, kandidatudskiftning eller stop for en tidlig gevinst. Lås offentliggjorte kvitteringer og rapportér datagab og alle planlagte GWs, også ved blokering. Forsøget evaluerer de frosne skyggehandlinger. En eventuel produktionsændring kræver separat evidens og godkendelse.

## Reproduktion og regression

Kør fra repository-roden med Python 3.12, NumPy 2.3.5, pandas 2.2.3, SciPy 1.17.0, scikit-learn 1.8.0, Matplotlib 3.10.8 og pytest. Brug de fastlåste checkouts nedenfor og friske input-/outputmapper. GitHub CLI bruges til offentlig readback. Armene kan køres sekventielt med én numerisk tråd. Den aktuelle måling bruger to parallelle legacy-processer og overlapper de originale beregninger. TS v3’s legacy-baselinetid stammer fra PR #64, så tiderne er diagnostiske.

```sh
root="$PWD/work/ts-validation"
mkdir -p "$root"
git fetch origin 01bcaba225c111b222f3b329a3e18245a4f14835 6d875a65251fb62f691dc0386ea81aeb29d27c0f \
  161b67b6fb8786a38e78c245b92a03ad841575d8 a07e8f7aef0e9bdc9e5dfbb6a31f157c37826af9 \
  3715a063e6b9e8e3458205331b5f844703c6781b
git worktree add --detach "$root/pr64" 01bcaba225c111b222f3b329a3e18245a4f14835
git worktree add --detach "$root/legacy" 6d875a65251fb62f691dc0386ea81aeb29d27c0f
git worktree add --detach "$root/frozen" 161b67b6fb8786a38e78c245b92a03ad841575d8
git worktree add --detach "$root/c1" a07e8f7aef0e9bdc9e5dfbb6a31f157c37826af9
git worktree add --detach "$root/market" 3715a063e6b9e8e3458205331b5f844703c6781b
git worktree add --detach "$root/archives" d4d6e8046ad5d965cf41f5a8fce2b32a49fca16c
python "$root/pr64/research/dynamic_control/verify_source.py" "$root/legacy"
for arm in tsv3 rho70 rho80 rho90 rho100 discount_costs zero_buffer audit; do
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python research/ts_v4_validation/compare.py \
    "$root/pr64" "$root/legacy" "$root/legacy-results" "$arm"
done
python "$root/market/research/market_dynamics/fetch.py" "$root/market-inputs"
TS_VALIDATION_INPUT="$root/originals" PYTHONPATH=integration/research-data:research/ts_v4_validation python - <<'PY'
import json, os
from pathlib import Path
from originals import REVISIONS, MARKET_GW12
from releases import Github, recover

class ReadOnlyGithub(Github):
    def create(self, *args):
        raise RuntimeError("Research uses completed public releases only")
    upload = create

root = Path(os.environ["TS_VALIDATION_INPUT"])
api = ReadOnlyGithub("pdamkier-del/fpl-analytics-app")
for gw, revision in zip((12, 13, 12), (*REVISIONS, MARKET_GW12), strict=True):
    _, proof = recover(f"fpl-forecast-2026-27-gw{gw}-{revision}", root, api)
    (root / f"{revision}.proof.json").write_text(json.dumps(proof))
PY
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python research/ts_v4_validation/originals.py \
  "$root/c1" "$root/frozen" "$root/market" "$root/market-inputs" "$root/originals" "$root/originals.json"
python -m pytest -q research/ts_v4_validation/test_compare.py tests/research_data
(cd "$root/pr64/research/dynamic_control" && python -m unittest -q test_small test_replay)
(cd "$root/c1" && FPL_ARCHIVE_RUNTIME="$root/archives" python research/tools/verify_current.py)
```

Fire nye kontrakttests og 27 arkivtests bestod. PR #64’s fem regressionstests og C1’s eksisterende 94-gennemløb bestod, med to historiske snapshot-tests fravalgt af C1’s egen selektor. Legacykildens og forecast-/prisbundtets bytehashes er kontrolleret. Alle nye ændringer ligger under `research/ts_v4_validation/` på `research/ts-v4-consolidated-validation`. Basen er main `5e35397b`. Main rykkede under kørslen med en ændring i AGENTS.md, mens den originale C2-runtime fortsat valideres ved det pinnede `d4d6e804`.

[Legacybeslutninger pr. GW med afstemte udfald](results/decisions.csv) · [Sammenfattede sammenligninger og parametre](results/summary.json) · [Originalscenarie-stier og runtime](results/originals.json) · [Kilde- og arkivreceipter](results/provenance.json)
