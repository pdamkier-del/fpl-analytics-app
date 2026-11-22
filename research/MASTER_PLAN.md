# FPL Analytics og FPL Research Lab — videnskabelig masterplan

Version 1 · registreret 22. november 2026 · kilder: PR #41 og #42. Dette er en planlægnings-PR, ikke en dashboard- eller modelrelease.

## To permanente produkter, én kontrolleret evidenskæde

1. **FPL Analytics:** brugerappen for hold, forventede point, transfers, kaptajn og chips. Den må alene læse den godkendte produktionsmanifest og validerede releases. Den eksisterende publicerede B-kædes kontrakt siger `locked_model_active=false`; planen må ikke omdøbe den til fuldt certificeret. TS's seks-GW-/chipvalideringsgab skal lukkes.
2. **FPL Research Lab:** permanent forsknings- og evalueringsplatform. Først et reproducerbart repo-register og rapporter; siden et visuelt separat webområde. Lab viser både positive, negative og uafklarede resultater. En forskningskandidat er aldrig en implicit produktionsmodel.

Arkitekturen er `FPL Analytics ↔ versionerede data/prognoser ↔ FPL Research Lab`. Pilene betyder datakontrakter og validerede releases — ikke at Lab kan ændre live-parametre. Se [ARCHITECTURE.md](ARCHITECTURE.md).

## Regler der består på tværs af sessioner

- Frosne MM B-, PM vFinal- og TS v3-kilder, parametre og app-UI ændres ikke af forskningsarbejde.
- Det eksisterende præregistrerede substitutionsforsøg er eksternt beskyttet og fuldstændig uændret. Dets 8-GW/80-kamp-regler erstattes ikke af generelle nye standarder.
- Før nye forsøg: søg registry og PR #41's fulde forsknings-/testinventar. Ingen ny indpakning af en allerede set test som en ny holdout.
- Protokol, inputvintage, modelkode og resultater har stabile ID'er og hashes. Rettelser får nye versioner og begrundelser; beslutninger er append-only.
- Private managerdata forbliver uden for Git, Pages og offentlige CI-artifacts. En intention er ikke en faktisk udført transfer.
- Hver performancepåstand angiver target, population, regelår, informationscutoff, evalueringsklasse, sammenligning, usikkerhed og begrænsninger.
- Accept i forskningsregistret er ikke en produktionsdeploy. Overførsel kræver en separat integrations-PR.

## Nuværende evidensgrundlag

PR #41 kortlægger 178 forsøgsmapper/2.471 filer og 236 testfiler; det betyder ikke 178 uafhængige performanceforsøg eller at alle tests er genkørt. PR #42 retter audit-serialisering og tilføjer PM-dekomponeringer. De oprindelige GW8–10 giver 2.007 publicerede spillerobservationer/30 kampe. Disse outcomes er allerede set. Den officielle ep_next-baseline er sammenlignet korrekt i de gamle kildepakker; kommercielle modeller er ikke rangordnet uden data.

Der er kendte fejl i substitutionsantal/P90, komponent-/positionsfordeling og datadefinitioner. Stor individuel restfejl er ikke automatisk evidens for forkerte spillerparametre. TS's gamle sæsonreplays er ikke certificering af nutidens fulde seks-GW-/chipkæde. Den senest observerede substitutionsledger (21. november) har GW11 pending, 0 afsluttede nye GW/0 kampe.

## Permanent automatisk GW-cyklus — målarkitektur

1. **Før deadline:** gem original model-/inputversion, cutoff, publiceringskvittering, spiller-/fixture-ID, scorerule-version, checksum, fuld seks-GW-horisont og nødvendige fælles scenarier. Baseline og forskningsarm gemmes i adskilte navnerum. Private TS-state/anbefalinger går direkte til verificeret privat lagring.
2. **Når GW er final:** hent officielle labels med `finished && data_checked`, fixture-/spillerkodekontrol og eksplicit håndtering af blanks, DGW og flyttede kampe. Manglende labels er ikke nul. Labels kan få en dokumenteret korrektion; den oprindelige prognose ændres aldrig.
3. **Evaluér:** score MM/PM med proper scores og kalibrering. TS kræver korrekt original state, keep-control og kendt udførsel; ellers vises Not Available. Samme kamp/GW behandles som afhængige observationer.
4. **Opdatér forskning:** tilføj nye resultatversioner og registry-events. Præregistreringernes gates følges uden løbende tuning. Deskriptive signaler kan skabe en ny hypotese, men er ikke en godkendelse.
5. **Publicér:** lav en versioneret offentlig evalueringsrapport og opdatér Labs read-only-visning gennem en rapport-/UI-release med testede privatheds- og identitetsgrænser. Ingen modelpointer ændres af evalueringsjobbet.

Genbrug eksisterende GitHub Actions, originalt publiceret Git-historik, Pages og auditkode. Nye publiceringsjobs har kun nødvendige rettigheder og må ikke have adgang til private managerfiler eller tokens til privat compute.

## Etapeopdelt implementeringsplan for slutproduktet

| Etape | Konkret leverance | Definition of done | Afhængighed og planlægningsestimat |
| --- | --- | --- | --- |
| 0. Permanent forskningsfundament | Denne masterplan, metodik, 25 registreringer, kildekatalog, status og append-only beslutninger | Valideret registry; næste session finder en gyldig opgave og de allerede afviste retninger | Nu; ingen fits/simulationer |
| 1. Korrekte målinger og contracts | TS exact-small-harness; end-to-end public scorer; capture-schema-kompatibilitet og private storage gates | Originale scoretal reproduceres; DGW/blank/missing/revisions-tests; den rigtige frosne worker kan logges uden numeriske ændringer | Separat forsknings-/integrationsbranch; ca. 3–5 udviklingsdage, ikke en bestilling |
| 2. Automatisk versioneret GW-loop | Oprindelige snapshots, final labels, append-only evalueringer og jobstatus | Mindst én fuld live GW-cyklus uden manuel datarettelse; failed capture markeres, ikke udfyldes | Afhænger af etape1 og privat lagring; ca. 2–4 dage plus kalender-GW |
| 3. Research Lab MVP | Separat offentligt `/research-lab/` med MM/PM-scorekort, kalibrering, GW-grafer, fejlatlas, registry og modelhistorik | Dashboardtal matcher de versionerede JSON-rapporter; kildedrilldown, sample sizes og pending/unknown vises; ingen managerdata | Rapportkontrakt stabil; ca. 4–7 dage; ingen UI implementeres nu |
| 4. Videnskabelige eksperimenter | Uafhængig frozen-MM-serie, kontrollerede ablationer, PM-target-/coupling-tests og lovlige eksterne benchmarks | På forhånd låste targets/perioder og effektstørrelser; nye data og paired GW-usikkerhed; negative resultater bevares | Registry-/datagates; typisk12+ nyeGW; substitutionsforsøget har sin egen uændrede gate |
| 5. Avanceret Lab | Betinget usikkerhed, modelafhængige risikokurver, private TS-policyvisninger og isoleret parameter-/experiment explorer | What-if er tydeligt en forskningsarm; ingen live-write-adgang; ingen falske “% af optimum”-tal | Mere data og separat privat sikkerhedsreview; estimat først efter MVP |
| 6. Kontrolleret overførsel | Valideret kandidat → separat integrations-PR → regression/privacy/rollback → eventuel godkendt release | Reproduceret ny out-of-sample-gevinst, downstream safeguards og eksplicit versioneret rollback; Lab fortsætter efter release | Aldrig automatisk som følge af en p-værdi eller ændring i registry |

Estimater er grove udviklingsrammer, ikke dokumenterede runtimes eller køb. Infrastruktur og kalenderkrav er separate fra statistisk power. Et dashboard kan bygges før der er nok data til en effektpåstand, men skal vise netop det.

## Første tre anbefalede undersøgelser

1. **EXP-TS-SEARCH-001 — ready:** præcis, billig exact-small-reference mod frossen TS. Adskiller regel-/søgefejl fra prognosekvalitet. Ingen nye kampdata eller parametre kræves. Implementeringsharness mangler; det er næste gyldige nye arbejde.
2. **EXP-MM-LIVE-001 — awaiting data:** uafhængig evaluering af frossen MM fra første gyldige GW12-eller-senere origin-snapshot. GW8–10 gentages ikke som ny test; GW11 kan kun være deskriptiv under denne nye protokol. Informationsværdi er høj, men data-/collectorgates mangler.
3. **EXP-PM-DEFS-001 — ready:** målbare definitions-/dækningskontroller for CS, DC, saves og BPS. Bygger direkte på #42 og afgør, hvilke efterfølgende kandidatforsøg der overhovedet er identificerbare. Ingen BPS-point tilføjes endnu.

Den eksisterende substitutionsundersøgelse fortsætter sideløbende med uændret model/protokol. Capture-reparation i draft PR #43 er en data-infrastrukturafhængighed, ikke et nyt modelresultat.

## Dokumentkort og næste session

- [STATUS.md](STATUS.md): genereret, dateret oversigt; ikke en live jobmonitor.
- [METHODOLOGY.md](METHODOLOGY.md): targets, scores, afhængighed, ablationer og risikogrænser.
- [DATA_CATALOG.md](DATA_CATALOG.md): data/cutoffs/rettigheder og evidens.
- [BENCHMARKS.md](BENCHMARKS.md): eksterne baselines og TS-sammenligninger.
- [POWER_ANALYSIS.md](POWER_ANALYSIS.md): første power-/MDE-plan uden opdigtet power.
- [ARCHITECTURE.md](ARCHITECTURE.md), [LAB_PRODUCT_SPEC.md](LAB_PRODUCT_SPEC.md): permanente produkter, datastrømme og senere dashboard.
- [DECISION_LOG.md](DECISION_LOG.md), `events.jsonl`: beslutningshistorik og status-events.
- [REPRODUCIBILITY.md](REPRODUCIBILITY.md), [SESSION_HANDOFF.md](SESSION_HANDOFF.md): kommandoer, gates og præcis fortsættelse.

**Aktuel opgave er afsluttet, når denne plan/registry-PR kan læses og valideres af en ny session. Hele dashboardet og de fremtidige model-/pipelineændringer er ikke en del af denne release.**
