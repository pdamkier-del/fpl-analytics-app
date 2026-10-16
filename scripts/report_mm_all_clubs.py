#!/usr/bin/env python3
"""Render all-club MM evidence without fitting or changing model outputs."""
import gzip
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT/'analysis/results/mm-all-clubs-20261016'
DOC = ROOT/'docs/research'
NEW = 'role_chance_return_duration'
LABELS = {'original':'Låst MM', 'role':'Individuel rolle-MM',
          'role_news_projected':'Rolle + news', 'role_source_chance':'Rolle + chance-loft',
          NEW:'Chance-loft + returvarighed', 'role_return_carry':'Fuld før-skade-rolle ved retur',
          'role_return_duration':'Kun returvarighed uden chance-loft',
          'news_all_starter_duration':'News + rollevarighed for alle',
          'chance_all_starter_duration':'Chance-loft + rollevarighed for alle'}


def num(x, digits=3):
    return 'Not Available' if x is None or pd.isna(x) else f'{x:.{digits}f}'


def interval(v):
    if not v:
        return 'Not Available'
    return num(v['delta'])+' ['+(', '.join(num(x) for x in v['interval95']) if v['interval95'] else 'Not Available: få GW-blokke')+']'


def table(head, rows):
    text = ['| '+' | '.join(head)+' |', '| '+' | '.join(['---']*len(head))+' |']
    for r in rows:
        text.append('| '+' | '.join(str(x).replace('|', '/').replace('\n', ' ') for x in r)+' |')
    return '\n'.join(text)+'\n\n'


def m(club, model=NEW):
    return club['models'][model]['metrics']


def g(club, group, model=NEW):
    return club['models'][model]['groups'][group]['metrics']


def problem(club):
    p = club['problem']['largest_component']
    names = dict(start_selection='Startudvælgelse', starter_duration='Startvarighed',
                 cameo_selection='Indskiftningschance', cameo_duration='Indskiftningsminutter')
    groups = [(label, g(club,label)) for label in ['regular','rotation_or_short_history','reserve']]
    label, hardest = max(groups, key=lambda x:x[1].get('minute_mae', -1))
    text = names[p]+'; sværest: '+label+' (MAE '+num(hardest.get('minute_mae'))+')'
    if m(club)['false_zero_appearance']:
        text += '; '+str(m(club)['false_zero_appearance'])+' falske nuller'
    return text+'; kausal årsag ikke fastlagt'


def main():
    d = json.loads(gzip.decompress((DATA/'report.json.gz').read_bytes()))
    top = pd.read_csv(DATA/'top_errors.csv.gz', low_memory=False)
    groups_csv = pd.read_csv(DATA/'group_metrics.csv.gz', low_memory=False)
    groups_csv = groups_csv[groups_csv.phase.eq('evaluation_reused')]
    main = ['# Klubvis MM-evaluering: alle Premier League-klubber, 2024/25 og 2025/26\n',
        '**Kun MM.** Ingen PM, FPL-point, TS eller chips er simuleret eller ændret. Produktionskoden er uændret; `locked_model_active=false`.\n',
        '## Hovedresultat\n',
        'Den eksisterende kandidat med rolle, kilde-news, spillechanceloft og bevaret startvarighed ved selection-retur sænker samlet minut-MAE. Det er et forskningsresultat på tidligere anvendte perioder, ikke en ny uafhængig godkendelse. At erstatte betinget startvarighed med den langsigtede rolleprofil for alle spillere forværrer MAE, men forbedrer RMSE. Den er derfor ikke en generel forbedring og anbefales ikke som erstatning ved det hidtidige MAE-fokus.\n',
        '## Identiske cohorts og informationsgrænser\n',
        'Alle 20 klubber er evalueret i hver sæson. 2024/25 GW6–21 vises separat som genbrugt udviklingsperiode; hovedsammenligningen bruger 2024/25 GW22–38 og 2025/26 GW6–38. GW1–5 mangler MM-forecasts i dette checkpoint og må ikke udgives som testet. Der er 540 klub/model/periode-kombinationer (9 arme × 60 klubperioder); de fem efterspurgte hovedarme giver 200 klub/model-kombinationer i evalueringen.\n',
        'Det er en deterministisk evaluering af de frosne walk-forward-MM-forudsigelser og nye isolerede s-ablationer, ikke nye Monte Carlo-kampforløb. Betingede minutgennemsnit og sandsynligheder evalueres; ingen ny fuld survival-fordeling eller joint XI-simulation påstås. Hver frossen spillerkamp er koblet én-til-én til Core: spiller-ID, sæson, fixture, klub, GW, faktiske starter og minutter er kontrolleret. Samtlige modelarme har identiske nøgler/truth/cutoffs. Kickoff ligger efter cutoff; alle anvendte news-snapshots ligger strengt før cutoff. Klub-ID’er er sæsonafgrænsede. Historisk offentliggørelse af realiserede kampdata er stadig den nedarvede kickoff+3/4h-proxy, så fuld kildecertificering er ikke påstået.\n',
        'Normalrolle og nyhedsstatus holdes adskilt. Ukendt tilgængelighed bliver ikke rask. En source-selection-return betyder første kildebekræftede AVAILABLE efter en dokumenteret FPL-medical-flagning, ikke lægelig clearance. Der er ingen verificerede træningsreturdatoer i dette lag.\n',
        '## Samlet evaluering, begge sæsoner\n']
    combined = d['combined_evaluation']
    main.append(table(['MM-arm','N','Minut-MAE','RMSE','Bias','Start-Brier','Spille-Brier','Falske nul-spillechancer','MAE−original [95% CI]'],
        [[LABELS[k],v['rows'],num(v['minute_mae']),num(v['minute_rmse']),num(v['minute_bias']),num(v['start_brier'],5),num(v['appearance_brier'],5),v['false_zero_appearance'],interval(d['combined_intervals'][k]['metrics']['minute_mae'])]for k,v in combined.items()]))
    main.append('Minut-MAE er vægtet efter antal spillerkampe, ikke et uvægtet gennemsnit af klubber/sæsoner. Kombinationsintervaller resampler sæsonerne separat. Alle nul-spillechancer med faktisk spil har teoretisk uendelig log-loss; de viste finite log-loss-tal anvender det eksplicitte numeriske klip 1e−12 og må ikke skjule denne begrænsning.\n')
    main.append('## Hvilke grupper er sværest, og hvorfor MAE/RMSE er uenige\n')
    group_table = []
    for label in ['regular','rotation_or_short_history','reserve','prior_three_full_starts','single_short_after_three_full','actually_played_evaluation_only']:
        for model in ['role_source_chance',NEW,'chance_all_starter_duration']:
            rows = groups_csv[groups_csv['group'].eq(label) & groups_csv.model.eq(model) & groups_csv.rows.gt(0)]
            n = int(rows.rows.sum())
            group_table.append([label,LABELS[model],n,num((rows.rows*rows.minute_mae).sum()/n),num(((rows.rows*rows.minute_rmse**2).sum()/n)**.5),num((rows.rows*rows.minute_bias).sum()/n)])
    main.append(table(['Gruppe','Model','N','MAE','RMSE','Bias'],group_table))
    main.append('Rollevarighed-for-alle giver præcis ændringen Δx=p·Δs, fordi p/q/c er uændrede. Kvadreret fejl ændres med 2·(x−minutter)·p·Δs+(p·Δs)². Den kan derfor reducere få store fejl og samtidig gøre mange moderate fejl større. Gruppen efter én kort start forbedres deskriptivt, mens gruppen med tre tidligere fulde starter forværres i MAE; dette begrunder ikke en ny efterfølgende specialregel på samme evalueringsdata.\n')
    main.append('Actually-played/started og played-return er outcome-betingede diagnostiske grupper. Deres bias kan ikke alene bevise fejlkalibrering af ubetinget startchance: hvis man kun vælger faktisk startende spillere, vil en korrekt usikker prognose ofte ligge under deres realiserede minutter. De før-cutoff definerede rollegrupper og Brier/log-loss skal læses sammen med dem.\n')
    main.append('## De første 1–3 kampe efter kildebekræftet selection-retur\n')
    return_table = []
    for label in [prefix+str(i) for prefix in ['scheduled_return_','played_return_'] for i in [1,2,3]]:
        for model in ['original',NEW]:
            rows = groups_csv[groups_csv['group'].eq(label) & groups_csv.model.eq(model) & groups_csv.rows.gt(0)]
            n = int(rows.rows.sum())
            return_table.append([label,LABELS[model],n,num((rows.rows*rows.minute_mae).sum()/n),num((rows.rows*rows.minute_bias).sum()/n),num((rows.rows*rows.start_brier).sum()/n,5),num((rows.rows*rows.appearance_brier).sum()/n,5)])
    main.append(table(['Returgruppe','Model','N','MAE','Minut-bias','Start-Brier','Spille-Brier'],return_table))
    main.append('Klubvise parrede intervaller og alle øvrige metric findes i JSON/CSV. Første observerede source-AVAILABLE er ikke præcis lægelig raskmelding; episoder ved datasættets start kan være venstrecensurerede, og GW1–5-returer kan mangle. N for planlagte kampe og faktiske deltagelser må ikke lægges sammen.\n')
    main.append('## Usikkerhed og modelvalg\n')
    main.append('Der bruges 1.000 parrede circular moving-GW-block-bootstrap-træk med bloklængde 4 og fast seed. Alle kampe og spillere i samme GW følger samme træk; blanke klub-GWs forbliver på kalenderaksen. Under otte befolkede GWs står intervallet Not Available. Især 17 evaluerings-GWs i 2024/25 giver få effektive blokke. Intervallerne dækker ikke kildefejl, ubekræftede medicinske forhold eller gentagen modeludvælgelse; ingen multiplicitetskorrektion er foretaget. Perioderne er genbrugt forskning, ikke uberørte holdouts.\n')
    main.append('Ni arme indeholder de fem bestilte plus isolerede komponenttests: kun kildeprocent, kun retur-s, fuld før-skade-tuple, og kun s fra den eksisterende frosne rollevarighed for alle spillere. De sidste to s-arme ændrer ikke p, q eller c. Ingen ny modelparameter er fitted, og ingen klub- eller spillerjustering vælges ud fra disse tabeller. “Ny” i klubtabellen er den allerede fastlagte chance+returvarighedskandidat, ikke den bedste model valgt separat for hver klub.\n')
    for season in ['2024-25','2025-26']:
        z = d['reports'][season+':evaluation_reused']
        clubs = z['clubs_ranked']
        improved = sum(m(c)['minute_mae'] < m(c,'original')['minute_mae'] for c in clubs)
        worse = sum(m(c)['minute_mae'] > m(c,'original')['minute_mae'] for c in clubs)
        main += ['## '+season+' – alle 20 klubber\n', f'{improved} klubber forbedres og {worse} forværres mod den oprindelige MM. Rækkefølge: størst ny minut-MAE først. Negativ delta betyder forbedring.\n']
        main.append(table(['Klub','Original MAE','Ny MAE','Delta [95% CI]','Største dokumenterede problem'],
            [[c['club'],num(m(c,'original')['minute_mae']),num(m(c)['minute_mae']),interval(c['models'][NEW]['vs_original']['metrics']['minute_mae']),problem(c)]for c in clubs]))
        main.append(f'[Fuld klubrapport med fem hovedarme, grupper, returer og ti største fejl pr. klub](2026-10-16-mm-clubs-{season}.md). Alle ni arme og alle modelvarianters ti største fejl findes i CSV/JSON.\n')
        main.append('### Isolerede komponentændringer\n')
        main.append(table(['Kandidat','Reference','MAE-delta [95% CI]','Spille-Brier-delta [95% CI]'],
            [[LABELS[k.split(' vs ')[0]],LABELS[k.split(' vs ')[1]],interval(v['metrics']['minute_mae']),interval(v['metrics']['appearance_brier'])]for k,v in z['isolated_ablations'].items()]))
        main.append('### Manchester City, Chelsea, Arsenal og Liverpool\n')
        for c in clubs:
            if c['club'] not in ['Man City','Chelsea','Arsenal','Liverpool']:
                continue
            regular, reserve = g(c,'regular'), g(c,'reserve')
            full, short = g(c,'prior_three_full_starts'), g(c,'single_short_after_three_full')
            main += ['#### '+c['club']+'\n',
                f"Original MAE {num(m(c,'original')['minute_mae'])} → {num(m(c)['minute_mae'])}; ny RMSE {num(m(c)['minute_rmse'])}; bias {num(m(c)['minute_bias'])}. {problem(c)}.\n",
                f"Faste startere: N={regular['rows']}, MAE {num(regular.get('minute_mae'))}, bias {num(regular.get('minute_bias'))}, start-bias {num(regular.get('start_bias'))}. Reserver: N={reserve['rows']}, MAE {num(reserve.get('minute_mae'))}, start-bias {num(reserve.get('start_bias'))}. Negativ start-bias er underestimering; positiv er overestimering.\n",
                f"Tre tidligere kilde-AVAILABLE 90-minuttersstarter: N={full['rows']}, betinget startvarigheds-MAE {num(full.get('starter_duration_mae'))}, varigheds-bias {num(full.get('starter_duration_bias'))}. Efter tre fulde starter efterfulgt af én start under 60 min: N={short['rows']}, MAE {num(short.get('minute_mae'))}, betinget varigheds-bias {num(short.get('starter_duration_bias'))}. Disse er diagnostiske grupper, ikke en bevist taktisk/skadesårsag eller nye parametre.\n",
                f"Kildeukendte rækker: {c['source_unknown_rows']}. Verificeret træningsretur: Not Available. Kausal dokumentation for rotation, trænerskifte eller taktisk ændring: Not Available i det anvendte lag.\n"]
        detail = [f'# MM-klubrapport {season}\n',
            '[Samlet rapport og metode](2026-10-16-mm-all-clubs-results.md). Alle tal nedenfor bruger samme evalueringscohort pr. klub. Start-/spille-logloss er numerisk klippet ved 1e−12; falske nulprognoser vises særskilt.\n']
        for c in clubs:
            detail += ['## '+c['club']+'\n', problem(c)+'. Hypoteser om træner, taktisk rotation eller årsag til en kort kamp er ikke verificeret.\n']
            detail.append(table(['Model','N','MAE','RMSE','Minut-bias','Start-Brier','Start-LL','Spille-Brier','Spille-LL','Falske nul min / spil'],
                [[LABELS[k],m(c,k)['rows']]+[num(m(c,k)[x],5 if 'brier'in x else 3)for x in ['minute_mae','minute_rmse','minute_bias','start_brier','start_log_loss','appearance_brier','appearance_log_loss']]+[str(m(c,k)['false_zero_minutes'])+' / '+str(m(c,k)['false_zero_appearance'])]for k in ['original','role','role_news_projected','role_source_chance',NEW]]))
            detail.append('### Spillergrupper og de første tre kampe efter kilde-selection-retur\n')
            groups = ['regular','rotation_or_short_history','reserve','prior_three_full_starts','single_short_after_three_full','source_medical_return']+[prefix+str(i)for prefix in ['scheduled_return_','played_return_']for i in [1,2,3]]
            detail.append(table(['Gruppe','N','Original MAE','Ny MAE','Ny bias','Start-Brier','Spille-Brier','MAE-delta [95% CI]'],
                [[label,g(c,label)['rows'],num(g(c,label,'original').get('minute_mae')),num(g(c,label).get('minute_mae')),num(g(c,label).get('minute_bias')),num(g(c,label).get('start_brier'),5),num(g(c,label).get('appearance_brier'),5),interval(c['models'][NEW]['groups'][label]['vs_original']['metrics'].get('minute_mae'))]for label in groups]))
            detail.append('Scheduled-return tæller de første planlagte kampe efter første kilde-AVAILABLE; played-return tæller de første faktiske deltagelser og er alene en retrospektiv evalueringsgruppe. Ny medicinsk OUT eller klubskifte afslutter forløbet. Dette er ikke dokumentation for træningsretur/lægelig raskmelding. Ikke-deltagelse må ikke bruges til at erklære en ny skade.\n')
            cases = top[(top.season.eq(season)) & top.phase.eq('evaluation_reused') & top.club.eq(c['club']) & top.model.eq(NEW)]
            detail.append('### De ti største individuelle prognosefejl – fastlagt kandidat\n')
            detail.append(table(['Spiller','GW','Faktiske min','xMins','P(start)','Komponent','Verificerede observationer'],
                [[r['player'],int(r['gw']),num(r['actual_minutes'],0),num(r['expected_minutes']),num(r['p_start']),r['error_component'],r['verified_observations']]for r in cases.to_dict('records')]))
            detail.append('Fixture-ID, spiller-ID, cutoff, kickoff, rå news og kilde-URL følger hver fejl i `top_errors.csv.gz`; der er også ti fejl pr. alternativ model og klub. Den algebraiske komponent er ikke en kausal diagnose.\n')
        (DOC/f'2026-10-16-mm-clubs-{season}.md').write_text('\n'.join(detail))
    main += ['## Verificerede mekanismer og utestede rettelser\n',
        'De 35 falske nul-spillechancer fra den tidligere news-/chancekontrol er bevaret og ikke korrigeret med fremtidsviden. De tre DGW-karantænetilfælde har nu supplerende primærkildeunderstøttelse: [Liverpool 18. februar 2025](https://www.liverpoolfc.com/news/aston-villa-v-liverpool-team-news-2) omtaler Jones’ retur fra én kamps karantæne; [Palace 16. april 2025](https://www.cpfc.co.uk/news/match-reports/live-blog-highlights-reaction-newcastle-united-crystal-palace-april-2025/) bekræfter Guéhis retur efter City-karantænen og Nketiahs deltagelse. Begge er efter de relevante GW-deadlines. De bruges derfor kun som retrospektiv fejldokumentation, aldrig som før-deadline input. Dagens HTML-hashes og denne begrænsning gemmes i `corroborating_sources.json`.\n',
        '**Kampafgrænset karantænerettelse: Not Available som kildecertificeret A/B-arm.** De arkiverede FPL-noter mangler et fuldt, verificeret kamp-/tidsafgrænset udløb. At indsætte de senere artikler i en tidligere deadline ville give leakage. At gætte et år/klokkeslæt eller genindføre en spillers normale startchance efter en formodet udløbsdato er ikke gjort.\n',
        '**Trænings-/medicinsk returrettelse: Not Available.** Vi har kilde-selection-returer og retrospektive kampdeltagelser, ikke uafhængigt tidsverificerede kliniske clearance- eller træningsdatoer. Der er derfor ingen sådan ekstra effektarm eller opfundet skadevarighed.\n',
        '## Hvad bør beholdes eller forkastes?\n',
        '- Behold rolle, midlertidig status og normal startvarighed som adskilte begreber. Behold kildesnapshots, identitets-/deadlinekontroller og falske nul-caseaudit.\n- Behold chance-loftet som forskningskandidat: det forbedrer begge forskningsperioder, men FPL-procenter er ikke en kalibreret ubetinget start-/spillechance.\n- Bevar retur-s som separat, begrænset hypotese: lille gevinst i 2025/26; usikkert i 2024/25. Ingen automatisk høj startchance ved AVAILABLE.\n- Forkast fuld før-skade-tuple-carry som generel returløsning i denne form. Rollevarighed-for-alle forbedrer RMSE, men forværrer MAE og er derfor ikke en dokumenteret samlet erstatning; behold den oprindelige varighedsdel ved MAE-fokus.\n- Ingen klubspecifikke boosts, nye fitted parametre eller promotion. Nye prospektive/uberørte data og kampafgrænsede disciplinære kilder mangler stadig.\n',
        '## Data, kode og reproduktion\n',
        '`scripts/validate_mm_all_clubs.py` genskaber alle tabeller fra permanente MM-kapsler og Core; `scripts/report_mm_all_clubs.py` genskaber denne rapport og de to klubrapporter. `content_manifest.json` gemmer kode-/inputhashes og eksakte indholdshashes (udpakket gzip). Den dedikerede GitHub-workflow kontrollerer 40 evaluerings-klubsæsoner, 540 klub/model/periode-rækker, 5.400 største-fejl-cases, regressionstests, frosne prediction-bytes og uændret `src`.\n',
        'Resultatfiler: `club_metrics.csv`, `overall_metrics.csv`, `isolated_ablations.csv`, `group_metrics.csv.gz`, `top_errors.csv.gz`, `report.json.gz`, `summary.json`, `content_manifest.json` i `analysis/results/mm-all-clubs-20261016/`. Gzip-filer udpakkes til almindelig CSV/JSON. Der er ingen private managerdata.\n']
    proof_path = DATA/'reproduction.json'
    if proof_path.exists():
        proof = json.loads(proof_path.read_text())
        main += ['## Bestået CI og eksakt reproduktion\n',
            f"[Workflow {proof['workflow_run']}]({proof['workflow_url']}) er bestået med {proof['tests_passed']} relevante regressionstests, alle dæknings-/hashkontroller og uændret produktion. Alle syv numeriske outputfilers indhold matcher den uafhængige lokale kørsel byte for byte (gzip udpakkes før sammenligning; ingen numerisk tolerance/afrunding). Kodecommit `{proof['code_commit'][:7]}`, dataresultatcommit `{proof['data_commit'][:7]}`; `reproduction.json` gemmer kontrollen.\n"]
    (DOC/'2026-10-16-mm-all-clubs-results.md').write_text('\n'.join(main))
    print('Main MM report and both complete 20-club reports generated')


if __name__ == '__main__':
    main()
