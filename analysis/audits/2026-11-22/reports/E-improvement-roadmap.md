# E. Improvement Roadmap

Højst tre modelforbedringer udvælges. Rangeringen er en faglig prioritering ud fra dokumentation og gennemførlighed, ikke estimerede garanterede procentsatser. Ingen af dem integreres i appen af denne audit.

| Prioritet | Forsøg | Dokumenteret potentiale | Data / kompleksitet / risiko | Beslutning |
| --- | --- | --- | --- | --- |
| 1 | Fælles, lovlig substitutionsproces | Konkret underestimeret antal indskiftninger; reused 20-match-test har lavere CRPS/P90-Brier, men højere minut-MAE og point-MAE for alle markspillere | Eksisterende historik; mellem/høj kompleksitet; rapporterede minutlabels og lille reused stikprøve | Fortsæt præregistreret forsøgsprotokol uændret; ingen ny tuning |
| 2 | Fælles defensive handlinger, DC og regelkonsistent BPS; keeper-subtyper som afgrænset deltest | Positionsskævheder og manglende conditional kobling verificeret; rå inside-save/xGOT findes; keeper-rate-test giver lille usikker gevinst | God begyndende datadækning; høj kompleksitet; dobbeltregning og targettransport er centrale risici | Isolerede, rækkefølgefastlagte ablationer før fuld integration |
| 3 | Nyt cutoff-verificeret tilgængeligheds-/forventet-XI-signal ud over eksisterende rolle/status | Start-oracle viser stor fejlmargin; DOUBT/rotation er svære; ingen dokumenteret ny providergevinst endnu | Kræver tidsstempler og tilladt data; mellem/høj kompleksitet; stor look-ahead-risiko | Først dækning/retrospektiv tidsaudit, derefter ny fremadrettet test |

## 1. Bevar det frosne substitutionsforsøg

Kandidatfit-hash `726ae5cf7d7bf5645672c98e02fefadc14a7004fcfda04e0e0737dbc6a9a5fdb`, kernel-hash `abfb400bf4030d3c50101edf19db4390d2d2d31cb4e7e0e669f9744b820bf6d8`. Hovedmålet er point-CRPS for markspillere med reference-P(start) ≥0,20. Minimum otte nye afsluttede GW og 80 kampe; whole-GW parrede bootstrapintervaller. Krav om CRPS-forbedring, point-MSE-non-inferiority, ingen forværring af CRPS i rotation/regular og højst 1 % forværring af minut-RMSE; alle identitets-, klokke- og lovlighedsgates skal bestås.

Den senest hentede driftskvittering fra 21. november har GW11 afventende og nul afsluttede nye kampe. En efter-deadline capture er korrekt sprunget over; det betyder ikke, at den tidligere før-deadline capture mangler. Ingen automatisk promotion er autoriseret. De 20 gamle testkampe må ikke tælles med i de 80 nye.

## 2. Skil forbedret data fra en forbedret model

Frys først definitioner og missingness. Test ordinære keeper-save-subtyper alene, derefter regelkonsistent baggrundsmål, derefter fælles DC/BPS-residualproces. Udfør ikke et stort samlet redesign, hvor det er uklart, hvad en eventuel gevinst kommer fra. Bevar mål-/assist- og minutprocessen i disse deltests. Når et eksplicit BPS-bidrag tilføjes, skal den eksisterende baggrund retargeteres, så samme bidrag ikke tælles to gange.

Brug kronologiske fits uden target-kampens labels, samme arkiverede fixture-input og fælles tilfældige tal hvis en ny simulation er nødvendig. Mål total-point-CRPS og point-MSE samt keeper-/positions-BPS, bonuskalibrering og DC-rate. Ny evidens kræves: den første keeper-rate-test er mod en simpel historikmodel, ikke den aktive keeperlov, og dens 95 %-interval inkluderer ingen gevinst. Ingen ekstra penalties vælges på de allerede sete GW8–10.

## 3. Et nyt informationstilskud, ikke endnu en kopi af workload

Skadesstatus, tidligere XI, rollehistorik og cupbelastning bruges allerede. Et nyt signal skal derfor vise inkrementel værdi efter disse features. En press conference efter kampstart eller officiel XI efter FPL-deadline er ugyldig. Gem nyheds-/XI-observationer før deadline med tilladt brugsret, og test både start-Brier/log loss, minut-RMSE og point-CRPS. Brug hele klub-/GW-blokke og vis dækning, abstentions og fejl på raske startere, så højere MAE ikke skjules ved blot at sætte flere spillere til OUT.

## Hvad vi ikke prioriterer igen nu

- Generel nedskalering af høje angrebsshares: større eksisterende ablationer forværrer samlet RMSE.
- Nyt dynamisk holdfilter fra bunden: bedre end en simpel baseline er ikke bedre end den faktiske nuværende model; tidligere matched tests støtter ikke promotion.
- P90 ×0,8 som løs rettelse: kan bryde udskiftningsreglerne og kalibrerer ikke en fælles proces.
- Nye HMM-/duration-varianter på de samme genbrugte runder uden ny evidens.
- Køb eller automatisk scraping af kommercielle prognoser uden verificerbar historik og genbrugsret.

## TS: et nødvendigt evidensarbejde, ikke en fjerde udvalgt modelændring

Inden TS-vægte, FT-buffer eller chipregler optimeres, skal fulde før-deadline-vintages og managerstates gøre evalueringen gyldig. Gem anbefaling, keep-squad-kontrol, kaptajn/vice, budget, hits, FT-overgang, chips og forecast-hash. Adskil en én-rundes kontrolleret action-sammenligning fra stateful sæsonforløb. Verificér beslutnings- og regelkorrekthed billigt; genkør kun dyr søgning, hvor en konkret ubesvaret hypotese kræver det. Dette datagrundlag er ikke til stede nok til at oplyse en sikker chip-/transfergevinst nu.

## Fælles integrationsgate

En senere PR skal dokumentere fast protokol, kendt cutoff, predeclared population/primært mål, passende reference fra den aktive model, ny evalueringsperiode, parret usikkerhed og subgroup-gates. En fuld holdscore eller lav samlet bias kan ikke erstatte disse kontroller. Produktionsintegration sker i en separat, begrundet ændring; denne audit-PR er kun evidens og evaluering.
