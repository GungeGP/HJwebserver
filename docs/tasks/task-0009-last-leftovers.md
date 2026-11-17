---
nummer: task-0009
titel: Ryd de sidste rester af det gamle login og den forældede pakkeinfo
status: planlagt
kilde: interview
oprettet: 2026-11-11
---

# task-0009 — Ryd de sidste rester af det gamle login og den forældede pakkeinfo

## Hvad og hvorfor
Efter task-0003 er der stadig beskrivelser og en smule kode der hører til appens
gamle login, og pakkeinformation der er versionsstyret selv om den ikke skal
være det. De gør ingenting, men de vildleder den der læser koden. Fundne i
developers noter til task-0002–task-0005.

## Færdig når
- [ ] Ingen beskrivelser i koden nævner bruger- eller sessionsstyring, loginformularen eller adgangskodeskift.
- [ ] TableViewers script tjekker ikke længere for et svar om adgangskodeskift, som serveren aldrig sender.
- [ ] Det ubrugte alias `check_auth` findes ikke længere.
- [ ] Mappen `HJwebserver.egg-info` er ikke længere versionsstyret. Den ligger stadig på disken, og den udelukkes som `.gitignore` allerede siger.
- [ ] Alt virker uændret: login via Authentik, roller, formulartoken, audit, TableViewer og sidemenuen.

## Sådan ser det ud i en app
Intet ændres i appens kode.

## Sådan bygger vi det
- Docstrings i `WebServer/__init__.py`, `WebServer/core/__init__.py` og `WebServer/page.py`.
- Kommentarerne og tjekket for adgangskodeskift i `WebServer/public/js/TableViewer.js`.
- `check_auth = resolve_user` i `WebServer/auth.py`.
- `git rm -r --cached HJwebserver.egg-info`, så sletningen står klar til menneskets commit. Mappen på disken røres ikke.
- Ingen ny gren og ingen commit; mennesket committer selv.

## Hvad vi ikke rører
- Adfærd. Det her er kun beskrivelser, død kode og versionsstyring.

## Afhænger af
task-0003

## Beslutninger
- BESLUTTET: Samles i én opgave — samme slags rester som task-0003, samme kontrol: intet ændrer adfærd.

## Åbne punkter

## Indvendinger

---

## Developers noter

<Alt over denne overskrift ejes af architect. Alt herunder skrives kun af
developer, som aldrig retter i definitionen ovenfor.>

### Hvad er lavet
### Hvad er ikke lavet, og hvorfor
### Uklart
