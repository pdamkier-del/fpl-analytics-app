/* Model Explorer: checked against locked model source, 2026-10-09. */
window.FPL_MODEL_TREE = {
  "version": "2026-10-09",
  "repository": "pdamkier-del/fpl-analytics-app",
  "checkpoint": "fpl-model-complete-locked-20261009",
  "nodes": [
    {
      "id": "root",
      "parent": null,
      "title": "Den samlede FPL-model",
      "summary": "Fra kampinformation og minutter til point, transfers og chips.",
      "idea": "Modellen er en sammenhængende beslutningskæde: Først anslår vi spilletid (MM). Derefter simulerer vi FPL-point (PM). Transferstrategien (TS) vælger en lovlig trup over seks GW, og til sidst afgør chiplaget, om en chip skal bruges. Klik dig ned i hver gren for at se den faktiske matematik.",
      "formulas": [
        {
          "expression": "MM → PM/vFinal → TS v3 → FH / WC / BB / TC",
          "meaning": "De fire chips konkurrerer om den samme deadline. Kun én vælges ad gangen."
        },
        {
          "expression": "argmax₍lovlige handlinger₎  E[point] − omkostninger",
          "meaning": "Den gennemgående idé er at maksimere forventet værdi, ikke efterrationalisere faktiske point."
        }
      ],
      "details": [
        "GW1–5 bruger cold-start i den historiske model; fra GW6 bruges låst MM og PM/vFinal.",
        "Parametrene blev låst 9. oktober 2026. Det historiske samlede replay gav 2.266 point i 2025/26 – ikke en garanti for fremtidige point.",
        "Du kan åbne hvert underniveau eller bruge søgefeltet til at finde en ligning."
      ],
      "sources": [
        "analysis/FINAL_FPL_MODEL_MANIFEST_20261009.md",
        "config/fpl_locked_model.json"
      ],
      "type": "overview"
    },
    {
      "id": "mm",
      "parent": "root",
      "title": "MM · Minutmodellen",
      "summary": "Hvem starter, i hvilken rolle, og hvor længe?",
      "idea": "Spillertid er den vigtigste eksponering for alle efterfølgende pointkanaler. MM kombinerer kampværdien, spillerens positioner, hierarki, konkurrencen om elleve pladser og nylige officielle kampe.",
      "formulas": [
        {
          "expression": "xMinsᵢ = P(startᵢ)·μstartᵢ + [1 − P(startᵢ)]·P(indskiftningᵢ | ikke start)·μsubᵢ",
          "meaning": "Forventet antal minutter, opdelt efter start og indskiftning."
        }
      ],
      "details": [
        "Kampens sandsynlige XI er en sammenhængende formation; sandsynlighederne for de enkelte spillere er stadig kontinuerte.",
        "Officielle PL-, europæiske og cupkampe bruges i spillerhistorikken; nyere information vejer tungere."
      ],
      "sources": [
        "src/fpl_v1_1_model/minutes_decomposition.py"
      ],
      "type": "theory"
    },
    {
      "id": "mm-mi",
      "parent": "mm",
      "title": "Match Importance",
      "summary": "Hvorfor betyder nogle kampe mere for rotation?",
      "idea": "Kampværdi styrker især betydningen af førstevalgs-hierarkiet. Den lægges ikke blot som det samme startbonusbeløb på alle spillere.",
      "formulas": [
        {
          "expression": "MI = f(V₍turnering₎, S₍runde₎, O₍modstander₎)",
          "meaning": "Tre kilder til kontekst: turnering, runde og modstanderstyrke."
        },
        {
          "expression": "Feature₍i,r₎ = H₍i,r₎ · MI-komponent",
          "meaning": "Værdien interagerer med spillerens rollehierarki og påvirker derfor spillere forskelligt."
        }
      ],
      "details": [
        "Fatigue/workload er en separat minutmodelblok; det er ikke et fjerde led i Match Importance.",
        "Kampens eksakte sammenvejning er modelbaseret. Disse komponenter er dokumenterede inputs, ikke en universel MI-sum."
      ],
      "sources": [
        "src/fpl_v1_1_model/match_importance.py"
      ],
      "type": "theory"
    },
    {
      "id": "mm-mi-comp",
      "parent": "mm-mi",
      "title": "Dynamisk turneringsværdi",
      "summary": "Værdien af aktive turneringer ændrer sig gennem året.",
      "idea": "Hvis klubben ryger ud af andre turneringer, kan de tilbageværende kampe få højere relativ betydning.",
      "formulas": [
        {
          "expression": "V(c,A) = b(c) · [ Σₖ b(k) / Σₖ∈A b(k) ]^0,35",
          "meaning": "b(c) er grundværdien af turnering c; A er de aktuelt aktive turneringer."
        },
        {
          "expression": "b(PL)=1,00 · b(CL)=0,95 · b(EL)=0,70 · b(FA)=0,55",
          "meaning": "Eksempler på låste basisværdier; Conference League er 0,50 og EFL Cup 0,35."
        }
      ],
      "details": [
        "Det er en ikke-lineær opjustering, ikke en fast bonus pr. aktiv turnering.",
        "Brug kun konkurrencer, der var kendt aktive før kampens deadline."
      ],
      "sources": [
        "src/fpl_v1_1_model/match_importance.py"
      ],
      "type": "theory"
    },
    {
      "id": "mm-mi-stage",
      "parent": "mm-mi",
      "title": "Runde og turneringsfase",
      "summary": "En finale er ikke det samme som en gruppespilskamp.",
      "idea": "Ligaen får en gradvist voksende faseværdi; cupturneringerne bruger information om den konkrete runde.",
      "formulas": [
        {
          "expression": "S_PL(g) = 0,20 + 0,80 · [(g−1)/37]^1,5",
          "meaning": "g er GW 1–38; ligafasen bliver stærkere sent i sæsonen."
        },
        {
          "expression": "S_finale=1,00 · S_semifinale=0,88 · S_kvartfinale=0,76",
          "meaning": "Eksempler fra cup-stage-tabellen."
        }
      ],
      "details": [
        "Ved manglende konkret cup-runde findes konservative sæsonmåned-fallbacks.",
        "Disse værdier er kun én del af startmodellen."
      ],
      "sources": [
        "src/fpl_v1_1_model/match_importance.py"
      ],
      "type": "theory"
    },
    {
      "id": "mm-mi-opp",
      "parent": "mm-mi",
      "title": "Modstanderens styrke",
      "summary": "Modstanderkvalitet som skaleret signal.",
      "idea": "Stærke modstandere øger kampens betydning for at stille i den foretrukne formation.",
      "formulas": [
        {
          "expression": "O(Elo) = 1 / [1 + exp(−(Elo−1800)/180)]",
          "meaning": "Logistisk skala omkring Elo=1800; ukendt Elo giver neutralt 0,5."
        },
        {
          "expression": "MI_H = {H_fast·V, H_fast·S, H_fast·O, H_slow·V, H_slow·S, H_slow·O}",
          "meaning": "Hierarki-interaktionerne er faktiske features til startmodellen."
        }
      ],
      "details": [
        "Det er ikke det samme som modstanderens xG. Det er en rotationsfeature."
      ],
      "sources": [
        "src/fpl_v1_1_model/match_importance.py"
      ],
      "type": "theory"
    },
    {
      "id": "mm-roles",
      "parent": "mm",
      "title": "Rollefordeling q",
      "summary": "En spiller kan være relevant til flere forskellige positioner.",
      "idea": "I stedet for kun DEF/MID/FWD registrerer vi taktikroller fra de foregående starter. En spiller kan konkurrere om eksempelvis både venstre og højre wing.",
      "formulas": [
        {
          "expression": "qᵢ,r = (Mᵢ,r + 0,05) / Σₛ∈Rᵢ (Mᵢ,s + 0,05)",
          "meaning": "Mᵢ,r er recencyvægtet start-minutmasse i rolle r."
        },
        {
          "expression": "Σᵣ qᵢ,r = 1",
          "meaning": "Rollefordelingen normaliseres over tilladte roller."
        }
      ],
      "details": [
        "Kun afsluttede kampe før cutoff indgår.",
        "Ukendte indskifterroller må ikke bruges som startrolle-bevis.",
        "En lille pseudotælling 0,05 undgår nul for observeret tilladte roller."
      ],
      "sources": [
        "src/fpl_v1_1_model/role_history.py"
      ],
      "type": "theory"
    },
    {
      "id": "mm-recency",
      "parent": "mm-roles",
      "title": "Recency-vægte",
      "summary": "Nyere starter påvirker rollefordelingen mere.",
      "idea": "Historikken er ikke et simpelt sæsongennemsnit. En nylig start kan være mere informativ end en kamp for flere måneder siden.",
      "formulas": [
        {
          "expression": "wₗ = 2^(−l / h)",
          "meaning": "l er antal kampe tilbage i historikken; h er half-life, som i rollehistorikkoden har standarden 10."
        },
        {
          "expression": "Mᵢ,r = Σₖ wₖ · mᵢ,r,k / 90",
          "meaning": "Minutmasse kan desuden justeres efter kampens betydning."
        }
      ],
      "details": [
        "Half-life betyder, at bidraget fra en kamp h pladser tilbage er halveret.",
        "Formlen er den dokumenterede rollehistorik; øvrige blokke har egne historikregler."
      ],
      "sources": [
        "src/fpl_v1_1_model/role_history.py"
      ],
      "type": "theory"
    },
    {
      "id": "mm-hierarchy",
      "parent": "mm",
      "title": "Rollehierarki H",
      "summary": "Hvem er førstevalg til hver konkret rolle?",
      "idea": "Spillerne konkurrerer direkte mod hinanden om samme pladser. Det er forskelligt fra blot at rangordne alle forsvarsspillere samlet.",
      "formulas": [
        {
          "expression": "Hᵢ,r = min(0,995, Cᵣ · [Sᵢ,r + 0,1] / [Σⱼ Sⱼ,r + 0,1·max(1,nᵣ)])",
          "meaning": "Sᵢ,r = recencyvægtede starter i rolle r; Cᵣ = estimeret antal pladser for rollen."
        },
        {
          "expression": "Sᵢ,r = 0  ⇒  Hᵢ,r = 0",
          "meaning": "I den dokumenterede implementering gives nulhierarki ved ingen historiske starter i rollen."
        }
      ],
      "details": [
        "H er ikke alene P(start). Den bruges med q, andre features og formationen.",
        "Kampværdi påvirker hierarkiets rolle i startmodellen gennem interaktioner."
      ],
      "sources": [
        "src/fpl_v1_1_model/role_history.py"
      ],
      "type": "theory"
    },
    {
      "id": "mm-xi",
      "parent": "mm",
      "title": "Global XI og formation",
      "summary": "Elleve forskellige spillere – aldrig samme spiller på to roller.",
      "idea": "Hver tilladt formation opdeles i 11 roller/pladser. Algoritmen maksimerer en samlet assignment-score under reglerne, ikke 11 uafhængige topvalg.",
      "formulas": [
        {
          "expression": "max ΣᵢΣᵣ xᵢ,r · sᵢ,r + log P(formation)",
          "meaning": "xᵢ,r=1 hvis spiller i vælges til rolle r."
        },
        {
          "expression": "sᵢ,r = a·ln(qᵢ,r) + b·ln(Hᵢ,r) + c·ln(Pstartᵢ) + d·ln(formᵢ) + adjᵢ,r",
          "meaning": "Rolle-score bruger log-evidens og en eventuel rollejustering; standardvægten for performance kan være 0."
        },
        {
          "expression": "Σᵢ xᵢ,r = 1 ;  Σᵣ xᵢ,r ≤ 1",
          "meaning": "Hver plads besættes én gang; en spiller kan højst bruges én gang."
        }
      ],
      "details": [
        "Implementeret med lineær assignment-optimering og gennemgang af mulige formationer.",
        "Dette er den mest sandsynlige sammenhængende XI-forklaring; P(start) forbliver probabilistisk."
      ],
      "sources": [
        "src/fpl_v1_1_model/xi_assignment.py"
      ],
      "type": "theory"
    },
    {
      "id": "mm-start",
      "parent": "mm",
      "title": "P(start)",
      "summary": "Sandsynligheden for at starte næste kamp.",
      "idea": "Minutmodellens features omfatter nylige starter, rollefit og -hierarki, kampbetydning, performance-/workload-signaler og tilgængelighed.",
      "formulas": [
        {
          "expression": "pᵢ = P(startᵢ = 1 | information før deadline)",
          "meaning": "Den relevante betingede sandsynlighed er ex ante."
        },
        {
          "expression": "P(spil) ≈ pᵢ + (1 − pᵢ)·P(sub | ikke start)",
          "meaning": "Sandsynlighed for at få mindst ét minut; approximationen afhænger af modellens definitioner."
        }
      ],
      "details": [
        "En sandsynlighed på 0,75 betyder ikke, at spilleren får præcis 75 % af 90 minutter.",
        "P(start), forventet startvarighed og cameo-varighed håndteres separat."
      ],
      "sources": [
        "src/fpl_v1_1_model/minutes_decomposition.py",
        "src/fpl_v1_1_model/pstart_v2.py"
      ],
      "type": "theory"
    },
    {
      "id": "mm-duration",
      "parent": "mm",
      "title": "Startminutter og cameo",
      "summary": "Spilletiden afhænger af, om spilleren starter eller bliver skiftet ind.",
      "idea": "Modellen har betingede fordelinger og forventninger for start- og indskifterscenarier.",
      "formulas": [
        {
          "expression": "μstartᵢ = E[minutterᵢ | starter]",
          "meaning": "Startvarighed estimeres separat."
        },
        {
          "expression": "μsubᵢ = E[minutterᵢ | indskiftet og ikke startet]",
          "meaning": "Indskiftervarighed er et andet estimat."
        },
        {
          "expression": "xMins = pstart·μstart + (1−pstart)·psub·μsub",
          "meaning": "Loven om total forventning anvendt på de tre spille-scenarier."
        }
      ],
      "details": [
        "Det dokumenterede betingede-minut-forsøg bruger Ridge for varigheder og logistisk regression for indskiftersandsynlighed; dette er ikke en påstand om, at hver produktionskomponent har samme estimator."
      ],
      "sources": [
        "src/fpl_v1_1_model/minutes_decomposition.py"
      ],
      "type": "theory"
    },
    {
      "id": "mm-work",
      "parent": "mm",
      "title": "Workload og tilgængelighed",
      "summary": "Sene opgør og mange minutter kan øge rotationsrisiko.",
      "idea": "Historiske officielle klubkampe giver blandt andet nylige minutter, starter, hviletid og kortsigtet belastning, mens kendt skade-/karantæneinformation påvirker tilgængelighed.",
      "formulas": [
        {
          "expression": "Workloadᵢ(t) = Σₖ w(t−tₖ)·minutterᵢ,k",
          "meaning": "Skematisk eksponeringsmål: nyere kampe kan tælle mere."
        },
        {
          "expression": "P(startᵢ) = f(roleᵢ, Hᵢ, MI, nylige starter, workload, tilgængelighed, …)",
          "meaning": "f er den indlærte minutmodel – ikke en simpel kendt lineær sum."
        }
      ],
      "details": [
        "Denne formel viser idéen; den er ikke en eksakt publiceret produktionskoefficientvektor.",
        "Historiske afsluttede kampe efter cutoff må aldrig bruges som input."
      ],
      "sources": [
        "src/fpl_v1_1_model/workload.py",
        "src/fpl_v1_1_model/availability_projection.py"
      ],
      "type": "concept"
    },
    {
      "id": "pm",
      "parent": "root",
      "title": "PM · Pointmodellen",
      "summary": "Fra minutter og kampscenarier til forventede FPL-point.",
      "idea": "Den låste PM/vFinal bygger en sandsynlighedsfordeling for hændelser og regner det gennemsnitlige FPL-udbytte for hver spiller i en given fixture.",
      "formulas": [
        {
          "expression": "xPᵢ,g = E[FPᵢ,g | information ved deadline]",
          "meaning": "FPL-point er stokastiske; xP er middelværdien."
        },
        {
          "expression": "xPᵢ,g = Σ_fixtures E[FPᵢ,fixture]",
          "meaning": "En Double Gameweek består af flere kampbidrag."
        }
      ],
      "details": [
        "Fysiske scoringer er ikke sikre, selv når xP er høj.",
        "Modellen håndterer også defensive bidrag, bonus og negative hændelser."
      ],
      "sources": [
        "src/fpl_v1_1_model/joint_simulator.py",
        "src/fpl_xpts/vfinal_forecast.py"
      ],
      "type": "theory"
    },
    {
      "id": "pm-exposure",
      "parent": "pm",
      "title": "Eksponering og spilletid",
      "summary": "En spiller kan ikke score mål eller clean sheet uden at komme på banen.",
      "idea": "MM leverer start-/indskiftersandsynligheder og minutter, som bruges ved simulation af hver fixture.",
      "formulas": [
        {
          "expression": "μ₍hændelser₎,i ≈ rateᵢ,90 · E[minutterᵢ]/90",
          "meaning": "Intuitiv eksponeringsskalering for eksempelvis angrebshændelser."
        },
        {
          "expression": "E[appearance points] = E[f(minutter)]",
          "meaning": "FPL har diskrete minutteregler; forventningen skal følge minutterfordelingen, ikke kun gennemsnittet."
        }
      ],
      "details": [
        "En spiller med 60 forventede minutter får ikke automatisk præcis de samme point som én, der altid får 60 minutter."
      ],
      "sources": [
        "src/fpl_v1_1_model/joint_simulator.py"
      ],
      "type": "theory"
    },
    {
      "id": "pm-attack",
      "parent": "pm",
      "title": "Angreb: mål, assists og straffe",
      "summary": "FPL-point fra scoringer er tilfældige hændelser.",
      "idea": "Modellen kombinerer spillerens målandele med forventede holdmål og sandsynligheden for spilletid. Straffe modelleres som en separat fælles hændelsesproces.",
      "formulas": [
        {
          "expression": "G₍åbent spil₎,hold ~ Poisson(max(0, λmål − λstraffe·p₍scoret straffe₎))",
          "meaning": "Forventede scorede straffe trækkes ud af den almindelige målproces for at undgå dobbelttælling."
        },
        {
          "expression": "N₍straffe₎ ~ Poisson(λstraffe)",
          "meaning": "Straffehændelser trækkes separat, og en skytte vælges blandt spillere på banen."
        },
        {
          "expression": "E[goal pointsᵢ] = goal_weight(positionᵢ) · E[goalsᵢ]",
          "meaning": "Positionen bestemmer FPL-point pr. mål."
        }
      ],
      "details": [
        "Mål scorer ikke uafhængigt af hele holdets forventede antal mål.",
        "En assistsandsynlighed knyttes til hændelsesprocessen; xA er derfor ikke blot en kopi af et råt sæsongennemsnit."
      ],
      "sources": [
        "src/fpl_v1_1_model/joint_simulator.py"
      ],
      "type": "theory"
    },
    {
      "id": "pm-defense",
      "parent": "pm",
      "title": "Clean sheets og indkasserede mål",
      "summary": "Defensive forventninger afhænger af kampens udfald og spillerens minutter.",
      "idea": "Holdets mål imod og spillerens deltagelsesvindue afgør forventede defensive point.",
      "formulas": [
        {
          "expression": "P(CS) = P(ingen indkasserede mål i relevant scoringstilstand)",
          "meaning": "FPL clean-sheet-point afhænger også af position og minutgrænse."
        },
        {
          "expression": "E[CS-point] = CS_værdi(position) · P(CS-krav opfyldt)",
          "meaning": "Ikke blot P(holdets slutresultat = 0 mål imod)."
        }
      ],
      "details": [
        "Mål imod-deduktion er separat og positionsafhængig.",
        "I simulationsmodellen giver tidsintervallet på banen et mere retvisende billede end kun sæsongennemsnit."
      ],
      "sources": [
        "src/fpl_v1_1_model/joint_simulator.py"
      ],
      "type": "theory"
    },
    {
      "id": "pm-saves",
      "parent": "pm",
      "title": "Målmandsredninger",
      "summary": "Redninger kommer i grupper med FPL-pointgrænser.",
      "idea": "Modellen simulerer antal redninger og anvender en kalibrering af sandsynlighedsmassen i FPL-redningsintervaller.",
      "formulas": [
        {
          "expression": "N₍saves₎ ~ Poisson(λ₍saves₎) · kalibrering",
          "meaning": "Poisson-fordelingen rettes efter buckets 0–2, 3–5, 6–8, 9–11 og 12+."
        },
        {
          "expression": "E[save points] = E[⌊N₍saves₎ / 3⌋]",
          "meaning": "Der gives point for hver gruppe af tre redninger."
        }
      ],
      "details": [
        "Den sidste formel gælder for den almindelige redningspointkanal, uden andre målmandshændelser.",
        "Kalibreringen ændrer sandsynligheder, ikke de officielle FPL-regler."
      ],
      "sources": [
        "src/fpl_v1_1_model/joint_simulator.py"
      ],
      "type": "theory"
    },
    {
      "id": "pm-defcon",
      "parent": "pm",
      "title": "Defensive contributions (DefCon)",
      "summary": "Defensive handlinger kan give ekstra point.",
      "idea": "Modellen anslår tacklinger, blokeringer, clearinger og øvrige relevante defensive actions efter de gældende FPL-tærskler.",
      "formulas": [
        {
          "expression": "P(DefCon-bonus) = P(Dᵢ ≥ tærskel(positionᵢ))",
          "meaning": "Dᵢ er den relevante sum af defensive bidrag i GW'ens kampe."
        },
        {
          "expression": "E[DefCon-point] = bonusværdi · P(Dᵢ når tærsklen)",
          "meaning": "Sandsynlighedsberegningen tager højde for diskrete tærskler."
        }
      ],
      "details": [
        "Tærsklen varierer efter FPL-position og den pågældende sæsons regler.",
        "Den præcise eventrate er indlært og afhænger af rolle og kampkontekst."
      ],
      "sources": [
        "src/fpl_v1_1_model/defcon.py",
        "src/fpl_v1_1_model/joint_simulator.py"
      ],
      "type": "theory"
    },
    {
      "id": "pm-bonus",
      "parent": "pm",
      "title": "Bonus og BPS",
      "summary": "En god præstation giver ikke automatisk 3 bonuspoint.",
      "idea": "BPS beregnes ud fra kampens hændelser for alle relevante spillere, hvorefter de bedste scorer bonus efter FPL-regler og ligestillinger.",
      "formulas": [
        {
          "expression": "BPSᵢ = Σₑ vægtₑ · eventantalᵢ,e",
          "meaning": "Hændelser påvirker den bagvedliggende bonuspointscore."
        },
        {
          "expression": "E[bonusᵢ] = Σ_{b∈{0,1,2,3}} b · P(bonusᵢ=b)",
          "meaning": "Den korrekte størrelse er forventet bonus, ikke et fast tillæg."
        },
        {
          "expression": "bonusᵢ = rank-regel(BPS for kampens spillere)",
          "meaning": "Bonus tildeles i en fælles kampkontekst."
        }
      ],
      "details": [
        "Tilpasninger af baggrunds-BPS estimeres særskilt.",
        "Eksakt tie-break og sæsonspecifik bonusmatematik følger regelsættet i simulationskoden."
      ],
      "sources": [
        "src/fpl_v1_1_model/bps.py",
        "src/fpl_v1_1_model/joint_simulator.py"
      ],
      "type": "theory"
    },
    {
      "id": "pm-negative",
      "parent": "pm",
      "title": "Kort, selvmål og andre fradrag",
      "summary": "Også de dårlige udfald skal være med.",
      "idea": "Gule/røde kort, selvmål, straffesparksmissere og indkasserede mål kan trække FPL-point ned.",
      "formulas": [
        {
          "expression": "E[netto negative point] = −Σₑ cₑ · E[antalₑ]",
          "meaning": "cₑ er FPL-fradraget for negativ hændelse e."
        },
        {
          "expression": "xP = positive kanaler − forventede fradrag",
          "meaning": "Pointfordelingen har både positive og negative udfald."
        }
      ],
      "details": [
        "En simulation scorer først de faktiske hændelser efter FPL-regler og tager derefter gennemsnittet.",
        "Det er mere troværdigt ved tærskler og afhængigheder end ren rateaddition."
      ],
      "sources": [
        "src/fpl_v1_1_model/negative_events.py",
        "src/fpl_v1_1_model/joint_simulator.py"
      ],
      "type": "theory"
    },
    {
      "id": "pm-mc",
      "parent": "pm",
      "title": "Joint Monte Carlo",
      "summary": "Mange mulige kampe danner en pointfordeling.",
      "idea": "Mål, minutter, hændelser og bonus simuleres sammen i hver tænkelig kamp. Nogle hændelser er korrelerede gennem fælles teammål.",
      "formulas": [
        {
          "expression": "xPᵢ ≈ (1/N) Σₛ₌₁ᴺ FPᵢ⁽ˢ⁾",
          "meaning": "Monte Carlo-estimat: gennemsnit over N simuleringer."
        },
        {
          "expression": "Var(FPᵢ) ≈ [1/(N−1)] Σₛ (FPᵢ⁽ˢ⁾ − xPᵢ)²",
          "meaning": "Spredningen gør, at to spillere med samme xP kan have forskellig usikkerhed."
        },
        {
          "expression": "P(FPᵢ ≥ 10) ≈ antal(simulerede point ≥ 10) / N",
          "meaning": "Eksempel på en tail-sandsynlighed, som kan bruges til at forklare upside."
        }
      ],
      "details": [
        "Målsimulationen tager højde for, at spillere på samme hold deler de samme holdmål.",
        "Forecasten ved hver deadline må kun bygge på datakilder kendt dér."
      ],
      "sources": [
        "src/fpl_v1_1_model/joint_simulator.py"
      ],
      "type": "theory"
    },
    {
      "id": "pm-total",
      "parent": "pm",
      "title": "xP-sammensætning",
      "summary": "Ét tal med en forklarlig fordeling af pointkilder.",
      "idea": "Samlet forventet FPL-point kan fortolkes som summen af forventninger for de enkelte scoringkanaler, også når hændelserne er korrelerede.",
      "formulas": [
        {
          "expression": "xP = EV₍minutter₎ + EV₍mål₎ + EV₍assists₎ + EV₍CS₎ + EV₍saves₎ + EV₍DefCon₎ + EV₍bonus₎ − EV₍fradrag₎",
          "meaning": "Lineæritet af forventning tillader en forklarende dekomposition."
        },
        {
          "expression": "xP₍GW₎ = Σ₍kampe i GW₎ xP₍kamp₎",
          "meaning": "Også ved DGW; nul kampe giver nul kamp-xP."
        }
      ],
      "details": [
        "De præcise kanaltal afhænger af simulations- og prognoseversionen.",
        "PM/vFinal producerer det xpts_mean, TS senere bruger."
      ],
      "sources": [
        "src/fpl_xpts/vfinal_forecast.py",
        "src/fpl_v1_1_model/joint_simulator.py"
      ],
      "type": "theory"
    },
    {
      "id": "ts",
      "parent": "root",
      "title": "TS · Transferstrategien",
      "summary": "Den bedste lovlige beslutning over seks Gameweeks.",
      "idea": "TS har en tilstand (trup, bank, FT, købsværdier). Den udforsker alternative transferstier, scorer hver fremtidig GW og udfører kun den første handling.",
      "formulas": [
        {
          "expression": "J(π) = Σₖ₌₀⁵ wₖ · xP₍XI+kaptajn₎(π,k) − Σₖ (4 + 1)·paid_transfers(π,k)",
          "meaning": "Den låste 6GW-objective med risk buffer 1 pr. betalt transfer."
        },
        {
          "expression": "w = (1; 0,60; 0,36; 0,216; 0,1296; 0,07776)",
          "meaning": "Diskontering af forventede fremtidige point."
        }
      ],
      "details": [
        "Den matematiske model er receding horizon: handlingen for GW g gentænkes ved næste deadline.",
        "Chips lægges ovenpå TS og ændrer ikke selve TS-parametrene."
      ],
      "sources": [
        "src/fpl_xpts/transfer_planner.py",
        "scripts/run_ts_v3_final_chain_gw6.py"
      ],
      "type": "theory"
    },
    {
      "id": "ts-state",
      "parent": "ts",
      "title": "Tilstand og regler",
      "summary": "Truppen er ikke bare en liste spillernavne.",
      "idea": "En strategi skal holde styr på både købsværdier, nutidige salgspriser, bank, antal gratis transfers og chiprettigheder.",
      "formulas": [
        {
          "expression": "s_g = (Squad₍15₎, Bank, FT, purchase_prices)",
          "meaning": "Individuelle købsværdier er nødvendige for den korrekte salgspris."
        },
        {
          "expression": "s₍g+1₎ = T(s_g, handling_g)",
          "meaning": "T er den lovlige FPL-tilstandsovergang."
        },
        {
          "expression": "|Squad|=15 ; FT ≤ 5 ; højst 3 spillere pr. klub",
          "meaning": "FPLs centrale trupbegrænsninger."
        }
      ],
      "details": [
        "Den historiske TS fryser priser i sine hypotetiske fremtidige stier ved dagens pris-snapshot for at undgå informationslækage.",
        "Fri transfers har ingen vilkårlig fast værdi; deres værdi opstår, når man kan bruge dem senere."
      ],
      "sources": [
        "src/fpl_xpts/transfer_planner.py",
        "src/fpl_xpts/season_replay.py"
      ],
      "type": "theory"
    },
    {
      "id": "ts-weights",
      "parent": "ts",
      "title": "6GW-vægte og objektiv",
      "summary": "Næste GW vejer mest, men fremtidig fixtureplan tæller med.",
      "idea": "Vi sammenligner hold over seks GW med eksponentielt faldende vigtighed. Et dårligt enkeltopgør kan derfor være acceptabelt, hvis spilleren er god de følgende uger.",
      "formulas": [
        {
          "expression": "wₖ = ρᵏ ; ρ = 0,60 ; k = 0,…,5",
          "meaning": "Vægtene er låst."
        },
        {
          "expression": "J = Σₖ wₖ·xP₍manager,k₎ − Σₖ hitsₖ − Σₖ bufferₖ",
          "meaning": "I standard TS v3 diskonteres pointprognoser; hits og buffer trækkes ud uden tidsvægt."
        },
        {
          "expression": "w₀=1; w₁=0,60; w₅=0,07776",
          "meaning": "Direkte og fjern fremtid behandles forskelligt."
        }
      ],
      "details": [
        "Det er ikke den samme diskontering som TC's fremtids-usikkerhed.",
        "Horisonten forkortes naturligt ved sæsonslutning."
      ],
      "sources": [
        "src/fpl_xpts/transfer_planner.py",
        "scripts/run_ts_v3_final_chain_gw6.py"
      ],
      "type": "theory"
    },
    {
      "id": "ts-hits",
      "parent": "ts",
      "title": "Transferhits og buffer",
      "summary": "Et ekstra køb skal opveje mere end bare fire point.",
      "idea": "FPL trækker 4 faktiske point pr. betalt transfer. I beslutningen lægger TS et ekstra usikkerhedsfradrag på 1 xP – kun hvis transferen koster et hit.",
      "formulas": [
        {
          "expression": "n₍paid₎ = max(0, transfers − FT)",
          "meaning": "Antal transfers ud over de gratis."
        },
        {
          "expression": "officielle_hits = 4 · n₍paid₎",
          "meaning": "Faktisk FPL-straf."
        },
        {
          "expression": "decision_buffer = 1,0 · n₍paid₎",
          "meaning": "Beslutningsfradrag for usikkerhed, IKKE trukket fra faktiske point."
        },
        {
          "expression": "beslutningsomkostning = 5 · n₍paid₎",
          "meaning": "Summen af 4 og 1 i planlægningsobjektivet."
        }
      ],
      "details": [
        "Gratis transfers koster ikke en indsat kunstig 2,16-points værdi.",
        "Der er mulighed for 0–5 transfers pr. GW, afhængig af budget og regler."
      ],
      "sources": [
        "src/fpl_xpts/transfer_planner.py"
      ],
      "type": "theory"
    },
    {
      "id": "ts-xi",
      "parent": "ts",
      "title": "Startopstilling og bænk",
      "summary": "TS vurderer ikke en spiller på bænken som automatisk tabt investering.",
      "idea": "For hver GW vælges den lovlige XI med størst forventede point; resten bliver bænk. Samme spiller kan bænkes i svær kamp og bruges i næste GW.",
      "formulas": [
        {
          "expression": "XI*(g) = argmax₍lovlig XI⊂Squad₎ Σᵢ∈XI xPᵢ,g",
          "meaning": "Lovlige formationskrav er indbygget."
        },
        {
          "expression": "xP₍hold₎ = Σᵢ∈XI xPᵢ + xP₍ekstra kaptajn₎",
          "meaning": "Kaptajn/vice vælges efter startopstilling."
        }
      ],
      "details": [
        "Den aktuelle TS-opgørelse medtager ikke en fuld forventet autosub-værdi i alle led; BB beregner sit nettobidrag særskilt.",
        "Faktiske replay-point følger FPLs udskiftningsregler."
      ],
      "sources": [
        "src/fpl_xpts/optimize.py",
        "src/fpl_xpts/season_replay.py"
      ],
      "type": "theory"
    },
    {
      "id": "ts-captain",
      "parent": "ts",
      "title": "Kaptajn og vice",
      "summary": "Det er værdifuldt med en god vice, hvis kaptajnen ikke spiller.",
      "idea": "Kaptajnens forventede ekstra point inkluderer en reservegevinst fra vice, hvis kaptajnen ender på nul spillede minutter.",
      "formulas": [
        {
          "expression": "B(C,VC) = xP_C + (1 − P(play_C))·xP_VC",
          "meaning": "Den låste planlægger maksimerer dette udtryk over et gyldigt kaptajn/vice-par."
        },
        {
          "expression": "Score₍manager₎ = Σᵢ∈XI xPᵢ + B(C,VC)",
          "meaning": "Kaptajnens ekstra point lægges oveni den almindelige start-XI."
        }
      ],
      "details": [
        "Udtrykket bruger xP som ubetinget forventet point og P(play) fra prognosen.",
        "TC bruger ekstra bonus til kaptajn, så den vælges kun når spilleren er i vores XI."
      ],
      "sources": [
        "src/fpl_xpts/optimize.py",
        "src/fpl_xpts/tc_chip_bridge.py"
      ],
      "type": "theory"
    },
    {
      "id": "ts-search",
      "parent": "ts",
      "title": "Dynamiske transferstier",
      "summary": "Man skal tænke flere beslutninger frem, men kun udføre én.",
      "idea": "Plannerens state-space er for stort til at opregne alt. Den bruger en begrænset candidatesøgning/beam for at beholde lovlige og lovende fremtidige hold.",
      "formulas": [
        {
          "expression": "π* = argmax₍π∈kandidater₎ J(π)",
          "meaning": "π er en plan af lovlige handlinger for de næste højst seks GW."
        },
        {
          "expression": "a_g = første handling i π* ;  næste GW: genberegn π*",
          "meaning": "Receding horizon / model predictive control."
        },
        {
          "expression": "FT₍næste₎ = T₍FT₎(FT, transfers)",
          "meaning": "Gratis transfers er en del af tilstandsudviklingen, ikke en fast pointsats."
        }
      ],
      "details": [
        "Beam-søgningen undersøger ikke alle mulige holdkombinationer; den vælger det bedste blandt kandidaterne.",
        "En transfersti kan have 0 transfers nu og senere bruge gemte FT."
      ],
      "sources": [
        "src/fpl_xpts/transfer_planner.py"
      ],
      "type": "theory"
    },
    {
      "id": "ts-prices",
      "parent": "ts",
      "title": "Budget, køb og salg",
      "summary": "De officielle FPL-prisregler sætter grænserne.",
      "idea": "Spillere, der er steget i pris, har ikke nødvendigvis samme salgspris som aktuel købspris. TS regner med holdets faktiske salgsværdi.",
      "formulas": [
        {
          "expression": "budget₍efter₎ = bank + Σ pris₍solgte₎ − Σ pris₍købte₎",
          "meaning": "Budgetkrav for et transferbundt."
        },
        {
          "expression": "salgsprisᵢ = FPL_selling_price(købsprisᵢ, nuværende_prisᵢ)",
          "meaning": "Salgspris beregnes af den officielle regel, ikke bare markedets aktuelle pris."
        }
      ],
      "details": [
        "Holdet må ikke overstige 15 spillere eller klubbens max 3.",
        "WC får korrekt samlet rådighedsbeløb fra bank og trup-salgsværdier."
      ],
      "sources": [
        "src/fpl_xpts/season_replay.py",
        "src/fpl_xpts/transfer_planner.py"
      ],
      "type": "theory"
    },
    {
      "id": "chips",
      "parent": "root",
      "title": "Chips · Sæsonbeslutninger",
      "summary": "FH, WC, BB og TC konkurrerer om den samme deadline.",
      "idea": "Modellen regner først normal TS-værdi. Derefter vurderes marginalgevinster ved hver chip. Chips kan kun anvendes én ad gangen, og hvert chip kan bruges én gang pr. halvdel i 2025/26-reglerne.",
      "formulas": [
        {
          "expression": "valg = argmax {0, Q_FH, Q_WC, Q_BB, Q_TC}",
          "meaning": "En chip vælges kun, hvis dens justerede mulighed slår normal handling."
        },
        {
          "expression": "Q_chip = forventet ekstra gevinst − værdi af at gemme chip",
          "meaning": "Prisen for at brænde en chip tidligt beskrives af en nedtrapning/option."
        }
      ],
      "details": [
        "To chipperioder: GW1–19 og GW20–38.",
        "TC vurderes gennem sin selvstændige opsparingsmodel; ikke den samme λ-grænse som FH/WC/BB."
      ],
      "sources": [
        "src/fpl_xpts/final_chip_coordinator.py"
      ],
      "type": "theory"
    },
    {
      "id": "chips-clock",
      "parent": "chips",
      "title": "Værdien af at vente",
      "summary": "Gemmerettigheden bliver mindre værd tæt på periodens sidste GW.",
      "idea": "FH, WC og BB bruger en gradvist faldende forsigtighedsgrænse. Det forhindrer, at chips spildes tidligt på små, usikre fordele.",
      "formulas": [
        {
          "expression": "f(g) = (slutGW − g) / (slutGW − startGW)",
          "meaning": "start/slut er (1,19) eller (20,38)."
        },
        {
          "expression": "Q_FH = G_FH − 10·f(g) ; Q_WC = G_WC − 20·f(g) ; Q_BB = G_BB − 20·f(g)",
          "meaning": "Låste forsigtighedsværdier."
        },
        {
          "expression": "Q_TC = xP₍TC nu₎ − max(V₍kendt fremtid₎, V₍ukendt DGW₎)",
          "meaning": "TC har separat timing- og DGW-optionalitet."
        }
      ],
      "details": [
        "På GW19 og GW38 er forsigtighedsfradraget nul for FH/WC/BB.",
        "At en grænse når nul garanterer ikke, at enhver chip bruges: mulighed og lovlighed skal stadig være til stede."
      ],
      "sources": [
        "src/fpl_xpts/simple_chip_thresholds.py",
        "src/fpl_xpts/bench_boost_policy.py",
        "src/fpl_xpts/chip_planner.py"
      ],
      "type": "theory"
    },
    {
      "id": "chips-fh",
      "parent": "chips",
      "title": "Free Hit · FH",
      "summary": "Et midlertidigt fuldt hold for én GW.",
      "idea": "FH optimerer en ny lovlig 15-mands trup for den aktuelle GW – med samme disponibel salgsværdi – og går tilbage til den permanente trup efter GW.",
      "formulas": [
        {
          "expression": "G_FH = xP(best mulig FH-XI og C/VC i GW) − xP(normal TS-XI og C/VC i GW)",
          "meaning": "Måles kun på én GW."
        },
        {
          "expression": "Q_FH = G_FH − 10·f(g)",
          "meaning": "FH er attraktiv, når enkelt-GW-opløsningen slår det at bevare chippen."
        }
      ],
      "details": [
        "Squad, købsværdier, bank og gratis transfers genskabes efter FH.",
        "Modellen bruger en kandidatbegrænset optimizer, ikke matematisk garanti for absolut globalt bedste FH-hold.",
        "Første handling med FH må ikke gennemføre permanente transfers."
      ],
      "sources": [
        "src/fpl_xpts/chip_planner.py",
        "src/fpl_xpts/simple_chip_thresholds.py"
      ],
      "type": "theory"
    },
    {
      "id": "chips-wc",
      "parent": "chips",
      "title": "Wildcard · WC",
      "summary": "Permanent truppeskifte med ubegrænsede gratis transfers.",
      "idea": "WC ses som en særlig første handling i TS, hvor mange spillerudskiftninger er gratis, og den nye trup fortsætter ind i de følgende GW’er.",
      "formulas": [
        {
          "expression": "G_WC = J₆GW(best WC-as-TS) − J₆GW(normal TS)",
          "meaning": "Begge sammenlignes på samme seksugers objective."
        },
        {
          "expression": "Q_WC = G_WC − 20·f(g)",
          "meaning": "Beslutningen påvirker de følgende GW’er, ikke kun den første."
        },
        {
          "expression": "WC → samme låste TS i næste GW",
          "meaning": "Det nye hold er permanent og genplanlægges normalt."
        }
      ],
      "details": [
        "WC-kandidaterne kommer fra en begrænset søgning; bedste fundne er ikke en global optimum-garanti.",
        "Historical 2025/26-prognoser for den fjerne 6GW-horisont var delvis cutoff-baserede proxies, ikke fuld arkiveret PM i hver fremtidig GW.",
        "WC blev valgt i GW6 og GW26 i 2025/26-replayet."
      ],
      "sources": [
        "src/fpl_xpts/wildcard_ts_action.py",
        "src/fpl_xpts/simple_chip_thresholds.py"
      ],
      "type": "theory"
    },
    {
      "id": "chips-bb",
      "parent": "chips",
      "title": "Bench Boost · BB",
      "summary": "Hele bænken scorer med i samme GW.",
      "idea": "Det er ikke nok at lægge alle bænkens xP til, fordi almindelige automatiske indskiftninger ellers allerede kan give nogle af pointene.",
      "formulas": [
        {
          "expression": "G_BB = Σᵢ∈bænk xPᵢ − E[point fra bænken ved normale autosubs]",
          "meaning": "Nettoværdien af at aktivere Bench Boost."
        },
        {
          "expression": "Q_BB = G_BB − 20·f(g)",
          "meaning": "Låst λ_BB = 20."
        },
        {
          "expression": "xP_BB = xP_normal + G_BB",
          "meaning": "Dette er ekstra forventet point i forhold til en normal XI med autosubs."
        }
      ],
      "details": [
        "BB-sandsynligheden for starteres fravær og bænkens tilgængelighed beregnes med en uafhængighedstilnærmelse.",
        "Når BB er aktiv, tæller alle 15 spilleres faktiske point; der sker ingen normale autosubs.",
        "BB blev valgt GW11/GW29 i 2025/26-replayet."
      ],
      "sources": [
        "src/fpl_xpts/bench_boost_policy.py",
        "src/fpl_xpts/season_replay.py"
      ],
      "type": "theory"
    },
    {
      "id": "chips-bb-auto",
      "parent": "chips-bb",
      "title": "Autosub-fradraget",
      "summary": "Hvorfor er 16 bænk-xP ikke altid 16 ekstra xP?",
      "idea": "Hvis din startmålmand ofte misser kampen, vil reservemålmandens point ofte allerede tælle normalt. Det samme gælder udskiftere til forsvar/midtbane/angreb, når formationen tillader det.",
      "formulas": [
        {
          "expression": "E[autosub] = Σ₍tilgængelighedsscenarier s₎ P(s) · point₍normale autosubs | s₎",
          "meaning": "Beregnes ved at enumerere mulige spille/ikke-spille-scenarier."
        },
        {
          "expression": "P(s) ≈ ∏ᵢ pᵢ^(spillerᵢ spiller) · (1−pᵢ)^(ikke spiller)",
          "meaning": "Forenkling: tilgængelighedssituationer behandles omtrent uafhængigt."
        },
        {
          "expression": "E[BB-netto] = max(0, bench_xP − E[autosub])",
          "meaning": "BB-gain er aldrig negativ i modulets definition."
        }
      ],
      "details": [
        "Auto-sub-regler inkluderer minimum antal DEF/MID/FWD, samt GK-for-GK.",
        "Denne beregning er hurtig og forklarlig, men tager ikke alle korrelationer mellem skader/rotation fuldt med."
      ],
      "sources": [
        "src/fpl_xpts/bench_boost_policy.py"
      ],
      "type": "theory"
    },
    {
      "id": "chips-bb-wc",
      "parent": "chips-bb",
      "title": "WC efterfulgt af BB",
      "summary": "To chips kan virke godt sammen – men ikke samme GW.",
      "idea": "Efter WC har vi selv valgt 15 spillere. Det kan gøre BB attraktivt i GW+1, men man kan lige så godt vente, hvis en DGW eller bedre bænk senere ser stærkere ud.",
      "formulas": [
        {
          "expression": "kandidat_BB(g) = G_BB(g) − 20·f(g), g > GW_WC",
          "meaning": "BB evalueres først i uger efter WC."
        },
        {
          "expression": "anvend BB ⇔ Q_BB(g) > max(0, Q_FH(g), Q_WC(g), Q_TC(g))",
          "meaning": "WC tvinger ikke BB, men skaber mulige gode bench-opstillinger."
        }
      ],
      "details": [
        "2025/26-valget var WC6 → BB11 og WC26 → BB29.",
        "I den endelige model beregnes BB igen på den aktuelle deadlines information."
      ],
      "sources": [
        "src/fpl_xpts/bench_boost_policy.py",
        "src/fpl_xpts/final_chip_coordinator.py"
      ],
      "type": "theory"
    },
    {
      "id": "chips-tc",
      "parent": "chips",
      "title": "Triple Captain · TC v2",
      "summary": "Tredobbelt kaptajnpoint – men kun til en spiller vi ejer.",
      "idea": "TC-v2 bruger simulationsbaserede spillerprognoser, sammenligner det aktuelle GW med fremtidige muligheder og tager højde for, at et ukendt DGW stadig kan opstå.",
      "formulas": [
        {
          "expression": "TC-ekstra ved brug = FP₍kaptajn₎",
          "meaning": "Ud over normal dobbelt kaptajn: endnu ét sæt point."
        },
        {
          "expression": "Q_TC = xP₍kandidat nu₎ − V_save",
          "meaning": "Brug kun TC, når den justerede nutidsmulighed mindst matcher fremtidsoptionen."
        },
        {
          "expression": "TC-kandidat ∈ vores start-XI",
          "meaning": "En spiller uden for den faktiske trup kan ikke få chippen."
        }
      ],
      "details": [
        "Ved aktivering kan modellen skifte kaptajn blandt de 11 starters uden at ændre transfers eller XI.",
        "TC var på Thiago i GW13 og Haaland i GW36 i det samlede 2025/26-replay.",
        "Historisk TC-future fixturearkiv kan indeholde efterfølgende afklaret kampprogram; dette er en kendt live-databegrænsning."
      ],
      "sources": [
        "src/fpl_xpts/chip_planner.py",
        "src/fpl_xpts/tc_chip_bridge.py"
      ],
      "type": "theory"
    },
    {
      "id": "chips-tc-select",
      "parent": "chips-tc",
      "title": "Spillervalg og upside",
      "summary": "Vælg ikke blot spilleren med størst ekstremt udfald.",
      "idea": "TC-kandidater vælges ud fra gennemsnitlige forventede point, men i et snævert interval kan højre side af fordelingen (75%-kvantilen) afgøre valget.",
      "formulas": [
        {
          "expression": "C_g = {i : μᵢ,g ≥ maxⱼ μⱼ,g − 0,50}",
          "meaning": "Alle inden for 0,50 xP fra den højeste kandidat er relevante."
        },
        {
          "expression": "i* = argmaxᵢ∈C_g Q₀,₇₅(FPᵢ,g)",
          "meaning": "Den højeste 75%-kvantil afgør blandt nærliggende kandidater."
        },
        {
          "expression": "xP_TC,nu = E[FPᵢ*,g]",
          "meaning": "Det er stadig det forventede point, der sammenlignes med at vente."
        }
      ],
      "details": [
        "Kandidatsættet til det aktuelle GW begrænses til spillere i vores start-XI i den samlede appmodel.",
        "Fremtidige kandidater kan skifte, når TS senere foretager transfers."
      ],
      "sources": [
        "src/fpl_xpts/chip_planner.py",
        "src/fpl_xpts/tc_chip_bridge.py"
      ],
      "type": "theory"
    },
    {
      "id": "chips-tc-future",
      "parent": "chips-tc",
      "title": "TC: fremtid og DGW-option",
      "summary": "Et endnu uafklaret DGW kan gøre det klogt at gemme TC.",
      "idea": "Fremtidige forventninger regresseres mod en historisk baseline, og en strukturel sandsynlighed for ukendt DGW kan skabe ekstra værdi ved at vente.",
      "formulas": [
        {
          "expression": "μ₍TC baseline₎ = 8,57",
          "meaning": "Kalibreret forventningsreference i låst TCV2Config."
        },
        {
          "expression": "V_future(g+k) = μ_TC + Rₖ · (xP₍fremtid₎ − μ_TC)",
          "meaning": "Rₖ er en empirisk pålidelighedskurve; eksempel R₁≈0,757."
        },
        {
          "expression": "P₍ukendt DGW₎ = P₍strukturel DGW₎ · (1−P₍konkret DGW₎)",
          "meaning": "DGW-optionaliteten forsvinder, når muligheden bliver kendt/indregnet."
        },
        {
          "expression": "V_latent = μ_TC + P₍ukendt DGW₎ · [max(12,26875, μ_TC) − μ_TC]",
          "meaning": "Kalibreret baseline for et fremtidigt DGW."
        },
        {
          "expression": "V_save = max(V_future, V_latent)",
          "meaning": "TC bruges, hvis den nuværende kandidat er bedre end begge former for at vente."
        }
      ],
      "details": [
        "Kurven Rₖ og DGW-referenceværdien er låst – der er ikke samme λ=20 som WC eller BB.",
        "Den historiske TC-kalibrering er ikke bevis for fuld cutoff-sikker fremtidig fixture-information."
      ],
      "sources": [
        "src/fpl_xpts/chip_planner.py"
      ],
      "type": "theory"
    },
    {
      "id": "chips-arbiter",
      "parent": "chips",
      "title": "Fælles chipvalg",
      "summary": "To gode chips må ikke bruges samtidig.",
      "idea": "Alle fire chips evalueres med hver deres forventede marginalværdi. Koordinatoren vælger kun én lovlig handling eller ingen chip.",
      "formulas": [
        {
          "expression": "Q = {normal:0, FH:G_FH−10f, WC:G_WC−20f, BB:G_BB−20f, TC:TC_use_edge}",
          "meaning": "TC kommer kun med, hvis TC-v2 siger USE_TC, og kandidaten er i vores XI."
        },
        {
          "expression": "chip* = argmax₍tilgængelige chips + normal₎ Q",
          "meaning": "Ved lighed bevares chippen frem for at bruge den uden gevinst."
        }
      ],
      "details": [
        "Chipperioderne er GW1–19 og GW20–38 i 2025/26-versionen.",
        "Et WC ændrer den permanente trup; et FH gør ikke; BB/TC ændrer ikke transferstien."
      ],
      "sources": [
        "src/fpl_xpts/final_chip_coordinator.py"
      ],
      "type": "theory"
    },
    {
      "id": "data",
      "parent": "root",
      "title": "Datagrundlag og validering",
      "summary": "Hvad må modellen vide, og hvad er stadig begrænset?",
      "idea": "God beslutningsmatematik er kun nyttig, hvis prognoserne afspejler information, der eksisterede på den pågældende GW-deadline.",
      "formulas": [
        {
          "expression": "features₍GW g₎ = information med timestamp < deadline_g",
          "meaning": "Ingen fremtidige faktiske resultater, skader eller kampflytninger må lække ind i historiske beslutninger."
        },
        {
          "expression": "historisk scoring = Σ₍GW₎ FPL-point₍faktisk resultat₎ − officielle hits",
          "meaning": "Den er et diagnostisk replay, ikke et estimat af fremtidig evne."
        }
      ],
      "details": [
        "MM/PM/TS/chip-logik er låst; live dataindlæsning og cutoff-kontrol er en separat integrationsopgave.",
        "2025/26 samlet historisk resultat er 2.266 point inklusive chips."
      ],
      "sources": [
        "analysis/FINAL_FPL_MODEL_MANIFEST_20261009.md"
      ],
      "type": "theory"
    },
    {
      "id": "data-cutoff",
      "parent": "data",
      "title": "Cutoff og ingen lækage",
      "summary": "En prognose må ikke kende facit.",
      "idea": "Alle features skal være kendt inden deadline. En fremtidig DGW, der endnu ikke er offentliggjort, må håndteres som usikkerhed, ikke som en sikker kamp.",
      "formulas": [
        {
          "expression": "known_at(record) < cutoff_g",
          "meaning": "Lad informationens tidspunkt bestemme, om den må indgå."
        },
        {
          "expression": "E[point | 𝔽_g]",
          "meaning": "Forventningen betinges på den information, der var kendt på GW g."
        }
      ],
      "details": [
        "Dagens senest downloadede data er ikke automatisk gyldige til et historisk replay.",
        "Future-match-arkiver til TC og WC har dokumenterede forbehold, som skal håndteres i live bridge."
      ],
      "sources": [
        "analysis/CHIP_DECISION_READINESS.md"
      ],
      "type": "theory"
    },
    {
      "id": "data-results",
      "parent": "data",
      "title": "Hvad gav de låste modeller?",
      "summary": "Et konkret historisk benchmark med og uden chips.",
      "idea": "De historiske sæsonsimuleringer bruger samme grundlæggende transfer- og prognosemotor. Chips tilføjes ovenpå som tydelige beslutninger.",
      "formulas": [
        {
          "expression": "2025/26: TS alene = 2.125 · FH/WC = 2.209",
          "meaning": "Første store forbedring fra de to trupspecifikke chips."
        },
        {
          "expression": "+ BB = 2.242 · + TC = 2.266",
          "meaning": "Samlet chipsystem gav 141 point mere end TS alene i den historiske simulering."
        },
        {
          "expression": "2024/25 GW6–38: FH/WC/BB = 2.060",
          "meaning": "Betinget tværsæsonskontrol; ikke en komplet 38-GW-sæson."
        }
      ],
      "details": [
        "2025/26 er in-sample med chips, ikke en blind out-of-sample test.",
        "Cutoff-fremskrivninger i WC og historisk TC-kalender betyder, at historisk score ikke bør bruges som påstået live-forecast."
      ],
      "sources": [
        "analysis/FINAL_FPL_MODEL_MANIFEST_20261009.md",
        "analysis/BB_FIT_CROSS_SEASON_20261009.md"
      ],
      "type": "results"
    },
    {
      "id": "data-code",
      "parent": "data",
      "title": "Kode og versionering",
      "summary": "Hver ligning kan spores til implementationen.",
      "idea": "Detaljvisningen indeholder kildelinks. Matematikken er dokumenteret i to niveauer: eksakte beslutningsformler og skematiske forklaringer, hvor den konkrete estimator er mere kompleks.",
      "formulas": [
        {
          "expression": "låst parameter → kildekode → test → historisk replay",
          "meaning": "Fire separate led i verifikationen."
        },
        {
          "expression": "checkpoint = fpl-model-complete-locked-20261009",
          "meaning": "Den frosne kildeversion er udgangspunktet for dokumentationen."
        }
      ],
      "details": [
        "Math-intuition markerer forklaringer, der forenkler den fulde indlærte model.",
        "Vi holder den låste modelkode uændret, mens vi opdaterer designet."
      ],
      "sources": [
        "config/fpl_locked_model.json",
        "tests/test_final_fpl_chain.py"
      ],
      "type": "theory"
    }
  ]
};
