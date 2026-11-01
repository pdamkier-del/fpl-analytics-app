# Tydelig chipanbefaling på B-transfersiden

Problemet var, at den normale TS-plan blev vist som hovedanbefaling, mens et anbefalet Wildcard lå i et sammenfoldet diagnostikafsnit med `USE_NOW_DIAGNOSTIC`. Brugeren kunne ikke afgøre, om WC skulle bruges nu eller senere.

B-transfersiden begynder nu med en særskilt chipboks:

- “Brug Wildcard nu i GW …” kræver, at koordinatorens chipvalg, chiprækkens beslutning, aktuel GW og chiptilgængelighed stemmer overens. Samme fremgangsmåde gælder FH og BB; TC beholder manuel beslutning.
- Chipholdets næste-GW-score, forventet gevinst og margin over modellens udøvelsesgrænse kommer direkte fra det eksisterende chipresultat. WC-gevinsten mærkes som vægtet seks-GW-beslutningsværdi, ikke ekstra næste-GW-point. Manglende værdier opfindes ikke.
- Et udfoldeligt chiphold viser XI, kaptajn, vicekaptajn, bænk, eventuelle køb/salg og bank fra kandidatresultatet. Spillerne har links til eksisterende kort. Normale transfers, XI og horisont er mærket som alternativ uden chip, når en chip anbefales.
- Ved normalt valg vises gemmebeslutningen og at en senere WC-GW ikke er fastlagt. Ved manglende, inkonsistent eller utilgængeligt chipresultat vises ingen anbefaling. Manglende TC-scenarier står udtrykkeligt som en ufuldstændig sammenligning.

Ingen ny modelkørsel eller ændring af MM, PM, TS, chipgrænser, forecasttal eller privat holdlagring. Produktionsskabelonen `app/plan-view.js` er uændret; præsentationen tilføjes kun i den kopierede B-transferside.

## Kontrol

`analysis/verify_transfer_chip_advice.cjs` bruger tydeligt syntetiske chipresultater til UI-tests; det er hverken brugerens private plan eller en test af chipmodellens præcision. På desktop/mobil kontrolleres aktuel WC/GW, adskilte tal, chip-XI og normalt XI, køb/salg, manuel TC, gemmebeslutning, ingen opdigtet fremtidig WC-GW, afvisning af manglende/utilgængelige/forkert-GW-valg, uændret plan/holdlagring, ingen privat POST og ingen overflow/sidefejl. Den eksisterende transferresultat-browserregression består også. Begge beviser findes i denne mappe.

Den nye browserkontrol er tilføjet til den isolerede B-publicering sammen med de eksisterende regressioner. Offentlig verifikation tilføjes efter publicering.

## Publiceret og verificeret

- [Offentlig transferside](https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/app/transfers-classic.html). [Publicering 40309899441](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/40309899441) bestod med UI-kilde `cabef3f355c2ce6224c599cdd7a9a534c1f0c512`.
- CI: **1.025 tests bestået på 37,70 sekunder** og alle eksisterende browserregressioner samt den nye chipbrowserkontrol bestod.
- Den offentlige app er efter deployment testet på desktop/mobil med normal TLS-verifikation og syntetisk lokal chipplan. Samme kontroller består: chip før normalplan, klar GW, korrekte viste kildetal, separate hold, ingen overflow/sidefejl/privat POST eller ændret manager-state. Testen giver ingen udtalelse om brugerens private chipberegning.
- Alle **88 produktionsfiler** matcher den bevarede produktionsartefakt; produktionsforecast er byteidentisk før/efter denne publicering. Alle tre numeriske B-filer matcher den genbrugte validerede kørsel `40278297143`; modelkilde fortsat `03d5c4d4777b44bc1d37884a1cf4dde106b45cab`. Intet nyt forecast eller matematisk chipvalg blev opfundet til UI-ændringen.
