# HJwebserver

Et lille Python-rammeværk til interne værktøjer: ruter, statiske filer, JSON,
et databaselag (SQLite, MSSQL, MySQL), login via Authentik foran appen, en
sidemenu, og en TableViewer der viser og redigerer tabeller i en side.
En app skrives som en `main.py` der importerer `WebServer`. `main.py` i roden er
en eksempelapp, ikke en del af rammeværket.

Procesregler står i `AGENTS.md`. Brugerdokumentationen til rammeværket står i `docs/guide/` (se `docs/guide/README.md`).

## Stak

| Del | Hvad |
|---|---|
| Sprog | Python 3.14, i `.venv` i projektroden |
| Webserver | standardbibliotekets `http.server` (`ThreadingHTTPServer`) — ingen webramme |
| Database | MSSQL er den primære (`pyodbc` 5.3, ODBC Driver 18). SQLite indbygget, MySQL via `PyMySQL` |
| Login | Authentik som *forward auth* i Nginx Proxy Manager. Appen har intet eget login; `python-dotenv` læser nøglerne fra `.env` |
| Frontend | ren JavaScript og CSS under `WebServer/public/`, intet byggetrin |

Afhængighederne står i `requirements.txt`.

## Kommandoer

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
.venv\Scripts\python.exe -m WebServer audit
.venv\Scripts\python.exe -m WebServer --help
```

- Første linje kun når `.venv` ikke findes.
- `main.py` starter eksempelappen. CLI'en (`-m WebServer`) indlæser `main:app` og bruger dens database; `--app modul:variabel` vælger en anden app. Den eneste kommando er `audit` (`--user`, `--limit`); brugere og grupper styres i Authentik.
- **Tests, linter og formatter findes ikke endnu.**

## Miljø

`.env` i projektroden, ikke versionsstyret. Nøglerne står i `.env.example`.
`PROXY_SECRET` og `JWT_SECRET` kræves når en app slår `auth=True` til. I udviklingstilstand (`devUser`) kræves kun `JWT_SECRET`.

## Mappestruktur

| Sti | Hvad |
|---|---|
| `WebServer/__init__.py` | `WebServer`-klassen, sat sammen af mixins fra `core/` |
| `WebServer/core/` | Den offentlige flade på `app`: `server.py` (opstart, ruter, TLS, tråde, sikkerhedsheadere), `auth.py` (`settings()`, `checkAuth`, audit), `filehandler.py` (`addPath`), `assets.py` (rammeværkets js og css), `tableviewer.py` (`addTableViewer`), `menu.py` (`app.menu`) |
| `WebServer/auth.py` | Motoren bag Authentik: proxynøglen, brugeren fra `X-authentik-*`, roller fra grupper, formulartoken, audit, `/logout` og `/api/verify` |
| `WebServer/menu.py` | Sidemenuens motor: `MenuItem`, tjek ved start, menuen for én bruger på én side |
| `WebServer/tableviewer.py` | TableViewers motor: spec, filtre, opslag, gem og slet |
| `WebServer/database/` | Kun SQL: `core.py` (forbindelse, skema, migreringer), `auth.py` (AuditLog), `tableviewer.py` |
| `WebServer/WebHandler.py` | Hver forespørgsel: proxynøgle, rute, adgangskontrol, body-parsing, statiske filer |
| `WebServer/FileHandler.py` | Ruten bag hver `addPath` |
| `WebServer/page.py` | Det der sker med hver HTML-side: includes, menuen og rammeværkets scripts |
| `WebServer/helper.py` | `send_json` |
| `WebServer/public/` | Rammeværkets egne js- og css-filer. En app kan overskrive hver af dem med en fil af samme navn i sin egen `public/` |
| `WebServer/__main__.py` | CLI til audit-loggen |
| `docs/guide/` | Brugerdokumentation til rammeværket (engelsk). `SignInForm.md` er planen for et Microsoft-login i appen, som ikke er bygget |
| `docs/` | `README.md` (oversigt over mappen) og kontraktens arbejdsfiler: `BOARD.md`, `decisions/`, `tasks/`, `tests/`, `securities/`, `reviews/`, `debugs/` |
| `main.py`, `public/` | Eksempelappen og dens sider |

**Én funktion, ét modul pr. lag.** Login findes som `core/auth.py` (metoderne på `app`), `auth.py` (motoren) og `database/auth.py` (SQL'en). TableViewer og sidemenuen følger samme deling (`core/menu.py` og `menu.py`). Ny funktionalitet lægges på samme måde.

## Begreber

- **Rammeværk, ikke app.** Det bruges af flere systemer. Ny funktionalitet er en parameter, typisk på `settings()`, og standardværdien bevarer den adfærd der var før. Intet app-specifikt hører i `WebServer/`.
- **`auth=True`** sætter appen bag Authentik. Hvert kald skal bære `PROXY_SECRET` i `X-Proxy-Secret`, ellers får det en nøgen `403` — også statiske filer og offentlige sider. Først derefter læses brugeren fra `X-authentik-*`. Uden bruger er en rute eller side lukket, medmindre den er markeret `public=True`.
- **Roller** kommer fra brugerens grupper i Authentik via `authentikRoles` (`{gruppe: rolle}`); en bruger i ingen af grupperne får den laveste rolle. `roles=[...]` på en rute eller side kræver én af dem. Med `roleHierarchy` betyder det "den rolle eller højere"; uden den, præcis den.
- **Udviklingstilstand:** `devUser` i `settings()` gør alle til én bruger uden proxy og uden Authentik. Kun tilladt når serveren lytter på den lokale maskine.
- **Formulartoken:** `POST`, `PUT` og `DELETE` kræver `X-CSRF-Token`, en HMAC af brugernavnet med `JWT_SECRET`. `auth.js` henter den fra `/api/verify` og sender den selv.
- **Rammeforbud:** med `auth=True` bærer hvert svar `X-Frame-Options: DENY` og en CSP med `frame-ancestors 'none'`, uanset `csp` og `securityHeaders`.
- **Sidemenuen** slås til med `app.menu(items=[MenuItem(...)])`. Hvert punkt peger på en `addPath`-side, og rollerne står kun på siden; menuen skjuler punkter brugeren ikke må åbne. Serveren sætter menuen ind lige efter `<body>` i hver side; `addPath(..., menu=False)` fravælger den.
- **AuditLog** er sikkerhedshændelser (log ud, nægtet adgang, afvist formulartoken). **`tableviewLedger`** er dataændringer via en TableViewer, med gamle og nye værdier. Tabellerne `Users`, `Sessions` og `LoginAttempts` er fra det gamle login; de oprettes og står, men intet bruger dem.
- **Tråde:** serveren kører hver forespørgsel i sin egen tråd som standard (`threaded=True`). Delt tilstand i hukommelsen skal beskyttes med en lås. Det gør rammeværket selv for TableViewer-skrivninger.
- **Migreringer:** nye kolonner på rammeværkets tabeller tilføjes i `_MIGRATIONS` i `database/core.py`, for alle tre databaser, og køres når en app kalder `setDatabase()`.
