#!/usr/bin/env python3
"""Render the executed priority experiment; no fitting or production imports."""
from pathlib import Path
import pandas as pd,numpy as np,json
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'analysis/results/mm-club-importance-20261016'

def table(headers,rows):
    def val(v):
        if v is None or pd.isna(v):return 'Not Available'
        if isinstance(v,(float,np.floating)):return f'{v:.5f}'
        return str(v)
    return '| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'+'\n'.join('| '+' | '.join(val(v)for v in row)+' |'for row in rows)+'\n'


def main():
    metrics=pd.read_csv(P/'validation_metrics.csv');selection=pd.read_csv(P/'hyperparameter_selection.csv');samples=pd.read_csv(P/'match_samples.csv');observed=pd.read_csv(P/'observed_club_priorities.csv');priorities=pd.read_csv(P/'club_priorities.csv');months=pd.read_csv(P/'monthly_priorities.csv');cal=pd.read_csv(P/'calibration.csv');raw=pd.read_csv(P/'sample_coverage.csv')
    scalar=metrics[metrics.contrast_before.isna()]
    from experimental_club_match_importance import block_interval
    predictions=pd.read_csv(P/'validation_predictions.csv.gz',low_memory=False)
    overall=[]
    for (role,outcome),g in predictions.groupby(['role_definition','outcome']):
        keys=['club','match_id','cutoff']+(['player_id']if outcome=='normal_player_started'else[])
        base=g[g.model.eq('control')][keys+['prediction']]
        for model,h in g[~g.model.eq('control')].groupby('model'):
            j=h.merge(base,on=keys,validate='one_to_one',suffixes=('','_baseline'))
            error=(j.prediction-j.observed)**2-(j.prediction_baseline-j.observed)**2 if outcome=='normal_player_started'else abs(j.prediction-j.observed)-abs(j.prediction_baseline-j.observed)
            overall.append(dict(role_definition=role,outcome=outcome,model=model,group='all',**block_interval(j.cutoff,error)))
            if outcome=='normal_player_started':
                av=j.explicit_available.astype(str).eq('True')
                overall.append(dict(role_definition=role,outcome=outcome,model=model,group='explicit_predeadline_available',**block_interval(j.loc[av,'cutoff'],error[av])))
    data_dir=ROOT/'docs/research/data';data_dir.mkdir(exist_ok=True)
    pd.DataFrame(overall).to_csv(data_dir/'2026-10-16-importance-overall-contrasts.csv',index=False)
    parts=['''# Klubspecifik og dynamisk match importance: historisk kandidatstudie

Dato: 2026-10-16. PR #8, `research-role-injury-club-audit-20261016`.

## Beslutning

Behold den eksisterende kontrolmodel og produktions-MM. **Ingen importance-kandidat har dokumenteret en robust samlet forbedring af rotation og individuel spilleranvendelse.** Historisk brug af normale startere er en nyttig indikator; det er ikke tilstrækkelig dokumentation for en generel importance-komponent i MM.

Den dynamiske kandidat forbedrer ét defineret respons med objektive roller: andelen af de historiske normale startere i XI. Gevinsten holder ikke med eksisterende rolleprofiler og oversættes ikke til bedre individuelle startchancer. Klubspecifik historik giver heller ikke en robust marginal gevinst. Det er et forskningsresultat, ikke en produktionsgodkendelse.

**Fuld MM-simulation er ikke kørt.** PM, TS, FPL-point og chips er ikke kørt eller ændret. `locked_model_active=false`. Alle eksporterede importance-prognoser har `deadline_correct=false` og afvises af den strikte MM-featurelæser.

## 1. Fortsættelse fra eksisterende forskning og datagrænser

Reference: `docs/research/2026-10-16-mm-match-importance-results.md`, commit `b97d7c1`. Det tidligere inventar indeholder 35.735 spillerobservationer, 1.840 holdkampe og 1.743 komplette XI'er. Den tidligere XI-MAE 1,550→1,472 var en separat rotationsanalyse, ikke forbedring af MM.

Dette forsøg genbruger den stabile 2024/25-del: **19.600 spillerobservationer og 1.033 komplette hold-XI'er**. Der dannes 898 analyserbare holdkampe pr. rolledefinition efter minimum tre tidligere PL-kampe og mindst 11 tidligere kendte spillerprofiler. 398 ligger før januar 2025; 500 i senere evaluering. Samme 500 holdkampe bruges af alle kandidater og begge rolledefinitioner. Der er 5.500 evalueringsrækker med tidligere definerede normale spillere pr. rolledefinition.

2025/26 er **ikke** en ny sammenlignelig multi-competition-validering: FA Cup mangler, 40 europæiske source keys er i karantæne, europæiske XI'er mangler stabile ID'er, og nogle kickoff-/returkampversioner er fejlbehæftede. De 760 komplette PL-XI'er udfylder ikke de manglende tværturneringshistorikker. Vi hævder derfor ingen nye klubprioriteter eller modelresultater for 2025/26. Den eksisterende 280-rækkers dækningsmatrix bevares.

2024-kilderne har kickoff + fire timer som publiceringsproxy; faktisk publicering og historiske program-/faseversioner er ikke verificeret. Fase, normalroller og standings behandles derfor som **diagnostiske pre-kickoff/pre-deadline-konstruktioner**, ikke certificerede historiske forecasts. FPL-deadline bruges, hvor den eksisterende historiske MM har den; ellers markeres cutoff som pre-kickoff-diagnostik.

## 2. Hvad måler prioritet?

Der bruges ingen håndvalgt stjernespillerliste. En normalspillerkurv er de 11 spillere med størst **tidligere startchance × tidligere betinget startervarighed** blandt historisk kendte PL-spillere i klubben. Kurven beskriver et brugshierarki, ikke talent, den stærkeste lovlige XI eller en opstillingsprognose.

To rolledefinitioner testes separat:

1. **Objektiv historisk rolle:** starter-/bænkselektion i tidligere PL-kampe og kendte starterminutter. Eksisterende forskningspriors genbruges: startprior 0,65, eksponering 8, startervarighedsprior 77 minutter, eksponering 5, tids-halvering 180 dage. Ukendte bænkminutter udfyldes ikke. Fravær uden dokumenteret kampdagsselektion tilføjer hverken en start eller en taktisk bænkobservation.
2. **Eksisterende rolle:** den tidligere MM's bevarede normale startchance og startervarighed, kun når deres as-of er før cutoff. Manglende eksisterende profiler falder tilbage til den objektive profil; fallback-dækning vises nedenfor. Der findes ikke en yderligere verificeret historisk stjerneetiket, som vi kan indsætte uden at opfinde den.

Aktuel opstilling/minutter indgår **kun som labels**. Objektiv normalrolle bygger primært på PL for at undgå, at bevidst brug af cupreserver i sig selv gør dem til normale PL-startere. Historisk, eksplicit navngiven bænk bruges som tidligere kampdagsselektion; det er ikke en klinisk helbredsattest.

Aktuel tilgængelighed kommer kun fra kildekontrollerede, fixture-/deadline-matchede FPL-observationer. Gammel AVAILABLE videreføres aldrig til en cupkamp. Ukendt fravær, skader, suspensioner og transfers blandes ikke sammen som bevidst hvile. Normalrollen bevares under fravær; dokumenteret utilgængelighed er en separat kontrol. Historiske registreringer/transferdatoer er ikke fuldt verificerede, så `transfer_registration_verified=false`.

Responsvariable:

- `normal_share`: andelen af den før kampen fastlagte 11-spillerkurv, der starter. Ukendt fravær kan påvirke responsen; det er en **observeret selektionsintensitet**, ikke ren bevidst prioritet.
- `xi_changes`: ændringer fra forrige registrerede XI, forskelligt fra indskiftninger under kampen.
- `normal_minute_share`: normale spilleres andel af registrerede holdminutter. Ukendte minutter og manglende events betyder, at dette ikke er verificeret komplet minutsallokering.
- Individuel startindikator for de 11 før kampen valgte spillere, rapporteret både samlet og særskilt for eksplicit pre-deadline AVAILABLE. Ukendt tilgængelighed rapporteres separat.

Rolledefinitionerne har forskellige spillerkurve og dermed forskellige starterandel-/startchance-targets. Sammenlign kandidater **inden for** hver definition. XI-skift er samme fælles respons på tværs af begge.
''']
    parts.append(table(['Rolledefinition','Analysekampe','Gns. andel eksisterende profiler','Ukendt tilgængelighed blandt normalspillere'],[[role,len(g),g.existing_profile_share.mean(),g.unknown_availability.mean()]for role,g in samples.groupby('role_definition')]))
    parts.append('''
## 3. Objektive forhold, historisk adfærd og dynamik

De ønskede A/B/C/D-metoder implementeres med isolerede delmodeller:

| Variant | Informationslag |
| --- | --- |
| control | Klub, tidligere XI-stabilitet, tidligere rollehierarki, hvile, registrerede holdminutter 7/14 dage, særskilt kendt/ukendt tilgængelighed |
| A_objective | control + turnering, registreret fase/runde, sæsontid, historisk PL-placering/point pr. kamp, afstand til top/bund og modstanderens tidligere PL-point pr. kamp |
| B_global_history | control + fælles turneringseffekt og tidligere normalspillerbrug på tværs af klubber i turneringen |
| B_club_history | B_global + klubbens egen turneringshistorik og regulariseret klub×turnering-effekt |
| C_combined | A + B_club |
| D_dynamic | C + seneste tre kendte turneringsobservationer, forskel til klubbens PL-brug, ændring fra lang historik og en regulariseret klub×turnering×sæsontid-effekt |
| D_individual | D + normale spilleres belastning/hvile, rollevariation og profildækning som yderligere holdkontroller |

Alle individuelle startmodeller har derudover den konkrete spillers tidligere rolle, startervarighed, registrerede 7/14-døgnsminutter og hvile. Dermed sammenlignes importance-lagene med en kontrol, der allerede kender individuel rolle/belastning. D_individual tester den ekstra **fordeling af belastningen i normalspillerkurven**, ikke blot om vi husker at give kontrolmodellen spillerdata.

PL-stillingen rekonstrueres kun fra tidligere PL-resultater, der passerer +4t-proxyen; ved lige point bruges målforskel og scorede mål, og helt lige hold har samme provisoriske placering. Dette er almindelige ligapoint, **ingen FPL-pointberegning**. Klubbens ambitioner, kampens sande avancementsandsynlighed og trænerintention tilskrives ikke. Uverificerede samlede duelstillinger, næste kendte kamp, fremtidige sportslige udfald og fremtidige opstillinger indsættes ikke.

A er derfor en **tilgængelig sportslig proxy**, ikke en fuldt verificeret objektiv importance-sandhed. D er en dynamisk adfærdsmodel på de tilgængelige tidligere kampe, ikke en fuld optimering af et verificeret fremtidigt turneringsprogram.

## 4. Matematik, identifikation og usikkerhed

For et holdrespons bruges en penaliseret lineær model:

\\[
y_m=b+a_c+\\alpha_t+u_{ct}+\\beta^\\top X_m+\\gamma^\\top H_{ct,<m}+v_{ct}s_m+\\epsilon_m.
\\]

Kun de led, der hører til den pågældende variant, medtages. Klub-/turneringsinteraktioner regulariseres mod nul og dermed mod den fælles turneringseffekt. Estimation minimerer kvadreret fejl plus `alpha × sum(coef²)`; dette kan fortolkes som et hierarkisk Gaussian-prior/MAP-lag med fælles regularisering. Det er ikke en fuld empirisk Bayes-model med estimeret separat varians for hver klub. Få cupkampe giver ikke en fri, uregulariseret klubparameter.

En logistisk model med de samme informationslag bruges til den individuelle startindikator. Numeriske variable centreres og skaleres; sjældne kategorier bliver ikke opskaleret til samme varians som hyppige kategorier. Alpha vælges blandt 1/10/100 på december-data separat for hvert respons. Logistik vælges på Brier; kontinuerte responser på MAE. Ingen spiller-/klubspecifik manuel importance-vægt. Rollepriorernes 0,65 er en genbrugt starterprior, ikke en importance-score.

Rapporteret importance er en veldefineret **prognosekontrast i procentpoint**:

\\[
I_m=100\\{\\hat y_m(\\text{aktuel turnering/historik})-\\hat y_m(\\text{samme klub, PL-reference})\\}.
\\]

PL sættes dermed til nul inden for hver klub. Det er en rå lineær modelkontrast, ikke en kausal effekt og ikke en absolut psykologisk skala. **−20 betyder 20 procentpoint lavere modelestimeret normalstarterandel relativt til PL-referencen; det er ikke 20 % mindre vilje til at vinde.** Ingen subjektiv 0–100-skala bruges. Alle normale responsprognoser klippes til deres gyldige interval ved scoring; kontrasten vises i rå modelenheder.

Forskelle i evalueringsfejl får 1.000-draw cirkulær fireugers blok-bootstrap, der holder alle klubber/spillere i samme uge samlet. Prioritetsintervaller er et uge-cluster-sandwich omkring den penaliserede model, betinget på valgte features/alpha. Klubgennemsnittets kontrast får sin egen kovariansberegning; vi tager ikke blot et gennemsnit af enkeltkampenes standardfejl. Disse intervaller omfatter ikke ukendt kildekvalitet, alle modelvalg eller klinisk tilgængelighed. Hvis klub/turnering ikke findes i træning, beholdes det regulariserede prognosepunkt, men intervallet er **Not Available** frem for falsk sikkerhed om et uset effektled.

Conference League har kun Chelsea i disse PL-klubdata. En fri Chelsea-effekt kan ikke adskilles empirisk fra en fælles Conference-effekt dér; regularisering fastlægger en priorbaseret fordeling, ikke en identificeret klub-/turneringsårsag.

## 5. Kronologisk validering og faktiske resultater

Træning før 1. december 2024; alpha-valg i december; refit før 1. januar 2025; evaluering derefter. Historiske features opdateres med tidligere tilgængelige observationer, mens koefficienter fastholdes fra refit. Ingen aktuelle/fremtidige resultater kan indgå i egen featurehistorik.

Sæsonen er tidligere anvendt i forskning. De første kørsler i denne opgave fandt tab ved fælles alpha på tværs af responser; den endelige kørsel vælger derfor alpha separat pr. respons og retter numerisk centrering for logistisk konvergens. Det gør ikke senere data til et nyt uberørt holdout. Tallene er **genbrugt kronologisk forsknings-/evalueringsbevis**, ikke uafhængig produktionsvalidering. Der er ikke tunet særparametre til Chelsea, City eller andre klubber.
''')
    for role in ['objective','existing']:
        parts.append('\n### Rolledefinition: '+role+'\n')
        rows=[]
        for model,g in scalar[scalar.role_definition.eq(role)].groupby('model',sort=False):
            def get(out,key,group=None):
                z=g[g.outcome.eq(out)]
                if group:z=z[z.availability_group.eq(group)]
                return z.iloc[0][key]if len(z)else None
            rows.append([model,get('normal_share','mae'),get('normal_share','rmse'),get('xi_changes','mae'),get('xi_changes','rmse'),get('normal_minute_share','mae'),get('normal_player_started','brier','all_unknown_included'),get('normal_player_started','brier','explicit_predeadline_available'),get('normal_player_started','log_loss','explicit_predeadline_available')])
        parts.append(table(['Model','Normalandel MAE','Normalandel RMSE','XI MAE','XI RMSE','Minutandel MAE','Start-Brier alle','Start-Brier kendt AVAILABLE','Start-log-loss kendt AVAILABLE'],rows))
        contrasts=metrics[metrics.role_definition.eq(role)&metrics.contrast_before.notna()&metrics.outcome.eq('normal_share')]
        parts.append('\nMarginal værdi for normalstarterandel, negativ forskel er bedre:\n\n'+table(['Reference','Kandidat','MAE-forskel','95% lav','95% høj'],contrasts[['contrast_before','model','delta','low','high']].values.tolist()))
    parts.append('''
Samtlige numeriske responser, bias, RMSE, Brier/log-loss og parrede kontraster findes i `validation_metrics.csv`. Brier-kontraster er også beregnet særskilt for eksplicit AVAILABLE. `validation_predictions.csv.gz` giver alle 98.000 enkeltprognoser med observeret respons, model og cutoff, og `hyperparameter_selection.csv` alle før-evaluering-valg.

Den tidligere 1,550→1,472-XI-test har andre kontrolfeatures, responsspecifik modeludvælgelse og to flere evalueringskampe. Den må ikke bruges som direkte før/efter-resultat for dette forsøg.

### Kalibrering af individuelle startchancer
''')
    overall=pd.DataFrame(overall)
    picked=overall[overall.model.eq('D_dynamic')&((overall.outcome.eq('normal_share'))|((overall.outcome.eq('normal_player_started'))&overall.group.eq('explicit_predeadline_available')))]
    parts.append('\nDirekte D_dynamic mod kontrol (negativ forskel er bedre; starterandel bruger MAE, startchance bruger Brier):\n\n'+table(['Roller','Respons','Forskel','95% lav','95% høj'],picked[['role_definition','outcome','delta','low','high']].values.tolist()))
    rows=[]
    for (role,model),g in cal.groupby(['role_definition','model']):
        ece=np.average(abs(g.predicted-g.observed),weights=g.n);rows.append([role,model,ece,int(g.n.sum())])
    parts.append(table(['Roller','Model','ECE, 10 faste bins','Spillerkampe'],rows))
    parts.append('''
ECE er en bin-afhængig kalibreringsdiagnostik, ikke en proper scoring rule. Brier/log-loss vægtes højere ved vurderingen. `calibration.csv` viser antal, gennemsnitlig prognose og faktisk startrate for hvert bin. Udvalget er tidligere normale spillere, ikke alle klubbens reserver; der påstås ingen fuld MM- eller reservekalibrering.

## 6. Klubvis prioritet og observeret adfærd

Tabellen viser D_dynamic med objektive roller som **eksperimentel beskrivelse**, fordi netop denne variant gav den tydeligste normalstarterandel-gevinst. Den er ikke udvalgt som universel vinder. Tidligere normale spillere er defineret før hver kamp. Alle turneringer med rå observationer er med; manglende evaluering bliver Not Available.

Observeret normalandel/minutandel og XI-skift er hele det modellerbare historiske udvalg. Modelkontrast og interval gælder den senere evaluering. De forskellige perioder må ikke forveksles. De rå kampantal og manglende warm-up fremgår af `sample_coverage.csv`.
''')
    cp=priorities[priorities.role_definition.eq('objective')&priorities.model.eq('D_dynamic')].merge(observed[observed.role_definition.eq('objective')],on=['club','competition','role_definition'],how='left',suffixes=('','_obs'))
    parts.append(table(['Klub','Turnering','Rå kampe','Model-eval kampe','Observeret normalandel','Registreret normalminutandel','XI-skift','Relativ prioritet pp','Betinget 95% lav','Betinget 95% høj','Træningskampe klub/turnering'],cp[['club','competition','raw_team_games','evaluation_games','normal_starter_share','normal_minute_share','xi_changes','relative_priority_pp','conditional_low','conditional_high','training_club_comp_games']].values.tolist()))
    parts.append('''
### Chelsea, Manchester City, Arsenal, Liverpool, Aston Villa og Tottenham

Alle månedstal findes i `monthly_priorities.csv`. Nedenfor er de seks ønskede klubbers faktiske månedlige estimerede kontraster og observerede starterandele. Celler med få kampe er ikke en kausal ændringsanalyse. FA Cup findes først i den senere del af dette udvalg og har ofte ingen pre-januar-træning; intervaller mangler derfor med vilje. League Cup-kampe fra efteråret uden senere deltagelse giver ingen evalueret slutprioritet.
''')
    focal=['Chelsea','Man City','Arsenal','Liverpool','Aston Villa','Spurs']
    for club in focal:
        s=months[months.club.eq(club)&months.role_definition.eq('objective')&months.model.eq('D_dynamic')]
        parts.append('\n#### '+club+'\n\n'+table(['Turnering','Måned','Kampe','Estimeret relativ prioritet pp','Observeret normalstarterandel'],s[['competition','month','games','relative_priority_pp','observed_normal_share']].values.tolist()))
    parts.append('''
Dette er historisk anvendelse, ikke et bevis for, hvor meget en træner subjektivt går op i en turnering. Cupmodstanderes niveau, uobserverede skader og truppens bredde kan påvirke tallene. Betydningen af store føringer for nøglespilleres udskiftning kan ikke identificeres uden verificerede tidsbestemte kampstillinger og udskiftningshændelser. Der er ikke opfundet sådan en effekt.

## 7. Ren integrationsoverflade til næste MM-runde

`pre_match_features.csv.gz` indeholder kun prædiktorer, før-kamp-modellens estimat/standardfejl og metadata. Aktuel normalstarterandel, faktiske XI-skift og faktiske minutter er **fjernet**. Den deskriptive klubgennemsnits-standardfejl, der bruger evalueringsperiodens featurefordeling, er også fjernet fra før-kamp-output. Individuelle features er separat i `individual_pre_match_features.csv.gz`; aktuelle start-/minutlabels findes kun i forskningsfilen `individual_role_samples.csv.gz`.

Kontrakten indeholder klub-ID, turnerings-ID, kamp-ID, cutoff/cutofftype, model/rolledefinition, importance-estimat og usikkerhed, historiske rolle-/belastningsfeatures, kildereference, publiceringsfelt, sidste historisk kendte tidspunkt og deadline-indikator. Individuelle rækker indeholder kilden/tidspunktet for eventuel verificeret FPL-tilgængelighed.

`require_deadline_features()` afviser responskolonner, falsk deadline-indikator, manglende eller fremtidig verificeret publicering og fremtidig historik. **Ingen række passerer nu**: publicering/programversioner er ufuldstændige, så alle er diagnostiske. Der er ikke lavet en bagdør til den låste MM.

## 8. Svar på de afsluttende spørgsmål

- **Prioriterer klubber turneringer forskelligt?** Observeret normalspillerbrug og rotation varierer mellem klubber/turneringer. Det er ikke en isoleret kausal trænerprioritet. Frie klubspecifikke effekter har ikke robust marginal prognoseværdi her; få cupkampe og enkeltklub-Conference begrænser identifikation.
- **Ændrer prioriteringen sig?** Observeret brug og de dynamiske modelkontraster ændrer sig gennem sæsonen. Den dynamiske model hjælper objektivt defineret normalstarterandel, men ikke stabilt på tværs af rolledefinitioner og individuelle startchancer. Det er ikke generelt valideret importance-dynamik.
- **Giver egen klubhistorik ekstra værdi?** Ikke robust: det lille objektive starterandel-estimat omfatter nul i intervallet, og eksisterende roller forværres. Ingen begrundelse for en fri klubparameter pr. turnering i produktion.
- **Giver individuelle roller og belastning ekstra forbedring?** De er allerede med i kontrol/startmodellerne. D_individual giver enkelte gevinster, men ingen samlet robust forbedring af alle mål eller kendt tilgængelige spilleres startchancer.
- **Er data tilstrækkelige til troværdig fuld MM-simulation?** Ikke til en deadline-certificeret tværsæson/all-competition-test. 2025-hullerne, historiske publicerings-/programversioner, tie states, ukendte registreringer og tilgængelighed består. Ingen fuld MM er kørt i denne opgave.
- **Hvilken variant anbefales?** Behold kontrolmodellen med eksisterende rolle-/tilgængelighedslag som reference. Bevar D_dynamic med objektive roller som en isoleret sekundær kandidat til en fremtidig kildeafgrænset MM-ablation, ikke som ny produktionsmodel. Kræv især forbedring af individuel startkalibrering og korrekt tilgængelighed, før integration overvejes.

## 9. Tests og reproduktion

61 fokuserede MM-/datatests består lokalt, herunder ni nye tests for at den aktuelle XI/minutter/resultat ikke lækker ind i egne features, ukendt fravær ikke bliver verificeret hvile, fremtidig pooled historik afvises, ukendte bænkminutter ikke opfindes, PL-ankeret er præcist nul, og den strikte læser fejler lukket. Klassifikatorer, der ikke konvergerer, får hele kørslen til at fejle.

```bash
pip install -r requirements-model-checkpoint.txt -r requirements-model-tests.txt requests
python scripts/restore_core_checkpoint.py
python scripts/restore_2024_25_data_checkpoint.py
python scripts/archive_role_injury_mm.py --restore work/priority-mm-source
cp work/priority-mm-source/results/predictions.npz analysis/results/role-injury-mm-20261016/
PYTHONPATH=src:scripts:. OPENBLAS_NUM_THREADS=1 python scripts/experimental_club_match_importance.py
python scripts/report_club_match_importance.py
PYTHONPATH=src:scripts:. python -m pytest tests/test_club_match_importance.py tests/test_mm_competition_rotation.py tests/test_mm_all_clubs.py tests/test_mm_probability_robustness.py tests/test_mm_role_injury_integration.py tests/test_research_role_injury_club_audit.py tests/test_team_news_history.py tests/test_team_news_audit.py -q
```

Kildemanifest og indholdschecksums findes sammen med resultaterne. Gzip-indhold sammenlignes efter dekomprimering. Workflow `mm-club-importance.yml` gendanner samme arkiver, kører de faktiske kandidater og sikrer uændret produktions-`src` og frossen MM-prognosechecksum. Produktionsparametre, 2.125-point-benchmark og `locked_model_active=false` er bevaret.
''')
    repro=ROOT/'docs/checkpoints/2026-10-16-club-importance-reproduction.json'
    if repro.exists():
        r=json.loads(repro.read_text());exact=sum(v['exact']for v in r['files'].values());maximum=max(v['max_numeric_difference']for v in r['files'].values())
        parts.append(f"\n### Verificeret Actions og genkørsel\n\n[Actions {r['workflow_run']}]({r['workflow_url']}) er bestået med alle 61 tests, modelkørsler, produktionsdiff og frossen MM-checksum. Kode `e7422b1`, resultatcommit `9fae5f8`. Artifact {r['artifact_id']} er downloadet og ZIP-SHA-256-verificeret; alle 13 manifestførte filer og gzip-streams er valideret.\n\nEn separat lokal genkørsel matcher {exact}/13 filindhold byte-for-byte. De øvrige matcher rækker, labels, missingness, modelvalg og tal med højst {maximum:.3g} absolut numerisk forskel (kontrolleret tolerance 1e−6). De syv regressions-/klassifikationsfiler påstås ikke at være byteidentiske. Det fulde bevis findes i `docs/checkpoints/2026-10-16-club-importance-reproduction.json`. `docs/research/data/2026-10-16-importance-overall-contrasts.csv` dannes reproducerbart af rapportscriptet fra de verificerede enkeltprognoser; det er ikke en ny modelkørsel.\n")
    target=ROOT/'docs/research/2026-10-16-mm-club-dynamic-importance.md';target.write_text('\n'.join(parts));print(target)

if __name__=='__main__':main()
