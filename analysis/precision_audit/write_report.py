"""Render the single audit report from frozen numerical results."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'analysis/results/systematic-precision-audit-20261101'
def table(f):
    def fmt(x):
        if isinstance(x,(float,np.floating)):return f'{x:.4f}'
        return str(x)
    return '| '+' | '.join(f.columns)+' |\n| '+' | '.join(['---']*len(f.columns))+' |\n'+'\n'.join('| '+' | '.join(fmt(x)for x in row)+' |'for row in f.itertuples(index=False,name=None))
def read(name):return pd.read_csv(OUT/name)
def main():
    base=read('baseline-metrics.csv');base=base[base.group.eq('all')][['season','fixtures','rows','xp_MAE','xp_RMSE','xp_bias']]
    mm=read('minute-error-structure.csv');small=mm[mm.group.isin(['all','playing_role=regular','playing_role=rotation','playing_role=reserve','medical_out','returning','high_load_180plus','UEFA_7d_sourced_subset','domestic_cup_7d_sourced_subset'])][['season','group','rows','minute_MAE','minute_bias','start_Brier','p60_Brier','p90_Brier','p90_bias']]
    ora=read('oracle-group-metrics.csv');ora=ora[ora.group.eq('pregame_start_at_least_20pct')][['season','mask','rows','xp_MAE','xp_RMSE','xp_bias','goal_MAE','assist_MAE','CS_Brier']]
    attr=json.loads((OUT/'oracle-interactions.json').read_text());attr=pd.DataFrame([dict(season=r['season'],factor=r['factor'],MAE_reduction=r['Shapley_MAE_reduction'],CI95=f"[{r['fixture_bootstrap95'][0]:.4f}, {r['fixture_bootstrap95'][1]:.4f}]")for r in attr if 'Shapley_MAE_reduction'in r])
    cases=read('mc-control-cases.csv')[['name','draws','xp_mean','xp_SD','SD_low95','SD_high95']]
    rank=read('mc-ranking-stability.csv').groupby('draws').agg(top20_overlap=('top20_overlap','mean'),top5_overlap=('top5_overlap','mean'),captain_changed_pair_rate=('top_captain_changed','mean')).reset_index()
    comps=read('current-control-components.csv');events=read('position-event-totals.csv');ts=json.loads((OUT/'historical-TS-cases.json').read_text());tsdf=pd.DataFrame([dict(GW=r['gw'],FT=r['FT'],bank=r['bank_tenths']/10,players=r['universe'],exact_squads=r['exact_squads'],fast_squads=r['fast_squads'],pruning_loss=r['utility_regret'],joint_XI_gain=r['XI_gain'],fast_seconds=r['fast_seconds'],exact_seconds=r['exact_seconds'],financing_cases=r['negative_financing_bundles'])for r in ts]);bench=pd.DataFrame([json.loads((OUT/f'benchmark-{n}.json').read_text())for n in [400,2000,10000]])[['draws','kernel_seconds','simulation_seconds','process_peak_RSS_KiB','json_payload_bytes']]
    uncertainty=json.loads((OUT/'fixture-sampling-uncertainty.json').read_text());ints=[]
    for r in uncertainty:
        q=r['intervals']['xp_abs_error'];ints.append(dict(season=r['season'],cohort=r['cohort'],rows=r['rows'],MAE=q['mean'],CI95=f"[{q['fixture_bootstrap95'][0]:.4f}, {q['fixture_bootstrap95'][1]:.4f}]"))
    decisions=json.loads((OUT/'mc-decision-stability.json').read_text());rows=[]
    for n in [400,2000,10000]:
        g=[r for r in decisions['rows']if r['draws']==n];rows.append(dict(draws=n,distinct_XI=len({tuple(sorted(r['XI']))for r in g}),distinct_C=len({r['captain']for r in g}),distinct_VC=len({r['vice']for r in g}),distinct_transfers=len({(tuple(r['chosen_incoming']),tuple(r['chosen_outgoing']))for r in g})))
    md=f'''# FPL Analytics – samlet præcisionsaudit af MM → PM → TS

**Auditdato:** 1. november 2026. **Reference:** `736d65cacc1afeeaf8c3dcfad317d7ee745b48fa`.
**Branch:** `audit-systematic-precision-20261101`. **PR:** https://github.com/pdamkier-del/fpl-analytics-app/pull/29.

Auditten ændrer ingen modelparametre, app, låst PM, TS v3, produktion eller B-preview.
Der er ingen ny præcisionsforbedring aktiveret eller dokumenteret på uafhængige udfald.

## Konklusion og fejlsteder

| Led | Dokumenteret fund | Hvad det begrunder som næste test |
| --- | --- | --- |
| Datagrundlag | 341 genbrugte kampe, 27.092 spiller-kamp-observationer; ingen bevist uberørt historisk periode | Brug den nu låste fremadrettede prognoselog til reel evaluering |
| MM | Minut-MAE 10,86 / 10,28; rotationsspillere cirka 27; returer undervurderes 7,83 / 7,21 min; stamspilleres P(90) er 8,82 / 6,18 procentpoint for høj | Undersøg returforløb og kalibrering af start/varighed, før nye parametre vælges |
| PM/simulation | Ved 400 draws varierer Penders og Le Fées xP med SD 0,175 / 0,154 alene mellem seeds | Flere draws og parrede sammenligninger før små modelændringer fortolkes |
| Holdmål → PM | Facit-holdmål reducerer aktiv-kohortens xP-MAE fra 1,93 til 1,52 og 2,11 til 1,70 | Test holdmåls-*kalibrering*, ikke indsættelse af realiserede mål; facit fjerner også uforudsigelig kampvariation |
| Individuel PM | FWD-assists undervurderes i begge sæsoner; positions- og rollefejl udligner hinanden i samlet bias | Undersøg FPL-assistdefinition, eksponering og rollebaseret fordeling før ny afslutningsevne-model |
| TS | Ingen pruning-tab i seks afgrænsede FT-cases fra tre historiske tilstande; fælles XI/bænk/C/VC gav 0,18 xP i én tilstand | Lille evidens for praktisk gevinst; ingen begrundelse for ny TS nu |

Dette er fejlstruktur og diagnostiske facit-indgreb, **ikke** et estimat af en opnåelig procentvis forbedring. Rotationsspillere har også naturligt høj minutusikkerhed; høj MAE alene beviser ikke fejlkalibrering.

## 1. Historik, informationscutoff og scope

171 kampe fra 2024/25 og 170 fra 2025/26, GW22–38. Begge perioder er allerede brugt i forskning. Featurehistorik, arbejdsbelastning og GK-estimator rekonstrueres med observationer kendt før hvert origin. GK-fitkontrollen består for alle 341 kampe, og 682 hold-kampe har præcis samlet startmasse 1 og 90 forventede målmandsminutter.

Den eksisterende NP-målfordeling er fit på **2025/26 GW16–21, 4.670 rækker**. Derfor er 2024/25 en betinget retrospektiv robusthedskontrol, ikke kronologisk out-of-time. 2025/26 er senere i tid, men genbrugt under udvikling. Hele fit-proveniensen for nedarvede holdmål-, assist-, BPS-, save-, DC- og disciplinhoveder er ikke bevist af de afledte input. Cutoff-sikre features alene beviser ikke cutoff-sikre parametre. Se `parameter-provenance.json`.

Historiske offentliggørelsestidspunkter bruger blandt andet +3/+4 timers proxies efter kampe. Cup/UEFA-dækning er et dokumenteret kildeudsnit. Landsholdsminutter og komplette kliniske oplysninger er ikke tilgængelige. Det er begrænsninger, ikke nuleffekter.

Det gamle prepared-task-cache havde ikke den nuværende sole-GK-v2-policy. Auditten rekonstruerer den eksisterende estimator på fortidsprefixer med samme arkitektur. V2 havde særskilte tests tidligere; denne audit påstår ikke, at den aldrig var testet. Første aktuelle kamp reproducerer den publicerede B-prognose **eksakt, maksimal xP-afvigelse 0**, fra det forseglede origin-input.

Baseline (gennemsnit af tre uafhængige 400-draws-kørsler):

{table(base)}

Den fulde trup indeholder mange reserver med forventet/faktisk nul. Derfor vises også den på forhånd definerede kohorte **P(start) ≥ 20 %**:

{table(pd.DataFrame(ints))}

Intervallerne er 4.000 fixture-cluster bootstrap-resamples. Gentagne spillere og fælles GW-/modelchok kan give yderligere afhængighed; intervallerne er ikke komplet model-/parameterusikkerhed.

## 2. Facitdiagnostik: minutter, XI og holdmål

298/341 kampe kan danne et lovligt normalt minutforløb ved eksplicit rekonstruktion. 39 kampe med rødt kort og fire med over fem faktiske udskiftninger udelades fra oracle-kohorten. Rå FPL-minutter danner et præcist fysisk 0–90-forløb i **0/341** kampe; de faktiske ind-/udskiftningstidspunkter er alle manglende i Core.

Derfor benyttes to ure: faktiske FPL-minutter fastholdes præcist til point, 60+-grænse, saves/DC/BPS; et separat fysisk ur parrer spillere og samler udskiftningsvinduer under reglerne. Det fysiske ur er en rekonstruktion, ikke observerede tidspunkter. M alene udleder startere fra varigheder og pregame-p ved lighed; M+S bruger faktisk XI. Minutter indeholder dermed allerede meget startinformation.

G betinger den oprindelige Bernoulli-selvmåls-/Poisson-mål-/straffesparksproces på **præcis det faktiske holdresultat ved hvert minutforløb**. Det er ikke Poisson(lambda=faktiske mål), og ikke en ny posterior for alle mulige startopstillinger. Straffesparksmissere er den uafhængigt udtyndede proces. Ingen facitoplysninger eksporteres som fremtidige prognoser.

24 kvalificerede kampe pr. sæson vælges jævnt i GW/UUID-rækkefølge uden brug af fejlstørrelser: 48 kampe, 3.827 spillerobservationer. Alle otte arms har samme kohorte og tre 400-draws-repetitioner. Masker: M=1, S=2, G=4; kombinationer er bit-summer. Tabellen nedenfor viser den aktive pregame-kohorte; alle trup-, positions-, rolle- og eventmål findes i CSV-filerne.

{table(ora)}

MAE-baserede Shapley-bidrag på den **fulde** fælles oracle-kohorte, som fordeler overlap:

{table(attr)}

Summen af separate M-, S- og G-gevinster overvurderer den fælles gevinst med 0,0417 xP i 2024/25 og 0,1272 i 2025/26 pr. trupobservation. Derfor må de ikke lægges sammen. Se `oracle-interactions.json`. M og S overlapper især kraftigt.

G-oracle fjerner også irreducibel kampvariation; en stor gevinst beviser ikke, at holdets forventede mål er dårligt modelleret. Selv alle tre facit-input efterlader cirka 1,16 / 1,11 MAE i aktiv-kohorten fra individuel hændelses-/pointvariation og resterende modelfejl. Det er ikke et rent mål for fejl i spillerfordelingen.

Oracle-arms genstarter separate minut- og eventstreams med fælles udgangsseeds pr. draw. Konditionering bruger forskellige antal tilfældige tal; det er **delvis CRN**, ikke fuld hændelsesvis parring. `oracle-MC-metric-repetitions.csv` viser målevariation mellem hele repetitionsindeks; `oracle-seed-metrics.csv` bevarer de enkelte fixture-seeds.

## 3. Monte Carlo-støj og anbefalet antal draws

14 kampe: alle ti aktuelle GW10-kampe og fire historiske kontrolkampe fra GW24/GW32. Seks uafhængige seeds pr. kamp, 10.000 draws hver; 400 og 2.000 er præcise indlejrede prefixes. Observatøren bruger ingen RNG. Samlet hovedaudit: **2.259 kørsler og 1.710.000 simulerede kampe**, uden at tælle prefixes dobbelt.

SD er variation i estimeret xP mellem seeds, ikke spillerens pointusikkerhed i en rigtig kamp. SD-intervaller er chi-kvadratintervaller med kun fem frihedsgrader og derfor brede:

{table(cases)}

Aktuelle rangeringer, gennemsnit af alle 15 seed-par:

{table(rank)}

Én fast, lovlig modelkonstrueret trup; 24 spillere i den faste afgrænsning, 20 lovlige nul/én-transfermuligheder. Antal forskellige anbefalinger mellem de seks seeds:

{table(pd.DataFrame(rows))}

Selv 10.000 draws kan ændre vicekaptajn og en meget tæt transfer. Dette er én tilstand med ét-GW-mål, ikke seks-GW TS-policy-performance. Truppen er konstrueret fra gennemsnittet af 6×10.000 draws, fastholdt på tværs af N; ingen observerede udfald indgår.

Isolerede procesmålinger af **den oprindelige app-simulator**, med distributioner og TS-scenarier, første aktuelle kamp:

{table(bench)}

RSS omfatter Python og ti indlæste inputkampe, ikke kun ekstra draw-arrays. Tiderne er én måling pr. N under CPU-konkurrence, ikke en præcis skaleringsbenchmark. Se også alle 84 worker-receipts; deres RSS er for hele 10.000-draws-workerprocessen og må ikke forveksles med isoleret hukommelse ved 400/2.000.

**Anbefaling til efterfølgende implementeringstest:** 2.000 draws som almindeligt xP-estimat; 10.000 til validering og tætte beslutningssammenligninger med fælles draws. 400 er egnet til hurtig diagnostik, ikke til at tolke små xP-forskelle som modelgevinst. Brug observeret parret MCSE og vis usikkerhed ved meget tætte valg. En højere N øger ikke automatisk prædiktiv præcision.

Send ikke ukritisk alle 10.000 rå scenarier til browseren: kontrollens payload er cirka 4,5 MB pr. kamp mod 0,25 MB ved 400. 60 lignende kampe ville være omkring 270 MB før kompression. Backend-opsummering/lagring og TS-forbrug skal testes separat. Ingen af disse ændringer er aktiveret nu.

## 4. Penders og Le Fée

Aktuel kilde: publicering `41278968979`, data 1. november kl. **07.20 dansk tid**, seal `fac23927…bfbafb`, GW10. Sunderland–Chelsea: forventet holdmålbudget **1,5942–1,5578**.

Gennemsnit af seks 10.000-draws-repetitioner:

{table(comps[['name','analytic_minutes','points','minutes','started','p60','p90','goals','assists','clean_sheet']])}

Pointregnskab, præcist afstemt med xP uden dobbeltoptælling:

{table(comps[['name','appearance_pts','goal_pts','assist_pts','cs_pts','save_pts','penalty_save_pts','dc_pts','negative_pts','gc_pts','bonus']])}

Le Fées 4,1761 xP skyldes især høj spilletid, 0,2008 forventede mål og 0,2418 FPL-assists. Den ordinary-goal-vægt er 0,1319, assistvægten 0,2965, penalty-order 2. Vægte er **ikke isolerede sandsynligheder**; de normaliseres blandt reelt aktive konkurrenter. Hans høje niveau er ikke kun straffespark eller bonus. Det beviser ikke individuel overprognosticering før kampen er spillet.

Penders: cirka **85,78 PM E[min], 95,51 % start, 95,26 % 60+, 94,88 % 90 og 3,0314 xP** som sample-estimater. Han kan ikke få præcis 90 forventede minutter samtidig med positiv reserve-/tidlig-exit-sandsynlighed. Hans publicerede 400-draws-xP på 2,735 og Le Fées 4,230 er en bestemt seed-realisering; nye seed-gennemsnit er ikke dokumenterede model-forbedringer. De originale input og publicerede værdier står i `current-control-inputs.json`.

## 5. Individuel mål- og FPL-assistkalibrering

Sum af forventede/faktiske events på tværs af samtlige spiller-kampe:

{table(events[['season','position','goals','actual_goals','assists','actual_assists']])}

Samlet næsten nul bias skjuler blandt andet underprognoser for FWD-assists i begge sæsoner og modsatrettede positionsskævheder. Det bør efterprøves med en ægte ny evalueringsperiode, ikke rettes med et vilkårligt FWD-tillæg.

`event-calibration.csv` indeholder P(≥1 mål), P(≥1 FPL-assist) og clean-sheet-bins på position, startrolle og taktisk rolle. Små bins markeres. `individual-season-calibration.csv.gz` viser hver spillers faktiske G/90 og xG/90 samt forventede G/90/A/90 pr. forventet minut. Samlede minutter, mål, assists og point er bevaret, så lave eksponeringer ikke skjules. Spillerens individuelle usikkerhed kan være stor; ikke alle spillere har nok minutter til en meningsfuld effektivitetskonklusion.

Oracle-tabellerne viser også ændringer i mål/assists/CS, når minutter/holdmål kendes. Ingen ny finishing-model eller navnespecifik tuning er testet eller anbefalet på dette grundlag.

Holdets målbudget indeholder ordinary goals, scorede straffespark og modstanderens selvmål. Individuelle ordinary-goal-/assists-vægte normaliseres blandt kvalificerede spillere på banen. Standardhovedet kan ikke skabe en vilkårlig ekstra pulje af assists uafhængigt af holdmål. `team-goal-assist-budgets.csv` sammenholder budget, spillermål og FPL-assists for alle 682 hold-kampe. Forventede krediterede spillermål kan være lavere end inklusive holdmål på grund af selvmål; finite-N-gennemsnit er heller ikke præcist lambda.

Den eksisterende B-eventkode giver højst én kvalificeret assist pr. scoret event og forbyder selv-assist. Pointregnskabet holder missed penalties inden for negative point. Særlige FPL-assists ved fremtvunget straffespark/selvmål har ingen separat verificeret forekomstkilde i det forseglede input og er markeret som unsupported mekanisme i simulatorens trace. Der bruges faktisk **FPL-assist-label** (`fpl_assists`), ikke almindelige assist-labels. En historisk FPL-regelændring må ikke fortolkes som spillerform uden særskilt regel-/kildekontrol.

## 6. Minutfejl og sandsynligheder

Roller defineres på forhånd: regular P(start)≥0,90; rotation 0,20–0,90; reserve <0,20. Gruppeoverlap må ikke summeres. Medical-out er den historiske predeadline-kliniske flagkolonne, ikke alle OUT-statusser; tilbagevenden er eksisterende `return_active`. Høj belastning er mindst 180 dokumenterede minutter sidste syv dage. UEFA-/cupnavne er normaliseret på tværs af sæsonkilder.

{table(small)}

Start-bias samlet er automatisk cirka nul, fordi modellen og faktisk XI begge summerer til 11 startere pr. hold. Det er **ikke** individuel kalibrering. Start/60+/90-Brier og undergrupper er derfor vigtigere. P(90) evalueres mod FPL's 90-minutterslabel; forskellen mellem scoringsuret og fysisk spilletid skal undersøges før varighedsparametre ændres.

Retur-underestimering på cirka 7–8 minutter og overvurderet P(90) for sikre startere ses i begge sæsoner. Høj-load-gruppen er lille (220/90 observationer) og har positive minut-/P90-bias. Cup/UEFA er selekterede kildeudsnit, ikke en fuld optælling. Der er ingen parameteroptimering i denne audit. Alle positioner, klubber og taktiske roller står i `minute-error-structure.csv`.

## 7. TS: praktisk søgetab og præcise begrænsninger

Tre modelkonstruerede lovlige historiske tilstande ved GW24/28/32, hver med én og to gratis transfers. Første trup vælges fra de foregående tre observerede kampe før forrige deadline, budget £100m, købspriser fra forrige GW. Salgspriser, positionskrav, max tre pr. klub og hits er bevaret. Ingen faktisk managers bank/priser/hold er opfundet.

Trupkonstruktionen er afgrænset til overlap med de tilgængelige target-prognoser. Derfor er det en **betinget, realistisk konstrueret beslutningsdiagnostik**, ikke en verificeret menneskelig transferhistorik eller en uafhængig policy-backtest. Priskildens server-publiceringstidspunkt er ikke uafhængigt verificeret. NP-headens fremtidige træning i forhold til 2024 gør også disse tilstande retrospektive.

Fast og eksakt transferreference bruger samme afgrænsede kandidatunivers og samme eksisterende B-lineup-scorer. Separat søges alle lovlige XI'er, bænkordrer og C/VC for den oprindelige 15-mandstrup. Det er ikke ét globalt eksakt optimum for alle transferkombinationer plus fælles lineup over seks GW.

{table(tsdf)}

Den eksakte transferkontrol fandt **0/6** pruning-tab i disse seks FT-cases, fra kun **tre** forskellige tilstande; ikke seks uafhængige historiske eksempler. Ingen negativ finansieringskombination var nødvendig/til stede i den afgrænsede positive-gain-definition. Derfor kan auditten **ikke estimere den praktiske hyppighed eller gevinst af negative finansieringsben**. Kontantbeholdningerne er relativt høje. Den strukturelle begrænsning findes stadig i v3-koden: et enkelt ben med negativ vægtet spillerværdi frasorteres før en samlet pakke vurderes. En syntetisk kontrakttest beviser, at den eksakte reference tillader et lovligt negativt finansieringsben; legetesten tæller ikke som historisk præcisionsevidens.

Fælles XI/bænk/C/VC giver 0,18 xP mere i GW32-tilstanden, nul i de to andre. Tre tilstande og 400 scenarier er for lidt til at påstå generaliserbar policygevinst. Scenariebaserede søgetab er in-sample i den afgrænsede scenariomatrice og kan være følsomme for MC-støj. Ikke en ekstra out-of-sample performance-test.

Fuld historisk seks-GW-evaluering mangler: det eksisterende horizon-audit har **33 af 183** nødvendige ægte origin-target-celler. Det kræver komplette seks-GW-prognoser fra hvert oprindeligt cutoff, tilhørende fælles scenarier og komplette pris-/bank-/købspris-/chiptilstande. Senere-origin-prognoser må ikke genbruges som tidligere viden. Manglen omgås ikke med en falsk historisk forecastkæde.

## 8. Usikkerhed, ny uafhængig test og prioritering

`fixture-sampling-uncertainty.json` rapporterer fixture-sampling; `baseline-MC-metric-repetitions.csv`, `oracle-MC-metric-repetitions.csv` og `mc-individual-noise.csv.gz` rapporterer simulationsstøj. Bootstrap af tre-seed-gennemsnittet indeholder lidt resterende MC-støj; den er ikke analytisk dekonvolveret. Intervaller inkluderer ikke fuld parameter-/datakildeusikkerhed. Mål-/assistkalibrering i små rollegrupper er beskrivende, ikke bevis for systematiske effekter.

Fremadrettet er den **første** forseglede GW10–15-prognose låst med SHA-kæde og offentligt commit-/CI-tidspunkt, før GW10-deadline 6. november kl. 19.30 dansk tid. Primær evaluering er næste GW fra hvert origin; senere horisonter evalueres separat. Regel, nulminutspillere, metrics og manglende labels er frosset i `prospective/EVALUATION.md`. Ingen udfald findes endnu, og loggen er derfor endnu ikke dokumentation for højere præcision.

Prioriteringen følger potentiale × evidens / kompleksitet. Skalaerne nedenfor er **ordinale vurderinger** (1–3), ikke estimerede xP-gevinster; opnåelig præcisionsgevinst er ukendt. Monte Carlo-tiltaget forbedrer måling/stabilitet, ikke nødvendigvis prognosemodellen.

| Rækkefølge | Præcis næste test | Potentiale P | Evidens E | Kompleksitet C | P×E/C | Beståkrav |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Brug mindst 2.000 draws og 10.000/parrede draws ved små kandidatforskelle; test kompakt backend-levering | 2 | 3 | 1 | 6,0 | Lavere måle-/beslutningsstøj på faste uafhængige seeds; acceptabel latency/RSS/payload |
| 2 | Undersøg eksisterende returkalibrering og fuldkampsfordeling separat, med eksplicit FPL-/fysisk minutur | 3 | 2 | 2 | 3,0 | Lavere minut-MAE og start/60+/90-Brier i ny låst periode; xP må ikke forringes |
| 3 | Kontroller holdmålkalibrering før individuel fordeling, med dokumenterede gratis predeadline-input | 3 | 1 | 2 | 1,5 | Bedre holdmål-/CS-kalibrering og samlet xP i ny periode; oracle-gevinsten alene er ikke nok |
| 4 | Undersøg FWD-assistunderskud, FPL-regler og minuteksponering; behold fælles målbudget | 2 | 2 | 3 | 1,3 | Stabil probabilistisk forbedring i begge sæsondiagnostikker og fremadrettet; ingen navnetuning |
| 5 | Udvid TS-diagnostik med dokumenterede lav-bank-tilstande og ægte seks-GW-originprognoser | 1 | 1 | 3 | 0,3 | Gentageligt nettopointløft mod eksakt reference; regnetid og MC følsomhed rapporteres |

Ingen ny finishing-, assist-, minut- eller transfermodel implementeres før disse tests. Fysisk korrekte start-/minut-/udskiftningsregler forbliver gældende uafhængigt af præcisionsgevinsten.

## 9. Reproduktion, tests og levering

Se [reproduktionsvejledningen](../analysis/precision_audit/README.md) og [alle numeriske resultater](../analysis/results/systematic-precision-audit-20261101/). Frosne input inkluderer eksplicit facit til diagnostik og må aldrig sættes på forecast-endpointet. Ingen private managerdata indgår.

**Lokale tests:** 42 relevante oracle-/log-/eksakt-reference-/B-event-/fysisk-tidslinje-/GK-regressionstests består. Eksakt historisk replay fra det frosne beslutningsgrundlag består for alle seks FT-cases. Aktuel original B-replay har xP-afvigelse 0. `git diff --exit-code 736d65ca -- src scripts app model service` består.

**CI:** særskilt auditworkflow tester kontrakter, kontrollerer uændret produktions-/appkode og eksisterende publiceringsworkflows, genkører baseline og samtlige otte oracle-arms for en frossen kamp og sammenligner draw-metrics med de arkiverede resultater. Hele 341/48/14-kampsauditten er kørt lokalt; CI-smoke er ikke fejlagtigt betegnet som en fuld CI-genkørsel. Se PR'ens checks og auditworkflowets artifact.

**Ingen produktion eller ny B-preview er publiceret.** Leverancen er rapport, reproducerbar audit, frosne resultater og PR #29, som bestilt.
'''
    path=ROOT/'docs/2026-11-01-systematic-precision-audit.md';path.write_text(md);print(path)
if __name__=='__main__':main()
