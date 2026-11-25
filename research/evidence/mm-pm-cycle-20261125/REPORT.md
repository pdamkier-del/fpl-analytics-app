# C1-afslutning og løbende MM-/PM-drift — 25. november 2026

**C1's vedligeholdelsesarbejde er klar til review. Automatisk drift på main er endnu ikke aktiveret og må ikke erklæres verificeret.** Der er en ny gyldig originalprognose, men GW12 er ikke afsluttet. Ingen nye præcisionsresultater eller modelgevinster rapporteres.

## Klar og verificeret

- PR54's originale tidsgrænser, seks-GW-arkiv, origin-only scoring, 16-origin-vindue, 30-dages datalås, 12-GW/120-kamp-reviewminimum og frosne modeller er bevaret. Alle66tidligere registrerings-JSON'er og gamle resultater er uændrede. TS-funding er færdig/afvist; ingen ny TS-kørsel.
- Ny original: revision `9e03db632b5297c24238e55002baa9992156f9006e510993adc6d501552f2a41`, forecast `4ff695e3a59bb9d398fbdc5e1dc09040004d392acaf6ecacff3554fe4e33550a`. Datatid23Nov13:19:06UTC, komplet offentliggørelse23Nov20:32:44UTC; begge efter registrering23Nov11:04:39UTC. Hele arkivet gendannet og fuldt C2-valideret:674spillere, GW12–17,400fælles scenarier. Prognosen opfylder de nuværende issuekrav; den endelige, seneste originale origin-selection afventer stadig cutoff.
- Aktuel officiel GW12-metadata: `finished=false`, `data_checked=false`. Deadline27Nov18:30UTC(19:30dansk); selection-cutoff17:30UTC(18:30dansk). Både pinned v2 og den særskilt registrerede v3-preflight svarer `awaiting_selection_cutoff`,0scorede origins. Ingen event-live-udfald er hentet.
- Eksisterende finality/identitets-/DGW-/blank-/regnskabs-/immutable-revision-tests genbruges. Aktuelle checks: **94består**, to historiske snapshot-tests er erstattet af versionerede, semantiske metadata-checks i den nye testkommando. Gamle testfiler og PR54's v2-manifest er stadig byte-identiske. Registeret validerer66entries; beskyttet substitutionsforsøg stadig8GW/80kampe.

## Reel fejl og rettelse før første scoring

Den nye MM-original indeholder363`p_play`-værdier en maskinafrundingsrest under0, maksimalt2,220446049250313×10⁻¹⁵. PR54's strenge `metrics.probability` ville afvise dem ved scoring, selv om originalarkivet kan gendannes og validere. Det er en **evaluator-kompatibilitetsfejl**, ikke målt dårligere MM-præcision.

Versioneret v3 bevarer originaldata og gamle evaluatorfiler og bruger samme metrics/targets. Kun ved beregning af en sandsynlighedsmetrik normaliseres boundary-roundoff indenfor1e-12til0/1; substantielle fejl/NaN/inf afvises stadig. Der logges antal og største korrektion. Tests viser identiske resultater for allerede gyldige værdier, bevarede rådata og korrekt oprydning også ved fejl. Alle24.264kontrollerede probability-inputfelter på den nye original er kompatible med guarden. Ingen rigtige kampresultater er genberegnet.

Implementering/kommando/manifester er registreret før v3's read-only live preflight. Review af denne numeriske implementeringsrettelse er fortsat en aktiveringsgate. Den ændrer ikke den videnskabelige protokol og er ingen kandidat til bedre fodboldprognoser.

De gamle testfejl var1)fast65mod nu66registreringer og2)fast11reconciliations plus antagelsen om, at observation altid sker i initialstatus. Der var allerede13ved PR56. Nye tests verificerer eventregistreringer mod JSON'er, alle gamle protokolhashes, substitutionsgaten samt state/implementation på det faktiske eventtidspunkt. Gamle snapshot-checks kan reproduceres ved deres oprindelige pins. `verify_current.py` erstatter kun disse to specifikke tests; integritets-, tamper- og scientific-contract-checks bevares. Et ukritisk fuldt pytest-kald på historiske snapshots har derfor stadig de to kendte snapshots som forventet inkompatibilitet; det er ikke en skjult grøn fuldsuite.

## C2: præcise driftsgates

PR55 er stadig OPEN/ikke merged. Den observerede succes45184237876er PR-verifikation; publishing blev ikke aktiveret. Main står påd4d6e804og indeholder ikke evalueringswrapperen. Workflow-API'ens `active`-status alene beviser ikke main-drift.

C2 skal gennem review opdatere PR55 til den nye reviewed evaluator-pin, nye metadata-checks og `run_online_v3.py`. Bevar den eksisterende read-only/publish-adskillelse og pinned archive/runtime. [REVIEW.md](../../mm_pm_maintenance/REVIEW.md) er den konkrete C1→C2-overdragelse med kommandoer og nødvendige driftskvitteringer. Ingen merge/dispatch/publication er udført her.

Arkiveringsworkflowets tre seneste observerede kørsler fejler; seneste45595239869fejler i original-artifact/permanent-recovery-steppet og annoterer `Public forecast archive incomplete`. Den præcise underliggende kildeårsag kunne ikke verificeres: log/status-artifact-redirect var utilgængelig. Den allerede gendannede gyldige Release findes stadig. C2 skal læse den autoriserede statuskvittering og afklare fremtidig capture før pålidelig hver-GW-drift kan certificeres. Der bygges ikke en parallel pipeline eller omgås adgangskontrol.

## Løbende modeludvikling — uden at vente på 12 GW

[CYCLE.md](../../mm_pm_maintenance/CYCLE.md) beskriver: ny original → automatisk frossen evaluering efter official finality → understøttet, foreløbig fejldiagnose → isoleret kandidat på udviklingsdata → ny preregistreret test → eventuel separat integration. GW12kan, når afsluttet, give hypoteser; den kan derefter ikke bekræfte en kandidat afledt af de hypoteser. Frosne baselineprognoser og PR54-reviewvindue ændres aldrig. Kandidatudvikling behøver ikke vente på det samlede baseline-review; den skal blot have sit eget uafhængige testgrundlag og må ikke tilpasses løbende på det.

**Højst ét muligt modelspor:** genbrug den eksisterende PR42-hypotese om PM's assist-eligibility/rate med uændret mål-/minutproces. Det er ikke et nyt fund eller en ny skalafaktor. Gamle data forklarer størstedelen af assistbias via målvolumen, og timestamp-valide eventkategori/winner/taker-labels samt en reelt ny, isoleret fejl er endnu ikke etableret. Derfor er ingen prediktiv kandidat implementeret/registreret eller optimeret nu. Den konkrete datagate og testdesign ligger i CYCLE.md. Bredeste diagnoseprioritet er fortsat MM's start/eksponering og PM-komponenter; originale prospective reports afventer nye afsluttede kampe.

## Lukket versus afventende

**Lukket i denne fase:** input-/arkivverifikation, versioneret numerisk rettelse/tests, aktuelle registerchecks, data-/reviewgrænser, C2-overdragelse og proces for aktiv videnskabelig modeludvikling. Ingen yderligere større C1-modeludvikling er nødvendig for at bringe den frosne evaluering til review.

**Afventer:** uafhængigt implementation-review og C2's minimale PR55-pin/command integration/merge, årsagen til aktuelle arkiveringsfejl, main-driftskvittering og første komplette officielle GW12→rapport-recovery. Før disse er løst er automatisk end-to-end-drift ikke certificeret. Ingen fremtidige resultater, bedre model, promotion eller produktionsdeploy erklæres.
