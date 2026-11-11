# Beslutningslog

Append-only. Nyeste øverst. Én linje pr. beslutning.

**Ejes af `architect`.** Dens tråd er den eneste samtale i modellen, og loggen er det eneste spor af den der overlever tråden. Hver beslutning truffet i en `architect`-tråd skrives ind, med begrundelse, før tråden lukkes.

Her hører også **afvisninger**: et fund der ikke bliver en opgave, skal have sin begrundelse her. Ellers er det et fund der forsvandt.

`Nr.` er nummeret beslutningen hører til — `task-0042`, `test-0003` — eller `—` hvis den gælder projektet som helhed.

| Dato | Nr. | Beslutning | Begrundelse | Rolle |
|---|---|---|---|---|
| 2026-11-11 | task-0008 | Afvist før den blev bygget; menuens nuværende udseende beholdes | Menneskets valg: afvigelserne fra skærmbillederne er fine | architect |
| 2026-11-11 | task-0008 | Menuens farver og detaljer rettes til skærmbillederne | Set i browseren: grøn i stedet for skifergrå, lysere orange, grå baggrund, venstrestillet tekst nederst, Admin uden rund knap i den smalle udgave, ingen luft til indholdet | architect |
| 2026-11-11 | task-0007 | Små regler godkendt: nedtonede punkter henter ikke tal; skjult overpunkt skjuler underpunkterne; underpunkter kan have underpunkter | Developers valg; ingen grund til andet | architect |
| 2026-11-11 | task-0007 | Hjælpeteksterne på knapperne er på dansk | Som menuens øvrige tekster fra skærmbillederne | architect |
| 2026-11-11 | task-0007 | Korte navne uden `short=` er titlens første fire tegn | Developers valg; passer til den smalle udgave | architect |
| 2026-11-11 | task-0007 | HTML-filer direkte fra `public/` får menuen uden mulighed for at fravælge den | Siden kan registreres med `addPath(..., menu=False)` når den skal være uden; partials uden `<body>` røres ikke | architect |
| 2026-11-11 | task-0007 | Menuens stylesheet linkes af serveren, og et lille inline-script klapper menuen sammen før første tegning | Ellers blinker menuen ved hvert sideskift. Med en strengere CSP blinker den åben; det accepteres | architect |
| 2026-11-11 | task-0007 | Uden login sendes `hj:ready` ikke; egen navigation bruger `DOMContentLoaded` dér, som `menu.md` siger | `hjMenu` er sat før `DOMContentLoaded`; at ændre `auth.js` var uden for opgaven | architect |
| 2026-11-11 | task-0007 | På en offentlig side uden bruger viser menuen kun punkter for offentlige sider | Punkter brugeren ikke kan åbne uden login, skjules som andre punkter man ikke må åbne | architect |
| 2026-11-11 | task-0007 | Opgaven er afsluttet: bygget | 92 HTTP-tjek holdt; architect så menuen i browseren: underpunkter, aktivt punkt, tal, Admin-knap, "Logget ind som", sammenklapning der huskes. Udseendet afviger fra skærmbillederne; det er task-0008 | architect |
| 2026-11-11 | task-0006 | Fundet om at `.env` nævner `docs/` bliver ikke en opgave; mennesket retter selv sin `.env` | `.env` er menneskets og må ikke læses af rollerne. Linjerne er de `MS_*`-pladsholdere med en henvisning til `docs/SignInForm.md`, som blev tilføjet før skiftet til Authentik | architect |
| 2026-11-11 | — | Tavlen gendannet i `docs/` ved siden af `guide/` | task-0006 har adskilt dokumentationen fra arbejdsfilerne | architect |
| 2026-11-11 | task-0006 | Opgaven er afsluttet: bygget | Alle kriterier holder. Linktjek: 57 links, 0 brudte, efter at architect rettede README-linkene | architect |
| 2026-11-11 | task-0006 | Rækkefølge: task-0006 bygges før task-0007, så menuens dokumentationsside lægges i `docs/guide/` fra start. Ingen af dem sendes af sted før task-0001's kode er på `main` | Menneskets valg om rækkefølgen. task-0001's commits (`edd0a66`–`aeed6fe`) er ikke merget; dokumentationen der skal flyttes, og rollerne menuen bygger på, kommer derfra | architect |
| 2026-11-11 | task-0007 | "Logget ind som" viser rollen | Som på menneskets skærmbillede | architect |
| 2026-11-11 | task-0007 | Skjulte punkter som standard; `denied="disable"` viser dem nedtonet | Mennesket bad om både skjult og deaktiveret; skjult er det sikre udgangspunkt | architect |
| 2026-11-11 | task-0007 | Alle sider får menuen når den er slået til; `menu=False` på `addPath` fravælger den | En side uden for menuen, fx en sagsside, skal stadig have navigationen | architect |
| 2026-11-11 | task-0007 | `sidebar=False` med punkterne tilgængelige i siden er med fra start | Egen navigation får rollefiltrering og tal uden at gentage reglerne | architect |
| 2026-11-11 | task-0007 | Admin-knappen fører til en tom side, som appens egen `/admin` erstatter; ingen indbyggede admin-værktøjer | Menneskets valg: der skal være bygget til det, ikke mere | architect |
| 2026-11-11 | task-0007 | `count=` peger på en adresse der svarer med tallet | Siden bliver ikke langsommere; adressen kan have roller. Python-funktion i menuen afvist | architect |
| 2026-11-11 | task-0007 | Almindelige sideskift; serveren sætter menuen ind i hver side | Sidernes scripts virker uændret. Indholdsskift med JavaScript afvist. Mennesket: prøv det, ellers tag det derfra | architect |
| 2026-11-11 | task-0007 | Menupunkter peger på `addPath`-sider; roller kun på siden; start nægtes ved ukendt adresse | Én måde at lave en side på; menu og adgang kan ikke komme ud af trit | architect |
| 2026-11-11 | task-0007 | Menuen og dens punkter defineres i `app.menu(...)` | Menneskets krav | architect |
| 2026-11-11 | — | Ingen nye grene for nu; opgaver bygges på `main`. Afviger fra kontraktens én gren pr. opgave | Menneskets valg | architect |
| 2026-11-11 | — | Mennesket committer, merger og pusher selv; ingen rolle kører de linjer, og ingen commit får en `Co-Authored-By`-linje. Afviger fra kontraktens trin 8 | Menneskets valg | architect |
| 2026-11-11 | — | Tavlen gendannes først når task-0006 er bygget, og gemmer imens sin tilstand her: task-0001 afsluttet; task-0002 til task-0006 planlagt; emner: forretningsværdier ud af eksempelapp og docs, testsuite, præferencer for database og logning, LF-linjeskift, lokale indstillinger og miljøfiler ude af git | Mennesket slettede tavlen fordi den lå blandt dokumentationen | architect |
| 2026-11-11 | task-0006 | Rammeværkets dokumentation flyttes til `docs/guide/`; arbejdsfilerne bliver i `docs/` | Menneskets valg. At flytte arbejdsfilerne ud af `docs/` afvist: rollerne har stierne skrevet ind | architect |
| 2026-11-11 | — | Emnet "Skriv README'en om på dansk til dem der bruger og driver rammeværket" afvises | Følger af beslutningen ovenfor | architect |
| 2026-11-11 | — | README.md beholder menneskets struktur: engelsk navigation til `docs/`, ingen opsætning i den. Kun linjer tilføjes eller rettes. Afviger fra kontraktens `## README` | Rammeværket er et udviklerværktøj med meget dokumentation; README'en skal gøre det let at finde den rigtige side. Menneskets valg; en architect-omskrivning blev rullet tilbage | architect |
| 2026-11-11 | task-0005 | Eksempelappen starter i udviklingstilstand; driften står som kommentar | Menneskets valg: den skal kunne køres direkte lokalt, før Authentik er sat op | architect |
| 2026-11-11 | task-0001 | Advarslen om en gammel worktree ved hver commit bliver ikke en opgave | Den kommer fra en lokal oprydningsrest uden for koden; det er menneskets maskine, ikke projektets | architect |
| 2026-11-11 | task-0004 | `.env` skal findes fra appens mappe, ikke rammeværkets | Uden det virker rammeværket ikke installeret som pakke, og eksemplerne fra task-0001 bygger på `.env` | architect |
| 2026-11-11 | task-0003 | PyJWT, det gamle stylesheet, sidemærket, ubrugte databasefunktioner og `CLAUDE.md` ryddes i én opgave | Samme årsag og samme kontrol: intet må ændre adfærd | architect |
| 2026-11-11 | task-0002 | `auth=True` tvinger rammeforbuddet på alle svar | Kontraktens krav gælder hvert svar; i task-0001 gjaldt det kun med standardindstillingerne | architect |
| 2026-11-11 | task-0001 | Navnene `X-CSRF-Token` og `csrfToken` godkendes som valgt af developer | Gængse navne; ingen grund til andet | architect |
| 2026-11-11 | task-0001 | Udviklingstilstand kræver ikke `PROXY_SECRET` | Nøglen tjekkes ikke dér; tokenet og `JWT_SECRET` gælder stadig | architect |
| 2026-11-11 | task-0001 | "Første match" uden rangordning er rækkefølgen i `authentikRoles` | App-udvikleren styrer den rækkefølge, ikke rækkefølgen i Authentiks header | architect |
| 2026-11-11 | task-0001 | `/logout` er offentlig | Log ud skal virke, også når Authentik-sessionen er udløbet | architect |
| 2026-11-11 | task-0001 | Rammeværkets egne scripts, styles og `/logout` står i listen over offentlige stier, efter appens egne | Uden dem virker en offentlig side ikke for en der ikke er logget ind | architect |
| 2026-11-11 | task-0001 | Opgaven er afsluttet: bygget | Alle kriterier holder. Eksempel 6 efterprøvet i browser af architect. Rammeforbuddet på alle svar mangler med andre end standardindstillingerne, og det er task-0002 | architect |
| 2026-11-11 | task-0001 | `.env` læses når appen oprettes, ikke først i `settings()` | Så app-udvikleren kan læse gruppenavne med `os.environ` i `main.py` | architect |
| 2026-11-11 | task-0001 | De seks `main.py`-eksempler i opgaven er grænsefladen der bygges til | Godkendt af mennesket; rammeværkets kald er dets egentlige brugerflade | architect |
| 2026-11-11 | task-0001 | Databasens tabeller og kolonner til det gamle login bliver stående | Systemet kører i drift; ingen data slettes uden grund | architect |
| 2026-11-11 | task-0001 | Kommandolinjens bruger-, rolle-, sessions- og lockout-kommandoer fjernes | De styrer intet, når login og roller kommer fra Authentik | architect |
| 2026-11-11 | task-0001 | En bruger i ingen koblet gruppe får den laveste rolle | Authentik har allerede afgjort at personen må bruge systemet | architect |
| 2026-11-11 | task-0001 | Appens egne tokens til scripts fjernes | Kontrakten kræver at alle kald går gennem proxyen; scripts bruger servicekonti i Authentik | architect |
| 2026-11-11 | task-0001 | Udviklingstilstand med en falsk bruger, kun på den lokale maskine | Rammeværkets brugere skal kunne afprøve roller lokalt; spærren hindrer brug i drift | architect |
| 2026-11-11 | task-0001 | `auth=True` slår beskyttelsen til, og offentlige sider findes stadig | Menneskets krav: rammeværket skal stadig kunne køre uden login og med offentlige sider | architect |
| 2026-11-11 | task-0001 | Roller kommer fra brugerens grupper i Authentik | Ét sted at styre adgang, via AD-grupper; lokal rollestyring afvist | architect |
| 2026-11-11 | task-0001 | Login kun med d1 via Authentik foran appen; appens eget login og Microsoft-login i appen fjernes | Menneskets valg. Microsoft-login i appen afvist; planen bevares i SignInForm.md og koden i historikken | architect |
| 2026-11-11 | — | Microsoft-login committet direkte på default-branch før opgaven blev oprettet | Gjort af mennesket; ikke pushet; historikken omskrives ikke | architect |
