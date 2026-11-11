---
nummer: task-0006
titel: Rammeværkets dokumentation i sin egen mappe
status: afsluttet
kilde: interview
oprettet: 2026-11-11
---

# task-0006 — Rammeværkets dokumentation i sin egen mappe

## Hvad og hvorfor
Rammeværkets dokumentation til app-udviklere ligger i `docs/` sammen med
projektets arbejdsfiler (tavle, opgaver, beslutningslog, rapportmapper). Det gør
det svært at se hvad der er dokumentation, og hvad der er arbejdsfiler.
Dokumentationen flyttes til `docs/guide/`. Arbejdsfilerne bliver hvor kontrakten
kræver dem, så rollerne stadig finder dem.

## Færdig når
- [ ] Alle rammeværkets dokumentationssider ligger i `docs/guide/`, med uændret indhold bortset fra links.
- [ ] Filerne er flyttet så historikken følger med.
- [ ] Alle links mellem siderne, fra projektets README og fra `CLAUDE.md` peger på de nye placeringer og virker.
- [ ] `docs/README.md` er en kort oversigt over mappen: at `guide/` er rammeværkets dokumentation og hvor man starter, og at resten er projektets arbejdsfiler, så man ikke leder dér.
- [ ] Arbejdsfilerne og deres mapper ligger hvor de lå.

## Sådan ser det ud
Godkendt af mennesket.
```
docs/
  README.md          ← kort oversigt over mappen
  guide/             ← rammeværkets dokumentation
    README.md        (Getting started)
    auth.md
    database.md
    frontend.md
    routes.md
    tableviewer.md
    users.md
    webserver.md
    SignInForm.md
  BOARD.md           ← arbejdsfiler, som kontrakten kræver dem
  decisions/
  tasks/
  tests/  securities/  reviews/  debugs/
```
Projektets README beholder sin struktur; kun linkene ændres, fx `docs/auth.md` → `docs/guide/auth.md`.

## Sådan bygger vi det
- `git mv` for hver side: `docs/README.md`, `auth.md`, `database.md`, `frontend.md`, `routes.md`, `tableviewer.md`, `users.md`, `webserver.md`, `SignInForm.md` → `docs/guide/`.
- Siderne linker til hinanden med relative links i samme mappe; de virker uændret. Tjek alligevel hvert link efter flytningen, også ankre.
- Nyt `docs/README.md` på engelsk, som resten af dokumentationen. Kort: én linje om `guide/` med link til `guide/README.md`, og én linje om at `BOARD.md`, `decisions/`, `tasks/`, `tests/`, `securities/`, `reviews/` og `debugs/` er projektets arbejdsfiler (arbejdsmetoden i `AGENTS.md`), ikke dokumentation.
- `CLAUDE.md`: ret henvisningen til dokumentationen og mappestrukturtabellen.
- Projektets `README.md` rører du ikke; architect retter linkene der, før grenen lukkes.
- Rør ikke noget under `.claude/`.
- Efterprøv med et lille script at hvert relativt markdown-link i `README.md`, `CLAUDE.md` og `docs/` peger på en fil der findes.

## Hvad vi ikke rører
- Indholdet af siderne, ud over links.
- Arbejdsfilerne og deres placering. `docs/BOARD.md` er slettet i arbejdstræet af mennesket; den gendannes af architect efter denne opgave.
- Koden.

## Afhænger af
task-0001

## Beslutninger
- BESLUTTET: Dokumentationen flyttes til `docs/guide/`; arbejdsfilerne bliver — menneskets valg. At flytte arbejdsfilerne ud af `docs/` blev afvist: kontraktens roller har stierne skrevet ind.

## Åbne punkter

## Indvendinger

---

## Developers noter

<Alt over denne overskrift ejes af architect. Alt herunder skrives kun af
developer, som aldrig retter i definitionen ovenfor.>

### Hvad er lavet
Bygget direkte på `main` og ikke committet, som besluttet i `docs/decisions/log.md`.

- **Siderne ligger i `docs/guide/`, med uændret indhold.** `git mv` af `README.md`,
  `auth.md`, `database.md`, `frontend.md`, `routes.md`, `tableviewer.md`, `users.md`,
  `webserver.md` og `SignInForm.md` fra `docs/` til `docs/guide/`. `git diff --cached -M --stat`
  viser ni omdøbninger med 0 ændrede linjer. Ingen link i siderne skulle rettes: alle
  links mellem dem er relative inden for samme mappe, og ingen peger ud af `docs/`.
- **Historikken følger med.** Flytningerne er staged som omdøbninger (`R`). Index
  indeholder kun de ni omdøbninger, så de kan committes for sig. Se `### Uklart` om
  `docs/guide/README.md`.
- **Links.** `CLAUDE.md`, linje 9: henvisningen er nu `docs/guide/` og `docs/guide/README.md`.
  Mappestrukturtabellen har nu to rækker: `docs/guide/` (dokumentationen og `SignInForm.md`)
  og `docs/` (oversigten og kontraktens arbejdsfiler).
- **`docs/README.md` er ny**, på engelsk. Den er kort: én linje om `guide/` med link til
  `guide/README.md`, og én linje om at `BOARD.md`, `decisions/`, `tasks/`, `tests/`,
  `securities/`, `reviews/` og `debugs/` er projektets arbejdsfiler, med link til
  `../AGENTS.md`. `BOARD.md` står som navn og ikke som link, fordi filen ikke findes lige nu.
- **Linktjek.** Et script tjekker hvert relativt markdown-link i `README.md`, `CLAUDE.md`
  og `docs/**/*.md`: findes filen, og findes ankeret (GitHubs regel for ankre, uden
  overskrifter i kodeblokke). Det ligger kun i min scratchpad og er ikke en del af repoet,
  for opgaven beder ikke om et varigt testapparat. `.claude/` er ikke med. Jeg har set
  det fange et forkert anker og en manglende fil i en testmappe. Resultat: 57 links
  tjekket, 6 brudt, og alle 6 er i projektets `README.md`, som architect retter (se nedenfor).
  Alle links og ankre i `docs/` og `CLAUDE.md` virker.
- **Arbejdsfilerne ligger hvor de lå.** `docs/decisions/`, `docs/tasks/`, `docs/tests/`,
  `docs/securities/`, `docs/reviews/` og `docs/debugs/` er ikke rørt. `docs/BOARD.md` er ikke oprettet.
- Statussen står på `i-gang`.

**Links architect skal rette i projektets `README.md`:**

| Linje | Nu | Skal være |
|---|---|---|
| 10 | `docs/README.md` ("The wiki lives in `docs/`") | `docs/guide/README.md`. Linkteksten `docs/` kan blive til `docs/guide/` |
| 12 | `docs/README.md` (Getting started) | `docs/guide/README.md` |
| 13 | `docs/webserver.md` | `docs/guide/webserver.md` |
| 14 | `docs/routes.md` | `docs/guide/routes.md` |
| 15 | `docs/database.md` | `docs/guide/database.md` |
| 16 | `docs/auth.md` | `docs/guide/auth.md` |
| 17 | `docs/users.md` | `docs/guide/users.md` |
| 18 | `docs/frontend.md` | `docs/guide/frontend.md` |

Linje 10 og 12 virker teknisk stadig, fordi `docs/README.md` findes. Men de lander nu
på mappeoversigten og ikke på Getting started. Derfor fanger linktjekket dem ikke.

Ingen nye kommandoer eller indstillinger.

### Hvad er ikke lavet, og hvorfor
- **Projektets `README.md` er ikke rettet.** Den er uden for opgaven (architect retter
  linkene). Listen står ovenfor.
- **`.env` er ikke tjekket for henvisninger til de gamle stier.** En søgning gav et
  træk på `docs/` i `.env`, men en regel nægter mig at læse filen. Hvis det er en
  kommentar der peger på fx `docs/auth.md`, skal den pege på `docs/guide/auth.md`. Det
  er en lokal fil uden for versionsstyring, så det er menneskets at se efter.
  `.env.example` nævner ikke `docs/`.
- **Ingen commit**, som besluttet.

### Uklart
- **Historikken for `docs/guide/README.md` følger kun med hvis flytningen committes
  for sig.** Hvis omdøbningen og det nye `docs/README.md` kommer i samme commit, ser git
  `docs/README.md` som ændret og `docs/guide/README.md` som en ny fil. Så følger
  `git log --follow` ikke den gamle historik. De otte andre sider er ikke berørt.
  Jeg har derfor kun staged de ni omdøbninger og ladet det nye `docs/README.md` være
  untracked. Så kan mennesket committe i to trin, med kommandoerne nedenfor (plus
  hvert sit `-m`). `CLAUDE.md` og opgavefilen er heller ikke staged.
  ```
  git commit
  git add docs/README.md CLAUDE.md docs/tasks/task-0006-docs-guide-folder.md
  git commit
  ```
  Om det skal være to commits eller én, er menneskets valg.
