# Analyseprotokol

## Population og tid

To markedsserier med originale bootstrap-observationer. Den primære prisserie på GW-niveau bruger seneste optagelse 1–24 timer før deadline med samme deadline i selve payloaden. Dagserien bruger én optagelse pr. UTC-dato, primo 2025/26–ultimo 2025/26 og separat kilde/regelregime i 2026/27. Kræv 18–30 timer for dag +1 og 60–84 timer for dag +3. GW +1 og +2 bruger den eksakte nummererede GW i samme sæson. Ingen interpolering eller sæsonovergange. Pris er aktuel købspris i tiendedele af £1m.

Historiske udfald kommer fra afsluttede fixtures og knyttes til tilstanden før deadline med FPL-id og sæson. Et historisk udfald kan indgå i features og træning efter første optagelse med både `finished` og `data_checked` for dets GW. Historiske xP fra Vaastav udelades. Eksponér omtrentlige tidsstempler og manglende labels. Registrer en dokumenteret blank som nul, hvis spilleren var på det registrerede hold og ingen fixture er registreret dér. Manglende øvrige udfald beholdes som manglende.

## Prognoser

Klasserne er fald, uændret og stigning mellem to observerede priser. Sammenlign Laplace-udglattede frekvenser, en diskret flow-baseline, multinomial logistisk regression uden transfers/ejerskab, en simpel flow-logistisk model, en udvidet L2-logistisk model og gradient boosting med fast lav dybde. Evaluer på fælles rækker, med fast valgte hyperparametre og priors. Ekspanderende træning refittes hver syvende dagsoprindelse eller fjerde GW-oprindelse i hver sæson. Ved refit skal snapshot for træningslabel ligge højst ved første testoprindelse. 2022/23 er opvarmning for GW-modeller. Dagmodellerne begynder efter mindst 42 modne træningsdatoer. Rapportér de to dagregimer separat samt samlet. Rapportér Brier, log loss, nøjagtighed, præcision pr. klasse og makro, kalibrering i faste bins og parrede tidsblokintervaller.

## Marked og sportslig værdi

Undersøg tidsforskudte rangkorrelationer, køberkoncentration, halepersistens, asymmetri og prisreversering. Definér store pointudbytter som mindst 10 point og mindst 8 over en kendt fire-GW form. Salgsbølge er bund-5 %-flow blandt spillere med mindst 1 % ownership ved origin. Prisepisode er mindst tre pris-ticks på to GW-intervaller med positivt flow i begge. Sammenlign kohorter med andre spillere i samme GW, position, helbredsgruppe, omtrentlige ownership og forudgående form. Følsomhed og fortolkning er deskriptiv. Aggregerede observationer identificerer ikke kopiering, kausal prisfeedback eller bobler.

Sammenlign parret Ridge med og uden markedsfeatures for minutter og point på samme historiske rækker. Disse referencefeatures er en sportslig proxy. Sammenhold ægte, frosne MM/PM-originalers residualer med uafhængigt tidligere observeret flow. Brug én vintage pr. mål-GW og rapportér små populationer deskriptivt. Hovedspørgsmålet er fortsat åbent, hvis originale matchbare GWs ikke er tilstrækkelige.

Sæsonreplayet sammenligner tre begrænsede politikker. Vælg én fælles starttrup efter referenceprognosen. Kør holdselvstændige, købsmomentsbaserede salgspriser og bank, budget og formation, klubkvoter, højst én gratis transfer pr. GW og ingen chips. Armene bruger pointproxy, udvidet pointproxy, eller pointproxy samt en lille værdi for næste prisbevægelse. Samme udtagelse, kaptajnregel og scout-kandidatregler. Rapportér faktisk score, manglende outcomes og deltas pr. sæson. Replayet er en afgrænset politiktest af historisk markedsinformation og kan ikke måle TS v3's score eller en kausal effekt.
