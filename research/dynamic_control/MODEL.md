# FPL som sekventielt beslutningsproblem

Ved deadline i GW (t) er den observerede tilstand
(s_t=(Q_t,B_t,C_t,F_t,H_t,P_t,Z_t,K_t,b_t)).

| Led | Betydning |
| --- | --- |
| (Q_t,B_t,C_t) | De 15 ejede spillere, bank i £0,1m og individuel købspris |
| (F_t,H_t) | Gratis transfers og resterende chips med gyldighedsvindue |
| (P_t) | Aktuel pris, klub og position for hver spiller |
| (Z_t,K_t) | Skader, karantæner, registrering og den kendte kampkalender inklusive blanke og dobbelte runder |
| (b_t) | Fælles prædiktiv fordeling for point, minutter, tilgængelighed, priser og ændringer til kampkalenderen givet det, der er kendt ved deadline |

Skadesgrad, rolle og managerens udtagelsesplan kan være latente. Med en belief state (b_t) opdateret ved nye observationer fås et fuldt observeret beslutningsproblem på beliefs. Et praktisk alternativ er en approksimeret Markov-tilstand med fastfrosset deadlineprognose og scenarier for revisioner. Marginale sandsynligheder for minutter og point er utilstrækkelige, hvis fælles DNP, kaptajnens vice og bænken skal prises korrekt.

Handlingen (a_t=(O_t,I_t,L_t,h_t)) sælger og køber et lovligt sæt spillere eller ruller med tomme sæt. (L_t) angiver formation, XI, bænkrækkefølge, kaptajn og vice. (h_t) er inaktiv i første eksperiment. Uden chips har truppen 2 mål­mænd, 5 forsvarere, 5 midtbanespillere og 3 angribere, højst tre fra en klub og en gyldig startformation. Det femtransfersloft, der anvendes i replayet, kommer fra den frosne TS-søgning. Det er en afgrænsning af handlingsrummet.

Salgsprisen i heltal er (d(p,c)=p) for (ple c), ellers (c+lfloor(p-c)/2floor). Nye spillere får købsprisen (P_t(i)). Bank efter handlingen er (B_t+sum_{oin O_t}d(P_t(o),C_t(o))-sum_{iin I_t}P_t(i)) og skal være ikke-negativ. Uden chips og med (n=|I_t|) er hits (4(n-F_t)^+) og næste saldo (min(5,(F_t-n)^++1)). Forberedelse af starttruppen i GW1 efterlader nul gratis transfers til yderligere ændringer på samme deadline i replayet. En gammel købspris kan gøre et senere tilbagekøb ufinansierbart. En funding-handel kan omvendt muliggøre et senere køb ved at frigøre bank eller en klubplads.

Med udfald (Y_t) er belønningen

[
R_t(s,a,Y_t) = operatorname{FPLPoints}(L_t,Y_t,h_t) - 4(n-F_t)^+ .
]

Pointleddet omfatter lovlige autosubs og kaptajnens eller vicens bonus. Særskilte chipforsøg kræver deres egne transitionsregler. Free Hit har en midlertidig trup og et separat budget, Wildcard ændrer den permanente trup, Bench Boost ændrer, hvem der scorer, og Triple Captain ændrer kaptajnens bonus. Bellman-ligningen under en risikoneutral sæsonmålsætning er

[
V_t(s)=max_{ainmathcal A_t(s)}
  mathbb E!left[R_t(s,a,Y_t)+V_{t+1}(S_{t+1})mid s,aight],
qquad V_{39}=0 .
]

For alle metoder indgår samme oplysninger ved samme deadline. Senere runder må reagere på ny information gennem (S_{t+1}). En transfer i første runde skal vælges før forgrening. Det maksimale forventede pointtal beregnet med ekstra information før første valg er en informationsgrænse, som en mulig beslutningsregel ikke bør vurderes imod uden særskilt mærkning.

Bank og gratis transfers har ingen særskilt belønning. Deres marginaler er (Delta_F V_t(s)=V_t(s+1_{m FT})-V_t(s)) under loftet og (Delta_B V_t(s)=V_t(s+£0{,}1m)-V_t(s)). En praktisk pris på fleksibilitet er forskellen mellem fortsættelse med mulighed for at vælge forskellige handlinger efter et observeret chok og en fortsættelse med ét bindende valg før chokket. Ejerhistorik, klubplads, budgettærskler og tid til næste deadline ændrer disse forskelle.
