# Kort beslutningsoversigt — FPL Research Lab

Vi bygger to permanente produkter: FPL Analytics til brugerens beslutninger og FPL Research Lab til dokumentation, evaluering og eksperimenter. Fælles grundlag er versionerede originale prognoser og data. Lab kan foreslå en forbedring, men kan ikke automatisk ændre appens modeller.

Masterplanen har syv etaper: forskningsfundament → korrekte måle-/capturekontrakter → automatisk GW-cyklus → visuelt Lab-MVP → uafhængige forsøg → avanceret usikkerheds-/parameterundersøgelse → kontrollerede integrationsreleases. Den nuværende opgave leverer alene plan, register og arkitektur.

## Første tre anbefalinger

| Forsøg | Hvorfor først | Status og næste handling |
| --- | --- | --- |
| **EXP-TS-SEARCH-001** | Billig, uafhængig kontrol af lovlighed og søgekvalitet, uden fremtidige kampdata. Skelner algoritmens fejl fra prognosens støj. | Klar til implementation; et lille exact-reference-harness skal skrives. Intet nyt sæsonreplay eller parameterfit. |
| **EXP-MM-LIVE-001** | Ny, reelt uafhængig dokumentation af frossen MM. Gamle gode scoretal kan ikke genbruges som nye resultater. | Afventer valideret original-vintage-collector og nye GW; tidligst nye origin-GW12-prognoser. |
| **EXP-PM-DEFS-001** | Forhindrer, at vi korrigerer forkerte targets eller tæller BPS-bidrag dobbelt. Genbruger #42's resultater. | Klar til definitions-/dækningsarbejde; ingen ny PM-kandidat eller simulation endnu. |

Substitutionsforsøget fortsætter med helt uændret protokol. Det har senest registreret GW11 pending og0afsluttede nyeGW; nye programmeregler erstatter ikke dets8GW/80kamp-gate.

Draft PR43 bevarer det operationelle integrationsarbejde separat. En rigtig frozen-worker-test fandt en bench-role-kontraktfejl; privat vedvarende lagring og flere datagates er heller ikke verificeret. Den er ikke release-klar og ikke deployet.

Vi kan måle aktuelle scoretal, kalibrering, fejlafhængigheder og præcis optimalitet i afgrænsede små testdomæner. Vi kan endnu ikke angive en verificeret procentdel af “optimal præcision”, sikker nutidig TS-/chipgevinst eller kommerciel head-to-head-score uden valide data. Powerplanen viser, hvordan dette skal afgøres; den opfinder ikke power fra tusindvis af afhængige spillerrækker.

Næste session starter med `MASTER_PLAN.md` og registry-kommandoerne. Der findes25registreringer, oprindelig evidens og en eksplicit append-only beslutningshistorik. Ingen aktive modeller, app-UI eller produktionspipelines ændres af denne PR.
