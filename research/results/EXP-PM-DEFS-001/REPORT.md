# Fase 2 — PM-definitioner og datadækning

**EXP-PM-DEFS-001 · 22. november 2026 · ny opgave fra PR #48.**

Leverancen er et nyt versionsstyret katalog og datakontrakter, ikke en gentagelse af TS eller de gamle komponentaudits. `PM-COMPONENTS-1.0.0` indeholder **24 definitioner**, en entydig pointpartition og tre særskilte regelversioner. Der følger JSON-schema, eksekverbare kontrakter, kildehenvisninger og tests med. MM B, PM vFinal, TS v3, appen, C2-arbejdet og substitutionsforsøget er uændrede.

## Faktiske nye resultater

- De nye kontrakter accepterer **2.007 originale prognoser og 2.007 matchede faktiske komponentregnskaber** uden kontraktfejl. Der er **2.011 officielle rækker**; fire uden prognose tælles som manglende forecastdækning, ikke som nye prognoser.
- Alle 2.007 arkiverede prognoser har kontrollerbare mål-/straffesparksopdelinger og penalty-miss-delkomponenter. De stemmer med forældrekomponenterne og tælles ikke igen i totalsummen.
- Officielle arkiverede `game_config.scoring`-vægte matcher katalogets relevante pointkonstanter. Tre originale før-deadline-vintages og afsluttede/datacheckede labelrunder er verificeret som kontraktforudsætninger. Ingen prognose omskrives.
- Anvendelsen tog **1,56 sekunder**. **35 tests består**, herunder 24 nye kontrakt-/identitetstests og 11 eksisterende registrytests. Ingen model, simulation, fit, TS-kørsel, bootstrap eller ny præcisionsanalyse er udført.

Disse tal er **schema-/enheds-/identitetskontrol på eksisterende data**, ikke nye uafhængige observationsrunder eller dokumentation for bedre prognoser. PR #32's kalibrering, PR #41's BPS/DC-regelkontrol og PR #42's dekomponeringer er genbrugt med kildehash; de er ikke genkørt som nye studier.

## Definitioner, som nu er kodificeret

| Område | Kontrakt og konsekvens |
| --- | --- |
| Mål og assists | Holdmål inkluderer modstanderens selvmål; spillermål gør ikke. Straffesparks-/øvrige mål er en partition. FPL-assists følger officielle kategorier og kan ikke erstattes af xA/Opta-assists. Selvas­sist og dobbelte event-ID'er afvises. |
| Clean sheets | Hold-CS og kvalificeret spiller-CS er forskellige targets. 60+ FPL-minutter og relevant mål-imod-ansvar kræves; post-udvisningsansvar kan ikke rekonstrueres fra on-pitch-only tal. Produktet af marginale sandsynligheder erstatter ikke den fælles forventning. |
| DC | To point én gang pr. kamp ved DEF10 / MID-FWD12; ingen 60-minuttersgrænse. 2024/25 havde ikke dette pointmål. DGW-tællinger må ikke samles før threshold. |
| Saves | Totaltællingen inkluderer straffesparksredninger; deres særskilte fem point er lovlige. Inside- og big-chance-sæt overlapper. Ukendt subtype er ikke nul. `E[floor(S/3)]` er ikke `floor(E[S]/3)`. |
| BPS og bonus | BPS er ikke direkte FPL-point. Den fælles kamp-rangering og ties afgør bonus; negativ BPS må ikke filtreres væk. Rangering af middel-BPS er ikke forventet bonus. |
| Dobbeltoptælling | Ti additive komponenter; gammelt `expected_bonus` mappes én gang til neutralt `bonus_points`. Penalty-miss og mål-underopdelinger er diagnostik. Eksplicit BPS-led kan kun erstatte samme-led-i-residual med kendt partition; en identitet inden for ét target beviser ikke regeltransport mellem sæsoner. |

Den samme defensive handling må gerne give DC-point **og** påvirke bonus gennem BPS efter reglerne; det er ikke i sig selv dobbeltoptælling. Tilsvarende må en straffesparksredning give både sin særskilte belønning og indgå i de relevante save-regler.

Kort ved nul rapporterede minutter, ændret keeperrolle, ukendt udvisningstid og rå gul/rød-kodning behandles eksplicit. Det er grænsetilfælde i datakontrakten, ikke nye empiriske fund om modelgevinster eller en rettelse af den frosne scorer.

## Hvad findes, og hvad mangler?

[Datadækningsrapporten](COVERAGE.md) og [feltmatricen](field-coverage.csv) skelner mellem direkte label, afledt target, manglende felt og uidentificerbar fordeling:

- Aktuelle officielle stats indeholder mål, assists, CS, saves, DC, BPS og bonus. De arkiverede per-player-scenarier indeholder kun totalpoint/minutter; de identificerer ikke den fulde BPS-/hændelsescovarians.
- PR #32 har historiske `p_bps`, `p_bonus`, `bg_rate/bg_sd` samt labels, men ikke samme informationssæt som de aktuelle publiceringspakker. Gamle spiller-CS var regelafledte; 2024-DC-labels mangler, og visse 2025-BPS-residualer har kun bounds.
- Den tidligere providerkvittering beskriver 141 inside-save-rækker, 133 strengt afstemte og ingen eksplicitte big-chance-save-flags. Den er genbrugt evidens, ikke et nyt rådatasæt her. Officiel kategori-mapping og viderebrugsrettigheder er ikke verificeret.
- **Nogle targets kan allerede identificeres:** for outfield i én relevant kamp er `P(DC-award)=E[DC-point]/2`. Kvalificeret spiller-CS kan tilsvarende udledes ved positiv positionskoefficient. Det identificerer hverken hold-CS, hele countfordelingen eller bonus' afhængighedsstruktur.

Manglende almindelige big-chance-redninger, præcise exit-/korttider og event-/baggrundspartitioner må ikke erstattes med nul eller en vilkårlig xGOT-tærskel. Nutidige officielle regelartikler er daterede kilder, ikke bevis for deres oprindelige historiske tilgængelighed.

## Konkret næste eksperiment

**Præregistrér en fremadrettet, frossen DC-threshold-validering** på nye originale før-deadline-prognoser. Den kan udnytte de allerede identificerbare DC-hit-sandsynligheder og officielle labels uden nye BPS-subtyper eller modelparametre. Primært Brier-score og kalibrering med på forhånd fastlagte grupper, periode/powerplan og GW-afhængighed; aldrig en ny test på de gamle GW8–10. Første gyldige origin skal stadig være fremtidig efter registrering.

[Næste-eksperiment-protokolskitsen](../../pm_defs/NEXT_EXPERIMENT.md) beskriver dette samt de ekstra datagates for en senere CS/BPS-/inside-save-kandidat. Der er **ikke** registreret eller udført en ny kandidat i denne opgave. `EXP-PM-CS-BPS-001` beholder sine oprindelige endpoints og afhængigheder. En fuld kandidat kræver nye paired outcomes og downstream-safeguards; ingen automatisk promotion eller deploy.

## Reproduktion og begrænsninger

Katalog: [CATALOG.md](../../pm_defs/CATALOG.md). Kommandoer, kildehash og original registreringsrækkefølge: [REPRODUCIBILITY.md](../../pm_defs/REPRODUCIBILITY.md). Den første harness blev stoppet før dataanvendelse af en checksum-stitypefejl; originalen og fejlen er bevaret. Den separat præregistrerede v2 rettede kun stihåndteringen og gennemførte kontraktkontrollen med uændret katalog og input. En senere test-syntaksfejl blev rettet før tests kunne afvikles; ingen studieresultater blev ændret.

Studiet er færdigt som definitions-/dækningsarbejde. Uafhængigt fagligt review af kode/resultater er fortsat udestående; det er ikke en godkendelse af alle historiske regelscorere eller af en modelrelease.
