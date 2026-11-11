---
nummer: task-0003
titel: Fjern resterne af det gamle login
status: planlagt
kilde: interview
oprettet: 2026-11-11
---

# task-0003 — Fjern resterne af det gamle login

## Hvad og hvorfor
Efter task-0001 er der kode, filer og beskrivelser tilbage der kun hørte til
appens eget login. De gør ingenting, men de får rammeværket til at se ud som om
der stadig findes adgangskoder og sessioner. Fundne i developers noter til
task-0001.

## Færdig når
- [ ] `PyJWT` står ikke længere i afhængighederne og bruges ingen steder.
- [ ] Stylesheetet til den gamle loginformular og ruten til det findes ikke længere.
- [ ] Filhåndteringen sætter ikke længere et sidemærke som intet læser.
- [ ] Databaselaget har ingen funktioner til brugere, sessioner, lockout eller Microsoft-konti, som intet kalder. Beskrivelserne i modulet passer med det der er tilbage.
- [ ] `CLAUDE.md` beskriver login via Authentik og nævner ikke Microsoft-login, sessioner, `cryptography` eller kommandoer der er fjernet.
- [ ] Alt fra task-0001 virker uændret.

## Sådan ser det ud i en app
Intet ændres i appens kode.

## Sådan bygger vi det
- `requirements.txt`: fjern `PyJWT`. Tjek at intet importerer `jwt`.
- `WebServer/public/css/auth.css` og dens rute i `core/server.py`/`core/assets.py` fjernes.
- `FileHandler.py`: fjern `_hj_page`, når intet læser det.
- `WebServer/database/auth.py` og `database/__init__.py`: fjern de ubrugte funktioner, ret modulets docstring. Tabellerne og migreringerne i `database/core.py` står — de bliver efter beslutningen i task-0001.
- `CLAUDE.md`: ret stak, kommandoer (kun `audit` er tilbage i kommandolinjen), mappestruktur og begreber til Authentik.

## Hvad vi ikke rører
- Skemaet og migreringerne. Tabellerne bliver stående.
- Motoren fra task-0001.

## Afhænger af
task-0001

## Beslutninger
- BESLUTTET: Rester samles i én opgave — de har samme årsag og samme kontrol: at intet ændrer adfærd.
- BESLUTTET: `CLAUDE.md` rettes her af `developer` — den er ikke architects fil.

## Åbne punkter

## Indvendinger

---

## Developers noter

<Alt over denne overskrift ejes af architect. Alt herunder skrives kun af
developer, som aldrig retter i definitionen ovenfor.>

### Hvad er lavet
### Hvad er ikke lavet, og hvorfor
### Uklart
