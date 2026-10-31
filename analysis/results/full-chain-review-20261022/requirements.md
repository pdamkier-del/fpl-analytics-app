# Sporbar kravoversigt

Kilder: de konkrete ønsker i den tilgængelige samtale. Gentagne ønsker samles; citatfragmenter er forkortede. Status er adskilt fra prognosekvalitet. Ingen blanketgodkendelse af uklare referencer eller private data.

| ID | Trin | Ønske / krav | Status | Restbegrænsning |
| --- | --- | --- | --- | --- |
| A01 | Afgrænsning | Eksisterende branch og komponenter genbruges | funktionstestet | Ingen ny parallel modelbranch |
| A02 | Afgrænsning | Identificér alle oprindelige fem forslag | uafklaret_reference | De fem må ikke automatisk erklæres leveret; kendte konkrete ønsker nedenfor kan kontrolleres |
| D01 | Data | Stabile spiller-, klub- og kampidentiteter | funktionstestet | Kildedækning og publikationscertificering er separate krav |
| D02 | Data | Nuværende sæsons tidligere PL-kampe tilgængelige | funktionstestet | Publiceret historik omfatter GW1–7 |
| D03 | Data | Alle relevante ældre sæsoner kan undersøges i appen | delvist | Historiske modelarkiver er ikke det samme som brugeradgang til tidligere sæsoner |
| D04 | Data | CL/Europa/pokalkampe med minutter og statistik | delvist | Verificerede registrerede kampe vises; ingen garanti for komplet kildehistorik |
| D05 | Data | Kamptrupper, skader og udlån adskilles fra registrering | delvist | Officielle data er tidsstemplede captures; alle positioners faktiske hierarki er ikke certificeret |
| D06 | Data | Korrekte as-of-tider uden fremtidig information | delvist | Historiske kickoff+3/4h-proxies og ufuldstændige kildepublikationstider består |
| D07 | Data | Ukendt statistik eller deltagelse bliver ikke automatisk nul | funktionstestet | Ukendt availability er fortsat en begrænsning for probabilistisk kalibrering |
| D08 | Data | Opdateringsknap og brug af seneste verificerede forecast | delvist | Et klik er ikke bevis på øjeblikkelig fuld modelgenberegning; ældre snapshot kan bruges med synligt tidspunkt |
| R01 | Roller/MI | Flere historiske roller pr. spiller | funktionstestet | Historiske rolleandele er ikke kalibrerede kommende positionssandsynligheder |
| R02 | Roller/MI | Alternative kompatible opstillinger påvirker startchancer | mangler | Den viste XI giver ikke feedback til marginalerne |
| R03 | Roller/MI | Match importance kobles til konkrete roller og kampvalg | delvist | Current detailed selector discards importance weights; target-specific joint role/importance mechanism is not validated |
| R04 | Roller/MI | Fremadrettet prioritering mellem PL og kommende Europa-kamp | ikke_valideret | Rest-before-CL was not validated by the observed-European-history experiment |
| R05 | Roller/MI | Skeln probabilistisk mellem rotation, tabt rolle og skade | mangler | Ingen implementeret og valideret latent årsagsmodel; bekræftet fakta må ikke erstattes af gæt |
| R06 | Roller/MI | Taktisk kompatible alternative XI-scenarier | delvist | Ti markspillere i et draw beviser ikke en kompatibel formationsfordeling |
| R07 | Roller/MI | Seneste PL-kamps indflydelse isoleres | undersøgt | Følsomhedstest dokumenterer ikke, om vægten er korrekt; original upstream er holdt fast |
| M01 | MM | Startchancer beregnes og sammenlignes historisk | delvist | Genbrugte forskningsperioder; ikke uafhængig certificering af alle undergrupper |
| M02 | MM | Én keeper og samlet 90 minutters dækning | funktionstestet | Den skjulte pulje skal medregnes ved kontrol af summer |
| M03 | MM | Historisk hierarki dæmper ukendt reservepulje | delvist | Kun to berørte valideringskampe; ingen påvist takeover-xP-forbedring |
| M04 | MM | Penders og officielle konkurrenter indgår med status | delvist | Denne gennemgang kontrollerer det publicerede datagrundlag; er ikke ny selvstændig officiel clearance af hver keeper |
| M05 | MM | Gyldige 0/cameo/start/60+/90-sandsynligheder | delvist | Matematisk gyldighed er ikke fuld undergruppekalibrering; P(60+) blev marginalt dårligere i tidligere duration-test |
| M06 | MM | Skadesretur og tidligere normalrolle håndteres | delvist | Ikke en fuld fremtidig skade-/restitutionstilstandsmodel |
| M07 | MM | Seks-GW-horisont med korrekte nyhedsgrænser | delvist | Fremtidige skader og taktiske hierarkiskift modelleres ikke fuldt ud som scenarier |
| M08 | MM | Validerede usikkerhedsintervaller for minutter | ikke_valideret | Ikke uafhængigt kalibrerede intervaller eller parameterusikkerhed |
| P01 | PM | Samme analytiske minutforventning i MM og PM | funktionstestet | 400-draw sample means may differ; that is not analytic mismatch |
| P02 | PM | Mål/assist-prognoser bruger dokumenterede input og roller | delvist | Datakilder og rollevurdering kan stadig begrænse niveauet; ingen garanti for bedre individuel kalibrering |
| P03 | PM | Individuel afslutningsevne testes generelt | ikke_indført_efter_test | Ingen sikker forbedring; ikke aktiveret, og ikke en glemt implementering |
| P04 | PM | Modtagernes afslutningsevne testes | ikke_indført_efter_test | Chance-share proxies, ikke fuldt observeret creator→receiver-netværk; ingen sikker xP-gevinst |
| P05 | PM | Afslutningsniveau pr. skud og sværhedsgrad undersøges | ikke_indført_efter_test | Ikke stabil PM-forbedring; senere sæsondata delvise |
| P06 | PM | Straffesparkstagerhierarki indgår for aktive spillere | delvist | Occurrence/conversion retained; historical rank source timing partly proxy |
| P07 | PM | Pointdele, bonus, defensive bidrag og debiteringer hænger sammen | funktionstestet | Konsistente pointsummer beviser ikke perfekt hændelsesmodel |
| P08 | PM | Røde kort og selvmål kobles til efterfølgende kampforløb | mangler | Departure timestamp and opponent goal-event linkage incomplete |
| P09 | PM | Alle særlige officielle FPL-assisttyper | delvist | Penalty-winning/rebound/forced-own-goal attribution not fully represented |
| P10 | PM | Sandsynligheder og simulationsusikkerhed skelnes | delvist | 400 draws; no adaptive precision for close TS decisions; outcome quantiles are not model-confidence intervals |
| T01 | TS | Alle visninger og TS bruger samme prognose | funktionstestet | En fælles identitet løser ikke input-/modelbegrænsninger |
| T02 | TS | Lovligt hold, priser, bank, FT, hits og overgang mellem uger | funktionstestet | Synthetic prices equal snapshot prices; actual personal purchase-price input remains separate |
| T03 | TS | Dit faktiske hold og Ødegaard bevares korrekt | kan_ikke_verificeres_privat | Dit aktuelle lokale browserhold er ikke tilgængeligt her; ingen opfundet rettelse af personlige IDs/priser |
| T04 | TS | Autosubs og anfører/vice med samme PM-scenarier | funktionstestet | XI selection and bench ordering are still heuristics, not a joint global optimizer |
| T05 | TS | Fuld seks-GW-beregning på aktuelle publicerede data | funktionstestet | Ikke dit personlige hold; ingen officielle FPL-handlinger |
| T06 | TS | Chipvalg med dokumenteret fremtidig optionsværdi | delvist | TC/full-half calendar incomplete; no certified full-season chip-optimal policy |
| T07 | TS | Transferpolitikkens faktiske sæsonafkast valideres | ikke_valideret | En fungerende plan er ikke dokumentation for bedre sæsonafkast |
| T08 | TS | Busy/timeout/retry uden tab af hold eller dobbelte jobs | funktionstestet | Netværks-/driftstid kan ikke garanteres af tests |
| U01 | App | Samme FPL-app og layout på desktop/mobil | funktionstestet | Browser assertions and screenshots; ingen ny separat erstatningsapp |
| U02 | App | Kompakt sandsynlighedsoversigt og spillerpanel | funktionstestet | Kalibrering og modelusikkerhed er særskilte M05/M08/P10-krav |
| U03 | App | Per-fixture xP/xMin/mål/assists og tidligere stats | funktionstestet | Projected goals/assists er ikke historisk shot xG/xA; nul og manglende data adskilles |
| U04 | App | Spiller- og klubhistorik med navigation til prognoser | funktionstestet | Aktuel sæson; tidligere sæsoners UI-dækning er D03 |
| U05 | App | Kildebelagt fraværsgrund og tydelig modelvurdering | delvist | Model-estimeret rotation er ikke implementeret; ukendt årsag vises som ukendt |
| U06 | App | Holdrelevante nyheder og næste-GW-planstatus | funktionstestet | Scenariet med ny skade er syntetisk i browserflow-testen; faktiske private holddata er ikke læst |
| U07 | App | Effektiv resultatside med centrale tal og spillernes kampe/stats | funktionstestet | Vigtige tal kontrolleres; subjektiv visuel præference kan ikke bevises med tests |
| U08 | App | Seneste plan vises og status er forståelig | funktionstestet | En ny prognose kan gøre en gemt plan forældet; der vises ikke en falsk genberegning |
| U09 | App | Prognose-/pris-/beregningstid vises korrekt | funktionstestet | Nyere nyheder vises som advisory og ændrer ikke automatisk eksisterende xP-tal |
| O01 | Drift | Ingen model-/produktionsændringer under audit | funktionstestet | 88 aktuelle produktionsfiler matcher publiceringskvitteringen; eksterne planlagte dataopdateringer er ikke auditens ændringer |
| O02 | Drift | Eksisterende offentlige B-preview fungerer | funktionstestet | Denne audit kræver ingen ny numerisk udgivelse; hidtidig preview testes live |
| O03 | Drift | Ingen mutation af privat state eller officielle FPL-handlinger | funktionstestet | Ingen adgang til dit virkelige browserlager; dette garanterer ikke, at dets indhold allerede er korrekt |
| O04 | Drift | Sporbar kravliste og testbeviser | funktionstestet | Uklar reference A02 og manglende bevis må ikke blive til grøn status |

Implementation, request fragments and per-row evidence references are retained without truncation in `requirements.json` and `requirements.csv`.
