# B-preview: rollefordeling og historiske sæsoner

Opfølgning på [den samlede kravgennemgang](2026-10-22-full-chain-review.md) og [rolleimplementeringen](2026-10-22-joint-role-implementation.md). Den oprindelige audit bevares som historisk status.

R02/R06 har nu en fælles, historikbaseret spiller/rolle-fordeling før MM og PM. R03 bruger eksisterende match-importance efter korrekt normalisering af konkurrencer og runder. Produktionssimulator og TS-defaults er uændrede. Historiske tal og begrænsninger fremgår af rolleimplementeringen; de små xP-forskelle er ikke statistisk sikre forbedringer. Den fulde numeriske kilde `2b8393a932c7ed5de0f3334cc024915b909e6442` bestod [CI 39832070543](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39832070543).

D03 er implementeret i det eksisterende desktoplayout: fire verificerede Core-sæsoner, 2022/23–2025/26, med søgning, klubfilter, spiller- og holdvisning samt kampdetaljer. Links fra spillerkort og klubsiden åbner den relevante historik. Nuværende prognoser forbliver på spillerkortet. Historiske klubber bestemmes af den faktiske kamp, ikke den aktuelle registrering. Klubfilteret bruger spillerens tal for netop den klub, inklusive klubskifter.

Eksporten indeholder 1.520 kampe, 113.260 spiller/kamp-rækker og 3.040 hold/kamp-rækker. Alle 3.352 filer og hver eksporteret statistik er afstemt mod den frosne, skrivebeskyttede Core-database. Spillere forbindes mellem sæsoner med verificerede stabile FPL-koder fra de oprindelige kildefiler; alle otte identitetskilder matcher Core-manifestets SHA256. Der bruges ingen fuzzy identitetsmatch eller opfundne manglende tal. Team-xG er mærket som summeret spiller-xG, og ufuldstændige summer er null. Retrospektive data fremstilles ikke som gamle prognoser eller dokumenteret viden før en deadline.

Lokale kontroller: 850 Python-tests og alle 27 JavaScript-testsuites bestået. Historikbrowserkontrol på desktop og mobil bestået for alle fire sæsoner, detaljer, filtre, spillerlink og bevaret lokal manager-state, uden private POST-kald. De separate [kvitteringer](../../analysis/results/b-role-history-release-20261023) indeholder ingen private brugerhold, købspriser eller jobnøgler. Den offentlige endekontrol er registreret nedenfor.

Denne levering erklærer ikke R04 (valideret kommende CL-prioritering), R05 (latent fraværsårsag), M08 (uafhængigt kalibrerede minutintervaller), P08/P09 (fuld kausal sjældne-hændelser/særlig-assist-model) eller T06/T07 (uafhængigt helsæson-/chipafkast) løst. Tidligere forkastede afslutningsevne-kandidater er fortsat deaktiveret. Brugerens faktiske lokale hold er ikke opfundet eller overskrevet.

## Publiceringsbeskyttelse

Den aktuelle numeriske kørsel [39917460202](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39917460202) bestod alle modelkontroller. Dens senere deploy-job blev afvist, fordi GitHub Pages kun tillader `main`. Denne beskyttelse er bevaret. Udgivelsen køres derfor fra `main`; genbrug af det beståede numeriske artefakt kræver, at hele den oprindelige wrapper er byteidentisk med den tidligere godkendte wrapper i main-commit `e4906926cfaf210f5280fd101fa4e004b097347a`, at denne commit fortsat er en main-ancestor, at numeriske kilde-/workflowpins er præcise, og at det numeriske job er bestået. Et ændret workflow, en ukendt ancestor, fejl i modeljobbet eller et udløbet/ambiguøst artefakt afvises. Alle UI- og produktionsintegritetskontroller køres igen før deploy. Den ekstra recovery-test består.

## Publiceret og endekontrolleret

[B-preview i den eksisterende app](https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/app/transfers-classic.html) og [historikvisning](https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/app/history-classic.html). [Publicering 39921451927](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39921451927) er bestået, inklusive 850 Python-tests på 49,20 sekunder, samtlige UI-gates og Pages-deploy. Numerisk kilde er `2b8393a932c7ed5de0f3334cc024915b909e6442`; UI-kilde er `5c45c2c2a5fcb1846f4a33ad58858406e1fcb909`.

Det publicerede forecast er `eef055ef9aa0bd3d8a013b05e3e309b326ff98298171bc9a2cccd361c6d2a134`, data-as-of 23. oktober 2026 kl. **09.42.37 dansk tid** (07.42.37 UTC), GW8–13, 668 spillere, 60 kampe og 4.008 spiller/kamp-rækker. En kamp og én GW reproducerer de tilsvarende fulde PM-resultater præcist. Gentagne fulde kørsler gav identiske prognoser. Den faktisk serverede numeriske audit bekræfter de forseglede filer, unikke identiteter, alle MM/PM-minutforventninger, pointdele, ti markspillerstartere og én keeper/90 minutters keeperdækning inklusive eksplicit umodelleret pool.

En ny, udtrykkeligt syntetisk seks-GW-kørsel på den rigtige private B-worker bestod 23. oktober kl. 10.08 dansk tid. Anfører/viceanfører og holdscore matcher de fælles PM-scenarier. Resultatet blev også kontrolleret i den offentlige transfer-/dashboard-brugerflade på desktop og mobil; valideringsresultatet afvises som et ægte personligt hold, og en lokal visningskopi beholder tallene uændret. Private jobnøgler, testhold og fulde planer er kun i `/tmp`, ikke i dette repository. Ingen officielle FPL-handlinger er udført.

Den offentlige HTTPS-app er testet med normal TLS-verifikation: historikarkiv, sandsynligheder, spillerkort, midtugekontekst, fælles forecast-identitet, snapshot-flow og transferresultat. Snapshot-testen bekræfter, at et senere bekræftet hold kan bruge det seneste forseglede forecast, at tidsstemplet vises, og at nyere skadeinformation advarer uden at slette planen. Deadline spærrer fortsat. Den rigtige remote-plans visning og dashboardets nyheds-/advisory-flow er separate beståede kontroller; samlet ni offentlige browsersuites på desktop og mobil.

Alle **88 faktisk serverede produktionsfiler** matcher det seneste originale produktionsartefakt. Det eksisterende originale workflow opdaterede selv ti datafiler, mens B blev valideret (run `39918011196`, færdigt 07.44 UTC). B-publiceringen bevarede dette nyeste komplette artefakt; den frøs eller ændrede ikke det oprindelige workflows drift. Produktionsmodel, formler og parametre er uændrede. Den isolerede B-refresh bruger nu de nye immutable pins fra main.

## Aktuel parret sammenligning

Kontrollen bruger samme aktuelle kilder og parametre, med og uden den nye markspillerrolle-kobling. Den allerede rettede keeperpolitik bevares i begge arme.

| Penders, første GW | Før rollekobling | Efter |
| --- | ---: | ---: |
| P(start) | 99,7593 % | 99,7593 % |
| MM xM | 89,4700 | 89,4700 |
| PM E[min] | 89,4700 | 89,4700 |
| P(60+) | 99,2808 % | 99,2808 % |
| P(90) | 98,7707 % | 98,7707 % |
| xP, 400 træk | 3,9150 | 3,7375 |

Keeperens analytiske rolle-/minutsandsynligheder er uændrede. De 400 træk er genereret med ændret simulations-/hændelsesrækkefølge. Enkeltspillerens xP-forskel kan ikke adskilles fra denne Monte Carlo-variation og må ikke fortolkes som en dokumenteret forringelse af Penders' keeperrolle eller individuelle kvalitet. Pointgevinsten for hele kandidaten er heller ikke statistisk sikkert etableret. De publicerede nuværende xP-tal er de forseglede PM-scenariers gennemsnit.

Cherkis startchance ændres fra 46,72 % til 47,97 % og xM fra 45,28 til 46,30. Ndiayes startchance ændres fra 87,69 % til 86,69 % og xM fra 79,57 til 79,03. Foden går fra 70,87 % til 71,00 %. Det er generelle rolle-/hierarkieffekter, ikke manuelle boosts. Aktuel xP ændres også af simulationsrækkefølgen; historiske parrede PM-tests er kvalitetsgrundlaget.

De officielle Chelsea-/FPL-kilder blev genhentet 23. oktober kl. 09.42 dansk tid; oprindelige publiceringstidspunkter står særskilt i [kildekvitteringen](../../analysis/results/b-role-history-release-20261023/current-official-goalkeeper-sources.json). Chelseas bekræftede Everton-opstilling/kampreferat er fra 17. oktober. Martínez-skadeopdateringen er fra 18. oktober og træneropdateringen fra 17. oktober. Sharman-Lowe og Slonina er registrerede førsteholdsreserver i de hentede profiler; registrering bliver ikke lig med en stor startprior. Sánchez/Jørgensen fremgår af udlånsgruppen. Der indføres ingen ny returdag, som klubben ikke har bekræftet.
