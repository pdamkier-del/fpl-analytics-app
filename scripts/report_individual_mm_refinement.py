#!/usr/bin/env python3
"""Read-only report rendering and distribution calibration; no model fitting."""
from pathlib import Path
import json,sqlite3,hashlib
import pandas as pd
import numpy as np
from individual_mm_evidence import load_frame
from audit_mm_components import error_terms,attribution
from validate_mm_probability_robustness import probability_scores

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'analysis/results/individual-mm-refinement-20261016'
DATA=ROOT/'docs/research/data'


def table(headers,rows):
    def cell(v):
        if v is None or pd.isna(v):return 'Not Available'
        if isinstance(v,(float,np.floating)):return f'{v:.6f}'
        return str(v)
    return '| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'+'\n'.join('| '+' | '.join(cell(v)for v in row)+' |'for row in rows)+'\n'


def main():
    DATA.mkdir(exist_ok=True)
    r=json.loads((P/'report.json').read_text());club=pd.read_csv(P/'club_metrics.csv');groups=pd.read_csv(P/'group_metrics.csv.gz');tuning=pd.read_csv(P/'development_selection.csv');fits=pd.read_csv(P/'fit_cutoffs.csv')
    predictions=load_frame(P/'predictions.npz');evaluation=predictions[predictions.season.eq('2025-26')|predictions.gw.ge(22)]
    critical=['regular','rotation','reserve','source_medical_return','documented_return_1','documented_return_2','documented_return_3','documented_suspension_return','short_rest','long_rest']
    decisions=[]
    for model,score in r['combined'].items():
        if model in ['original','best_existing']:continue
        ci=r['combined_intervals'][model]['metrics'];cg=groups[groups.club.eq('ALL')&groups.model.eq(model)&groups.group.isin(critical)]
        harm=cg[(cg.mae_low>0)|(cg.start_brier_low>0)]
        gain=ci['minute_mae']['interval95'][1]<0 and ci['start_brier']['interval95'][1]<=0
        decisions.append(dict(model=model,minute_mae=score['minute_mae'],mae_delta=ci['minute_mae']['delta'],mae_low=ci['minute_mae']['interval95'][0],mae_high=ci['minute_mae']['interval95'][1],brier_delta=ci['start_brier']['delta'],brier_high=ci['start_brier']['interval95'][1],critical_supported_harm_slices=len(harm),eligible_for_further_research=bool(gain and not len(harm)),production_approved=False))
    decision=pd.DataFrame(decisions).sort_values('minute_mae');decision.to_csv(DATA/'2026-10-16-mm-refinement-decision.csv',index=False)
    eligible=decision[decision.eligible_for_further_research]
    recommended=eligible.iloc[0].model if len(eligible)else'best_existing'
    pointwinner=decision.iloc[0].model
    parts=['''# Individuel MM: stabilitet, kalibrering, minutfordelinger og tilbagevenden

Dato: 2026-10-16. Ny branch: `research-individual-mm-refinement-20261016`. Draft PR #9, bygger videre på PR #4/#8 og commit `aca5dba`.

## Omfang og beslutningsprincip

Dette er en faktisk **MM-only, prequential historisk simulation/replay**, ikke blot implementering. Original MM, bedste eksisterende kandidat, A/B/C/D og fem på forhånd definerede kombinationer er kørt på de samme historiske spillerkampe. PM, TS, FPL-point og chips er ikke kørt. Produktions-MM og låste parametre er uændrede; `locked_model_active=false`.

Der vælges ikke automatisk den laveste minut-MAE. Den konservative forskningsscreening kræver en samlet MAE-forbedring og ikke-forværret start-Brier, hvor de parrede 95%-intervaller understøtter det, samt ingen statistisk understøttet forværring af de kritiske rolle-, retur- eller restitutionsgrupper i nogen sæson. Dette er en screen, ikke bevis for ækvivalens/non-inferiority: der er ikke opfundet en accepteret klinisk eller sportslig tolerancemargin. Sparsomme grupper med manglende interval kan ikke erklæres sikre. Intervaller er ikke multiplicitetstilpassede; screeningen er konservativ, og eventuelle fund skal bekræftes på nyt materiale.
''']
    parts.append(f'\nLaveste observerede samlede MAE blandt nye kandidater: **{pointwinner}**. Variant, der passerer den beskrevne konservative forskningsscreen: **{recommended}**. Ingen variant er produktionsgodkendt.\n')
    parts.append('''
## 1. Data, identiteter og kronologi

Samme frosne prognoser og kildekontroller fra PR #4/#8 genbruges. Hver referenceprognose matches mod Core på sæson, kamp, spiller, klub, GW, faktisk start og minutter. Alle target-kickoffs ligger efter cutoff. Ny rollehistorik ignorerer ukendt fravær; kendt tidligere optræden er direkte historisk selektionsevidens, men ikke en helbredsattest til næste kamp. Hard-source OUT/SUSPENDED med modstridende faktisk optræden er udeladt af normalrolle- og varighedstræning, men **forbliver i evalueringen**. De fjernes ikke for at forbedre målene.

50.231 spillerkampe har originale/beste MM-prognoser. Evaluering: **39.264 identiske spillerkampe pr. arm**, 2024/25 GW22–38 og 2025/26 GW6–38, alle 20 klubber i hver sæson. GW1–5 har ingen nye opfundne forecasts, men deres kendte kampminutter kan indgå som tidligere råhistorik. Alle nye beslutningsregler er globale, ikke spiller-/klubspecifikke boosts.

**Udvikling:** hyperparametre vælges på 2024/25 GW14–21, med modeller til hvert historisk cutoff udelukkende fittet til labels, der var kendt tidligere. B vælges på start-Brier; A/C/D på samlet minut-MAE. Kun rigtige ikke-nul kandidater søges i hver familie; den uændrede reference bevares som separat mulighed og kan vinde den afsluttende beslutning. Kombinationer er prædefinerede, ikke en efterfølgende klub-/spillergrid.

**Evaluering:** derefter GW22–38 og 2025/26 GW6–38. Kalibrerings-/residualmodeller refittes ved hver origin på tidligere kendte labels. 2024/25-resultater må indgå i senere 2025/26-træning, fordi de da er fortid. Baseline og perioder har været genbrugt i forskning; dette er **ikke uafhængige holdouts eller en ny uberørt valideringssæson**.

Outcome-tilgængelighed arver kickoff + fire timer i 2024/25 og + tre timer i 2025/26, ikke verificerede faktiske publiceringstidspunkter. Alle kendt-før-kontroller er strenge `< cutoff`; deadline-certificering er fortsat blokeret af kildeklokkernes usikkerhed.

Belastning/hvile følger spilleridentiteten på tværs af verificerede PL-klubskifter. Normalrolle og personlige varighedsprofiler forbliver klubspecifikke. Restitution er tid siden seneste kendte PL-optræden frem til cutoff, ikke en verificeret total restitutionstid ved kickoff. Cup-/Europaminutter mangler i denne kontrollerede MM-test og erstattes ikke med nul aktivitet. Fravær og langt ophold mellem kampe betegnes ikke automatisk skade.
''')
    parts.append(table(['Træningsorigins','Alle target-rækker','Laveste tidligere labelantal','Højeste tidligere labelantal','Alle label-klokker før cutoff'],[[len(fits),int(fits.target_rows.sum()),int(fits.training_rows.min()),int(fits.training_rows.max()),bool(fits.properly_before.all())]]))
    parts.append(r'''
## 2. Matematiske ændringer og isolation

Alle arme bruger den eksisterende identitet

$$
E[M]=p\,s+(1-p)q\,c,
$$

hvor p er startchance, s betingede starterminutter, q indskiftningschance givet ingen start og c minutter givet indskiftning. Den eksisterende source-cap og exact-11-projektion genbruges uændret: én forventet startende målmand og ti øvrige. Dette er **marginale startchancer**, ikke en ny uafhængig XI-sampler eller en påstand om simuleret lovlig joint-XI-fordeling.

### A: stabil normalrolle

Ud fra kun tidligere anvendelig rollehistorik beregnes

$$
p_{stable}=\frac{8p_{normal}+\sum_i w_i y_i}{8+\sum_i w_i},\quad
w_i=2^{-\Delta t_i/180},\quad
p_A=(1-a)p_{best}+a p_{stable}.
$$

Normalpriorn genbruges fra den eksisterende bevarede rolle, ellers den eksisterende rolle-MM. Midlertidigt fravær uden gyldig rolleobservation tæller ikke som en serie taktiske bænkninger. Én atypisk kamp påvirker en længere historik gradvist. Exponering 8 og halvering 180 dage er genbrugte forskningspriors; a vælges blandt 0,25/0,5/1 på udviklingsdata. Aktuel tilgængelighed håndteres separat af caps. A ændrer startsignalet, ikke direkte starter-/bænkvarighederne.

Et negativt resultat for A's faste ekstra blend betyder ikke, at historiske roller er værdiløse: B bruger også normal-/stabil rolle som input, men lærer vægtningen fra tidligere startudfald.

### B: startkalibrering

En regulariseret logistisk kalibrering bruger eksisterende logit(p)/logit(q), normal/stabil rolle, tidligere start-/indskiftningshistorik, position, hvile, registrerede 7/14-døgnsminutter og manglende-data-indikatorer. Hver model ser kun tidligere kendte outcomes og aldrig den aktuelle start eller aktuelle minutter. Numeriske variable standardiseres på træningshistorikken. Regulariseringsstyrke vælges blandt 0,1/1/10. Minimum 200 tidligere interiørprognoser og begge klasser kræves; ellers bruges den uændrede reference, ikke syntetiske træningsrækker. Source-hard-zero/caps bevares efter projektion.

### C: individuel varighedsfordeling

Der startes ikke en ny global MM fra bunden. Ridge lærer **residualkorrektioner til de eksisterende s/c**, separat blandt faktiske startere og faktiske indskiftninger, kun på tidligere pålidelige observationer. Samme prior-only rolle-/belastningsfeatures anvendes. Alpha vælges blandt 1/10/100; mindst 100 startere/50 indskiftninger kræves, ellers beholdes baseline.

En positionstilpasset empirisk residualfordeling omkring den nye betingede middelværdi kombineres med spillerens decayed personlige minutfordeling:

$$
P_C(M=m\mid state)=\frac{5P_{residual,position}(m)+h_{player}(m)}{5+\sum_m h_{player}(m)}.
$$

Exponering 5 genbruges fra eksisterende duration-prior. Hver startfordeling ligger på 0–90 minutter; indskiftningsfordelingen på 1–90, betinget på en positiv optræden. Fraktionel bin-deponering bevarer kontinuitet mellem minutbin. Middelværdier fra disse fordelinger bliver C's s/c; p og q ændres ikke. Spredning, 10/90-percentiler og P(90) / P(1–15) gemmes. Residualformen er estimeret i træningshistorikken, ikke en garanti for kalibrerede predictive intervals; out-of-origin-kalibreringen måles nedenfor.

Registrerede starterminutter beskriver stint-varighed, men ikke verificeret årsag til en udskiftning. Core mangler verificerede sub-on/off-tidsstempler. Der er derfor **ingen opfundet udskiftningshazard, føringsstilling, taktisk eller medicinsk exitårsag** i C.

### D: kildeafgrænset tilbagevenden

Sidste tidligere eksplicit AVAILABLE-rolle i samme klub gemmes før dokumenteret medicinsk OUT eller SUSPENDED. D aktiveres kun ved ny eksplicit AVAILABLE/RETURNED_AVAILABLE, aldrig fordi spilleren faktisk ender med at spille den aktuelle kamp. En global vægt a/(1+n) trækker p og s mod før-fraværsrollen, hvor n er antal tidligere afsluttede, allerede kendte kampe siden den nye selection-return-origin; de første tre kendte kamptrin undersøges. Vægten a vælges blandt 0,25/0,5/1 på udvikling. Ny OUT eller klubskifte nulstiller episoden.

Det er en testet probabilistisk rolleprior, ikke en erklæring om fuld kampform eller klinisk helbredelse. Ved DGW kan to fremtidige kampe ved samme cutoff dele n=0: første kamps endnu ukendte spilletid bruges ikke til den anden. Grupperne return_1/2/3 svarer til 0/1/2 **kendte** tidligere kampe siden return-origin, ikke en fremtidsinformeret faktisk optrædenstæller.

D er et tillæg til den bedste eksisterende kandidat. Dennes allerede etablerede bevaring af startervarighed ved en kildeafgrænset retur fjernes ikke, selv om det nye udvidede p/s-carry ikke giver en sikker ekstra gevinst.

### Kombinationer og begrænsninger

A+B, A+C, B+C, B+D og A+B+C+D er kørt. B er fittet som kalibrering af baseline; i A+B anvendes B's faste log-odds-korrektion oven på A, ikke en skjult refit på evalueringsdata. Alle startsignaler caps/projekteres. Ændret p kan nødvendiggøre ændret q for at overholde den samme source appearance-cap. Ingen ny q-model, importance-score, klinisk regel eller optimering af FPL-point er indført.
''')
    parts.append('\nValgte udviklingsparametre: `'+json.dumps(r['selected'])+'`. Alle forsøgsværdier og udviklingsmål findes i `development_selection.csv`.\n')
    parts.append('## 3. Samlede faktiske før/efter-resultater\n\n')
    from validate_mm_all_clubs import combined_ci
    ablations={}
    for candidate,reference in [('B_D','B'),('A_B','B'),('B_C','B'),('A_C','A')]:
        ablations[candidate+' vs '+reference]=combined_ci(evaluation[evaluation['mode'].eq(candidate)],evaluation[evaluation['mode'].eq(reference)])
    (DATA/'2026-10-16-mm-refinement-ablations.json').write_text(json.dumps(ablations,indent=2)+'\n')
    rows=[]
    for name,m in r['combined'].items():
        ci=r['combined_intervals'][name]['metrics']['minute_mae'];start=probability_scores(evaluation[evaluation['mode'].eq(name)].p,evaluation[evaluation['mode'].eq(name)].y)
        rows.append([name,m['minute_mae'],m['minute_rmse'],m['start_brier'],m['start_log_loss'],m['minute_bias'],start['ece_10_bins'],m['starter_duration_mae'],m['cameo_duration_mae'],m['false_zero_appearance'],ci['delta'],ci['interval95'][0],ci['interval95'][1]])
    parts.append(table(['Arm','Minut-MAE','RMSE','Start-Brier','Start-log-loss¹','Minut-bias','Start-ECE10','Startervarighed MAE','Cameovarighed MAE','False-zero','ΔMAE vs bedste reference','95% lav','95% høj'],rows))
    parts.append('''
¹ Viste log-loss bruger eksplicit numerisk 1e−12-clip til scoring. Modstridende hard-zero/hard-one-prognoser har **uendelig teoretisk log-loss**; clippet gør ikke prognosernes sikkerhed korrekt. Globale start-bias tæt på nul følger delvist af præcis 11 forventede startere og er ikke i sig selv bevis for individuel kalibrering.

Alle parrede intervaller bruger 1.000 cirkulære fire-GW-bloktræk med bevaret tom kalenderuge. Ved pooling resamples sæsonerne uafhængigt. Klub-/gruppeintervaller med færre end otte befolkede GWs er Not Available. Små effektive blokantal, datakildeusikkerhed, hyperparametervalg og multiplicitet er ikke fuldt indregnet.

## 4. Sæsoner og kritiske grupper
''')
    parts.append('\nDirekte kombinationsablationer, så effekter ikke tilskrives en anden komponent:\n\n'+table(['Kandidat vs reference','ΔMAE','95% lav','95% høj','ΔBrier'],[[k,v['metrics']['minute_mae']['delta'],*v['metrics']['minute_mae']['interval95'],v['metrics']['start_brier']['delta']]for k,v in ablations.items()]))
    overall=pd.read_csv(P/'overall_metrics.csv')
    parts.append(table(['Sæson','Arm','Minut-MAE','RMSE','Start-Brier','Bias'],overall[['season','model','minute_mae','minute_rmse','start_brier','minute_bias']].values.tolist()))
    selectedmodels=['best_existing','A','B','C','D',pointwinner]
    gg=groups[groups.club.eq('ALL')&groups.model.isin(selectedmodels)&groups.group.isin(critical+['single_short_after_three_full','prior_three_full_starts'])]
    parts.append('\nAlle gruppe-/klub-/armresultater er i `group_metrics.csv.gz`. Kritiske udsnit:\n\n'+table(['Sæson','Gruppe','Arm','N','MAE','Brier','Bias','ΔMAE','95% lav','95% høj'],gg[['season','group','model','rows','minute_mae','start_brier','minute_bias','mae_delta','mae_low','mae_high']].values.tolist()))
    parts.append('''
Regular/rotation/reserve-grupper defineres på tidligere Core-kampe, ikke aktuel opstilling. De bruges til evaluering, ikke til manuelle spillerboosts. Separat kildeafgrænset rollehistorik undgår at bruge ukendt fravær som taktisk rolleændring. Lange hvileperioder kan også være reservestatus eller manglende andre turneringer; grupperne må ikke alene kaldes restitutionsårsager.

## 5. Alle 40 klub-sæsoner

Tabellen viser den bedst målte nye samlede MAE-kandidat (ikke automatisk produktionsanbefalet) mod samme eksisterende reference. `club_metrics.csv` indeholder alle 11 arme pr. klub, alle metrics og parrede intervaller. Observeret MAE-stigning vises også, ikke kun gevinster.
''')
    b=club[club.model.eq('best_existing')];w=club[club.model.eq(pointwinner)]
    joined=w.merge(b[['season','team_id','minute_mae']],on=['season','team_id'],suffixes=('','_reference'))
    joined=joined.sort_values(['season','minute_mae'],ascending=[True,False])
    parts.append(table(['Sæson','Klub','Reference MAE',pointwinner+' MAE','Forskel','95% lav','95% høj','Brier'],joined[['season','club','minute_mae_reference','minute_mae','mae_delta','mae_low','mae_high','start_brier']].values.tolist()))
    parts.append('\nForskningsscreening (ingen produktionsgodkendelse):\n\n'+table(['Arm','MAE','ΔMAE','95% høj','ΔBrier','Brier 95% høj','Kritiske forværringsudsnit','Passerer konservativ screen'],decision[['model','minute_mae','mae_delta','mae_high','brier_delta','brier_high','critical_supported_harm_slices','eligible_for_further_research']].values.tolist()))
    bclubs=club[club.model.eq('B')]
    badclubs=bclubs[bclubs.mae_low.gt(0)]
    parts.append(f"\n**Klubforbehold for B:** {int(bclubs.mae_delta.lt(0).sum())}/40 klub-sæsoner forbedres og {int(bclubs.mae_delta.gt(0).sum())}/40 forværres i punktestimatet. Nedenstående positive intervaller er yderligere valideringsflag, ikke skjult bag de gode poolede grupper. De er ikke multiplicitetstilpassede, og de forhindrer en ubetinget integrationsanbefaling. Ingen klubspecifik efterjustering laves på disse evalueringsresultater.\n\n"+table(['Sæson','Klub','B ΔMAE','95% lav','95% høj'],badclubs[['season','club','mae_delta','mae_low','mae_high']].values.tolist()))
    harm=groups[groups.club.eq('ALL')&groups.group.isin(critical)&((groups.mae_low>0)|(groups.start_brier_low>0))&~groups.model.isin(['original','best_existing'])]
    parts.append('\nStatistisk understøttede forværringsflag, med ovennævnte multiple-test-forbehold:\n\n'+table(['Sæson','Arm','Gruppe','ΔMAE','MAE 95% lav','ΔBrier','Brier 95% lav'],harm[['season','model','group','mae_delta','mae_low','start_brier_delta','start_brier_low']].values.tolist()))
    parts.append('## 6. Fejlattribution og de 35 false-zero-tilfælde\n\n')
    best=evaluation[evaluation['mode'].eq('best_existing')]
    terms=error_terms(best.p,best.s,best.q,best.c,best.y,best.minutes);values=attribution(terms)
    assert abs(sum(v['mae_shapley']for v in values.values())-r['combined']['best_existing']['minute_mae'])<1e-9
    parts.append(table(['Komponent','Isoleret absolut størrelse','Algebraisk Shapley-MAE','Andel af samlet MAE'],[[k,v['standalone_absolute'],v['mae_shapley'],v['mae_share']]for k,v in values.items()]))
    parts.append('''
Shapley-opdelingen summerer algebraisk til den samlede minut-MAE, men er **fejlattribution, ikke kausal forklaring**. Komponenterne kan forstærke eller ophæve hinanden. Klubdiagnosen i report.json viser også de største komponentstørrelser. For tidlige exit/minutfejl er der ikke verificeret føring, skade, rødt kort eller trænerbeslutning som årsag.

De samme 35 modstridende hard-source appearance-tilfælde bevares i alle nye arme. 32 er OUT, tre SUSPENDED. De tre suspensioners rå dag/måned matcher en senere DGW-kamp; der mangler fortsat fuldt verificerede predeadline-udløbstidspunkter. Udaterede/ufuldstændige returdatoer, senere artikler og kliniske gæt reparerer ikke en historisk forecast.
''')
    conflicts=pd.read_csv(P/'false_zero_source_diagnosis.csv')
    parts.append(table(['Kildens begrundelseskategori','Tilfælde'],[[k,len(g)]for k,g in conflicts.groupby('source_reason_class')]))
    parts.append('''
Kategorierne beskriver **ordlyd i kilden**, ikke verificeret diagnose, transferfejl eller endelig årsag. Alle 35 individuelle IDs, rå nyheder, kildelinks, deadlines, kickoff, kildealder og dokumenterede begrænsninger står i `false_zero_source_diagnosis.csv`. Ingen tilføjet sandsynlighedsfloor eller falsk tilgængelighed skjuler problemet. Disse kilde-/certaintykonflikter blokerer fortsat fuld livegodkendelse.

## 7. Kalibrering af C's betingede minutfordeling
''')
    dist=pd.read_csv(P/'conditional_distributions.csv.gz');c=evaluation[evaluation['mode'].eq('C')].merge(dist,on=['season','fixture_uuid','player_uuid'],validate='one_to_one',suffixes=('','_distribution'))
    if not np.allclose(c.s,c.conditional_start_mean,atol=1e-10)or not np.allclose(c.c,c.conditional_cameo_mean,atol=1e-10):raise ValueError('Distribution/mean mismatch')
    rows=[]
    for season,g in c.groupby('season'):
        for state,mask,lo,hi,mean in [('start',g.y.eq(1)&g.p.gt(0),'s_q10','s_q90','s'),('cameo',g.y.eq(0)&g.minutes.gt(0)&g.q.gt(0),'c_q10','c_q90','c')]:
            z=g[mask&g[lo].notna()];coverage=((z.minutes>=z[lo])&(z.minutes<=z[hi])).mean()
            p90=((z.s_p90-z.minutes.eq(90))**2).mean()if state=='start'else None
            rows.append([season,state,len(z),coverage,(z[hi]-z[lo]).mean(),abs(z[mean]-z.minutes).mean(),p90])
    parts.append(table(['Sæson','Betingelse','N','10–90%-interval dækning','Gns. intervalbredde','Betinget MAE','P90 Brier'],rows))
    parts.append('''
Dette er predictive duration-intervaller betinget på faktisk start/indskiftning og positiv modelmasse, ikke konfidensintervaller for modelparametre. Hard-excluded optrædener får ikke en kunstig positiv event-sandsynlighed for at kunne scores betinget. Original MM's komplette duration-PMF er ikke bevaret i den frosne tabel, så der er **ikke opfundet** en original P90- eller intervalbaseline ud fra dens middelværdi. Sammenlignelige s/c-MAE og samlet MM-MAE findes ovenfor; distributionens egen kalibrering vises som diagnostik.

## 8. Hvad bør videreføres?
''')
    ref=evaluation[evaluation['mode'].eq('best_existing')]
    cc=evaluation[evaluation['mode'].eq('C')].merge(ref[['season','fixture_uuid','player_uuid','p','s','q','c','x']],on=['season','fixture_uuid','player_uuid'],validate='one_to_one',suffixes=('','_reference'))
    states={'actual_start':cc.y.eq(1),'actual_cameo':cc.y.eq(0)&cc.minutes.gt(0),'actual_zero':cc.y.eq(0)&cc.minutes.eq(0)}
    rows=[]
    for label,mask in states.items():
        z=cc[mask];delta=(abs(z.x-z.minutes)-abs(z.x_reference-z.minutes)).mean()
        rows.append([label,len(z),(z.s-z.s_reference).mean(),(z.c-z.c_reference).mean(),(z.x-z.x_reference).mean(),delta,len(z)/len(cc)*delta])
    assert abs(sum(row[6]for row in rows)-(r['combined']['C']['minute_mae']-r['combined']['best_existing']['minute_mae']))<1e-9
    parts.append('\n### Hvorfor C ikke godkendes trods bedre betingede varigheder\n\nC sænker startervarighed-MAE 8,064556→7,873829 og cameo-varighed-MAE 11,348578→10,899898, men øger samlet minut-MAE. Her er en eksakt opdeling af den samlede forskel i retrospektive udfaldsgrupper; labels bruges ikke som prognosefeatures:\n\n'+table(['Faktisk udfald','N','Δs','Δc','Δx','ΔMAE i gruppen','Bidrag til samlet ΔMAE'],rows))
    parts.append('\nBetinget varighedspræcision er altså ikke nok: x=p·s+(1−p)q·c scorer også for spillere, der ikke starter eller slet ikke spiller. Ændrede varigheder under uændrede p/q kan give en dårligere samlet tabsfunktion. Dette er en målt mekanismeopdeling, ikke bevis for taktisk eller medicinsk årsag. C bør derfor ikke integreres globalt på baggrund af de betingede gevinster alene.\n')
    parts.append(f'\nDen poolede kritiske gruppescreen anbefaler **{recommended}** som reference/næste forskningskandidat. Den laveste samlede punkt-MAE fra **{pointwinner}** alene er ikke tilstrækkelig til integration. **B har klubspecifikke forværringsflag for Everton 2024/25 og Newcastle/Wolves 2025/26. Derfor anbefales kun videre uafhængig validering/kontrolleret integrationstest, ikke ubetinget produktion.** Se tabellerne for præcis hvilke rolle-/retur-/restitutionsgrupper, der forværres. Ingen klub- eller spiller-specifik efterjustering er indført for at skjule disse udsnit. A og C frarådes som generelle minut-MAE-ændringer; D giver ingen dokumenteret ekstra MAE-gevinst, og B+D er ikke bedre end B alene.\n')
    parts.append('''
Før en ændring kan integreres, kræves nye ubrugte/prospektive MM-origins, dokumenteret kildekvalitet i nulkonflikterne, korrekt fixture-scoped suspension, kontrolleret dækning af øvrige turneringers belastning og evaluering af manglende event-/medicinske oplysninger. Modellen må ikke gøres mere kompleks alene for at opnå pænere Haaland-/Palmer-/João Pedro-tal. Der er ikke kørt PM/TS, så der drages ingen konklusion om FPL-point eller transfergevinst.

## 9. Reproduktion og sikkerhed

`research_individual_mm_refinement.py` udfører hele A–D-replayet, referencetjek, alle klub-/gruppeopdelinger, blokintervaller, kalibrering og distributionsarkivering. `fit_cutoffs.csv` dokumenterer hver origins tidligere kendte labels. `prior_only_features.csv.gz` har ingen aktuelle start-/minutlabels; `predictions.npz` og evalueringsfiler indeholder truth og må ikke bruges som prognosefeatures. `content_manifest.json` hasher gzip-indhold efter dekomprimering og NPZ som kanonisk decoded CSV.

```bash
pip install -r requirements-model-checkpoint.txt -r requirements-model-tests.txt requests
python scripts/restore_core_checkpoint.py
python scripts/archive_role_injury_mm.py --restore work/refinement-mm-source
cp work/refinement-mm-source/results/predictions.npz analysis/results/role-injury-mm-20261016/
PYTHONPATH=src:scripts:. OPENBLAS_NUM_THREADS=1 python scripts/research_individual_mm_refinement.py
PYTHONPATH=src:scripts:. OPENBLAS_NUM_THREADS=1 python scripts/report_individual_mm_refinement.py
PYTHONPATH=src:scripts:. python -m pytest tests/test_individual_mm_refinement.py tests/test_club_match_importance.py tests/test_mm_competition_rotation.py tests/test_mm_all_clubs.py tests/test_mm_probability_robustness.py tests/test_mm_role_injury_integration.py tests/test_research_role_injury_club_audit.py tests/test_team_news_history.py tests/test_team_news_audit.py -q
```

72 fokuserede MM-/kildetests består lokalt. De nye tester bl.a. current-truth-leakage, known-at-grænser, ukendt fravær, tidligere observeret selektion, hard-source karantæne, klubskiftebelastning, klinisk uverificeret retur, lovlige marginaler og duration-support. Produktions-`src`, original MM og det frosne benchmark er bevaret; `locked_model_active=false`.
''')
    repro=ROOT/'docs/checkpoints/2026-10-16-individual-mm-refinement-reproduction.json'
    if repro.exists():
        proof=json.loads(repro.read_text())
        parts.append(f"\n### Verificeret CI og eksakt reproduktion\n\n[GitHub Actions {proof['workflow_run']}]({proof['workflow_url']}) består alle72 tests, begge sæsoner/40klub-sæsoner, alle11 arme, produktionsdiff og original MM-checksum. Kode `8cb2c3e`; resultatcommit `ea0b2ec`. Artifact {proof['artifact_id']} er downloadet og ZIP-SHA-256-verificeret. Alle13 resultatfilers **indhold** matcher byte-for-byte mellem lokal kørsel og ren CI, herunder hele predictions-arkivet efter kanonisk NPZ-dekodning. Gzip-containere og NPZ-containerbytes påstås ikke at være identiske; det er de verificerede indholdshashes.\n\nDen fulde sammenligning og kilde-/produktionskontroller findes i `docs/checkpoints/2026-10-16-individual-mm-refinement-reproduction.json`. De rapportafledte beslutnings-/ablationstabeller gemmes separat under `docs/research/data/`, så de ikke forurener modeloutputmanifestet ved en ny kørsel.\n")
    target=ROOT/'docs/research/2026-10-16-individual-mm-refinement.md';target.write_text('\n'.join(parts));print(target)
    return r,decision


if __name__=='__main__':main()
