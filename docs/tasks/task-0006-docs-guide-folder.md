---
nummer: task-0006
titel: Rammeværkets dokumentation i sin egen mappe
status: planlagt
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
### Hvad er ikke lavet, og hvorfor
### Uklart
