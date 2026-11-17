---
nummer: task-0003
titel: Fjern resterne af det gamle login
status: afsluttet
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
- `requirements.txt`: `PyJWT` fjernet. Intet i `WebServer/` eller `main.py` importerer `jwt`; efterprøvet ved at en app med `auth=True` starter uden at `jwt` er i `sys.modules`. `cryptography` stod ikke i filen i forvejen. Pakken er ikke afinstalleret fra `.venv`.
- `WebServer/public/css/auth.css` slettet (kun i arbejdstræet, ikke staget). Ruten fjernet i `core/server.py`, aliaset `/public/css/auth.css` i `core/assets.py`, og docstringen i `_register_asset_route` siger nu kun `auth.js`. `/css/auth.css` og `/public/css/auth.css` svarer 404, og linjen er væk fra listen over offentlige stier til Authentik ved start.
- `WebServer/FileHandler.py`: `_hj_page` og kommentaren til den fjernet. Intet læste den.
- `WebServer/database/auth.py`: alle funktioner til brugere, sessioner, lockout og Microsoft-konti fjernet, også `_USER_COLUMNS`. Tilbage er `insert_audit`, `delete_audit_before` og `get_audit_log`, som `auth.py` og `app.getAuditLog()` kalder. Modulets docstring beskriver det der er tilbage, og at de tre gamle tabeller oprettes men ikke bruges.
- `WebServer/database/__init__.py`: genudsender kun de tre audit-funktioner; docstringen er rettet.
- `CLAUDE.md`: stak (Authentik, `python-dotenv`; ingen `PyJWT` eller `cryptography`), kommandoer (kun `audit`), miljø (`PROXY_SECRET`, `JWT_SECRET`, udviklingstilstand), mappestruktur (uden `microsoft.py`; med `menu.py`, `core/menu.py`, `page.py`, `FileHandler.py`, `helper.py`, `docs/guide/`) og begreber (proxynøgle, roller fra grupper, `devUser`, formulartoken, rammeforbud, sidemenuen, de tre ubrugte tabeller). Sessioner og Microsoft-login er ikke nævnt; kun `SignInForm.md` beskrives som en plan der ikke er bygget.
- `docs/guide/routes.md`: rækken for `GET /css/auth.css` fjernet fra tabellen over rammeværkets ruter.
- `docs/guide/database.md`: afsnittet *Built-in queries* fjernet. Det viste `get_user_by_username`, `create_user` og `update_user_password` som funktioner en app kan kalde, og de findes ikke længere.

Holdt op mod *Færdig når*, efterprøvet med HTTP-kald mod en egen server på SQLite i en midlertidig mappe og med kommandolinjen (29 tjek, alle holdt):
- Alt fra task-0001: bruger fra `X-authentik-*`, rolle fra grupper og rollehierarki, 403 på en admin-side for en bruger, 401 uden bruger, offentlig side uden bruger, nøgen 403 uden nøgle med forfalsket bruger, `/api/verify` med rolle og formulartoken, `POST` uden token afvist og med token igennem, `/logout` til Authentik, audit-loggen skrevet og læst, oprydningen med `auditRetentionDays` kører ved start uden fejl (at den sletter gamle rækker er ikke tjekket), `python -m WebServer audit` og `--help` (kun `audit`).
- Menuen fra task-0007: i siden, punktet til admin-siden skjult for en bruger, `menu.js` og `menu.css` svarer 200, også under `/public/`.
- task-0002's 339 tjek kørt igen efter ændringerne; alle holdt.

Ingen nye kommandoer eller indstillinger.

### Hvad er ikke lavet, og hvorfor
- Tabellerne og migreringerne i `database/core.py` står, som opgaven siger.
- Andre rester af det gamle login, som opgaven ikke nævner, er ikke rørt (se *Uklart*).

### Uklart
- `docs/guide/database.md` beskrev tre af de fjernede funktioner som noget en app kan kalde. Jeg fjernede dem alligevel, fordi kriteriet siger "som intet kalder", og intet i repoet kalder dem. En app i et andet system, der importerer dem fra `WebServer.database`, vil fejle ved import.
- Rester uden for opgavens liste, ikke rettet:
  - `WebServer/core/__init__.py` og `WebServer/__init__.py`: docstringen siger at `core/auth.py` står for "user/session/audit management".
  - `WebServer/page.py`, `inject_js_scripts`: docstringen siger at markøren `data-hj-page="public"` får `auth.js` til ikke at vise loginformularen. Markøren læses stadig af `auth.js`, men der er ingen formular.
  - `WebServer/public/js/TableViewer.js`: kommentarer om loginformularen og et tjek på `password_change_required`, som serveren aldrig sender længere.
  - `WebServer/auth.py`: aliaset `check_auth = resolve_user` ("backwards-compatible name used by WebServer.checkAuth"); `checkAuth` bruger `resolve_user` direkte, og intet bruger aliaset.
  - `HJwebserver.egg-info/` er versionsstyret, selv om `.gitignore` udelukker `*.egg-info/`, og `SOURCES.txt` nævner filer der ikke findes længere.
