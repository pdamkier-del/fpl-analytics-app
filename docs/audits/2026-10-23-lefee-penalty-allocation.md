# Hvorfor Le Fées xP bliver højt

Undersøgelse af det publicerede B-forecast `eef055ef9aa0bd3d8a013b05e3e309b326ff98298171bc9a2cccd361c6d2a134`, data-as-of 23. oktober kl. 09.42 dansk tid. Ingen model, prognose, personlig holdtilstand eller produktion er ændret.

## Fundet mekanisme

De almindelige mål fordeles efter en målrate baseret på **inklusive xG**, mens scorede straffespark fordeles i en særskilt proces. Straffesparks-xG påvirker dermed også spillerens vægt blandt almindelige målscorere. Holdets samlede mål forøges ikke: simulatoren trækker forventede straffesparksmål fra den almindelige holdintensitet. Problemet er fordelingen af holdets almindelige mål mellem spillerne. Det gælder generelt for straffesparksskytter.

Kodevejen er `deadline_components.player_components_at_deadline` (xg-rate) → `vfinal_replay_components.build_fixture_components` (rolleprior og performancevægtet målfordeling) → `phase4b` (målrate pr. spilminut) → `joint_simulator.simulate_match` (samme mål-vægt bruges til almindelige mål; særskilt valg af straffesparksskytte). Den oprindelige rate/rolleprior indeholder ingen eksplicit npxG-adskillelse.

## Le Fées faktiske afslutninger

Den samme FotMob-kildes syv afsluttede Premier League-kampe indeholder 12 afslutninger, heraf to straffespark. De to straffespark er verificeret mod den eksisterende event-/identitetsledger: scoret i GW3 og reddet i GW4. Der læses kun den kanoniske shotmap, og skud-ID'er kontrolleres for dubletter; samme skud optræder flere steder i rå JSON og må ikke tælles flere gange. Alle syv kampe har verificeret shotmap og afsluttet kampstatus.

| Samme afslutningskilde, GW1–7 | xG |
| --- | ---: |
| Samlet xG | 2,0810 |
| Straffesparks-xG | 1,5768 |
| xG uden straffespark | 0,5042 |

Cirka **75,8 %** af hans xG stammer fra straffespark. Officielle FPL-tal summerer til 2,09 xG, 1,60 xA og 608 minutter. Kildernes afrunding er forskellig; der trækkes ikke ukritisk FotMob-penalty-xG fra et FPL-total og kaldes det præcist FPL-npxG. I ablationen bruges den verificerede non-penalty-andel fra samme udbyder til hvert af FPL's kampinput.

## Kontrolleret simulation

Den oprindelige 400-træks kørsel reproduceres præcist med de frosne aktuelle input, samme seed og den aktive B-rolle-/keeperproces: **5,52 xP**. Heraf er 0,3425 almindelige mål og 0,045 scorede straffespark, altså 1,7125 + 0,2250 målpoint. Den direkte straffesparkskanal er derfor kun en lille del af de 1,9375 målpoint.

Derefter fjernes kun de to straffesparks bidrag til Le Fées individuelle historiske xG-rate. Halveringstid, den eksisterende inklusive rolleprior, performancefeatures, holdets målprognose, hele MM-/rollefordelingen og straffesparksprocessen fryses. Den samme shrunk-rateformel giver 0,26627 → 0,12817 målrate pr. 90. Den eneste ændrede simulatorparameter er hans vægt ved fordeling af almindelige mål. Da målfordeleren er lineær i denne rate før fælles normalisering, svarer vægtændringen til den isolerede rate-ablation med frosne øvrige kanaler. Der fits eller tunes ingen parametre.

| Måling | Original | Isoleret ablation |
| --- | ---: | ---: |
| xP, oprindelige 400 træk | 5,5200 | 4,7575 |
| xP, særskilt 4.000-træks kontrol | 5,3760 | 4,61975 |
| Almindelige mål, 4.000 træk | 0,31575 | 0,17775 |
| Scorede straffespark, 4.000 træk | 0,0435 | 0,0435 |
| Spilleminutter, 4.000 træk | 85,8695 | 85,8695 |
| Bonuspoint, 4.000 træk | 0,6185 | 0,44425 |

I 4.000-træks kontrollen er både hans minutter, hans scorede straffespark og holdets samlede mål **identiske i hvert enkelt træk**. xP-forskellen på −0,75625 kommer fra ændret mål-/assist-/bonusfordeling. Parret Monte Carlo-standardfejl er 0,03428; den beskriver simulationsstøj under disse frosne antagelser, ikke prognosefejl eller en historisk gevinst.

Den officielle frosne straffesparksrækkefølge er Diarra 1, Le Fée 2. Den eksisterende B-simulator respekterer rækkefølgen blandt spillere på banen. Le Fées historiske penalty-vægt på cirka 94 % må derfor ikke udlægges som hans faktiske ubetingede chance for at tage næste straffespark.

## Konklusion og afgrænsning

Årsagen er bekræftet som en individuel fordelingsmekanisme: historiske straffespark påvirker også almindelige mål, og målpoint øger samtidig bonusforventningen. De cirka 86 minutters spilletid og xA-bidrag er andre, bevarede drivere.

**4,62 er en diagnostisk ablation, ikke et færdigvalideret nyt xP-tal.** En generel rettelse skal adskille non-penalty xG fra straffespark for alle spillere og behandle rolle-/populationspriorer og relevante performancefeatures konsistent. Derefter kræves historiske sammenligninger, blandt andet for skift af skytte og fordeling til holdkammerater. De nuværende rolle-/performanceparametre er udviklet på inklusive data og kan ikke automatisk erklæres korrekte efter et inputskift. Ingen spillerbestemt reduktionsfaktor er indført i appen.

[Maskinlæsbar kontrol og kildehashes](../../analysis/results/lefee-penalty-allocation-20261023). Reproducer efter gendannelse af det offentlige inputartefakt og de SHA-verificerede rå afslutningskilder:

```sh
PYTHONPATH=src:scripts:. /workspace/fpl-venv/bin/python scripts/locked_numerical_runtime.py analysis/audit_lefee_penalty_allocation.py --inputs /tmp/fpl-fresh-role-evidence/work/current-B-inputs --forecast /tmp/fpl-fresh-role-current/current/forecast.json --out /tmp/fpl-lefee-penalty-probe.json
```
