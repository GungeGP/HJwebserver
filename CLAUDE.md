# HJwebserver

Et lille Python-rammeværk til interne værktøjer: ruter, statiske filer, JSON,
et databaselag (SQLite, MSSQL, MySQL), login med sessioner og valgfrit
Microsoft-login, og en TableViewer der viser og redigerer tabeller i en side.
En app skrives som en `main.py` der importerer `WebServer`. `main.py` i roden er
en eksempelapp, ikke en del af rammeværket.

Procesregler står i `AGENTS.md`. Brugerdokumentationen til rammeværket står i `docs/` (se `docs/README.md`).

## Stak

| Del | Hvad |
|---|---|
| Sprog | Python 3.14, i `.venv` i projektroden |
| Webserver | standardbibliotekets `http.server` (`ThreadingHTTPServer`) — ingen webramme |
| Database | MSSQL er den primære (`pyodbc` 5.3, ODBC Driver 18). SQLite indbygget, MySQL via `PyMySQL` |
| Login | `PyJWT` 2.14 (sessionstokens), `cryptography` 44 (Microsofts tokensignaturer), `python-dotenv` |
| Frontend | ren JavaScript og CSS under `WebServer/public/`, intet byggetrin |

Afhængighederne står i `requirements.txt`.

## Kommandoer

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
.venv\Scripts\python.exe -m WebServer listusers
.venv\Scripts\python.exe -m WebServer --help
```

- Første linje kun når `.venv` ikke findes.
- `main.py` starter eksempelappen. CLI'en (`-m WebServer`) indlæser `main:app` og bruger dens database; `--app modul:variabel` vælger en anden app.
- **Tests, linter og formatter findes ikke endnu.**

## Miljø

`.env` i projektroden, ikke versionsstyret. Nøglerne står i `.env.example`.
`JWT_SECRET` kræves når en app slår login til; `MS_*` kun når den slår Microsoft-login til.

## Mappestruktur

| Sti | Hvad |
|---|---|
| `WebServer/__init__.py` | `WebServer`-klassen, sat sammen af mixins fra `core/` |
| `WebServer/core/` | Den offentlige flade på `app`: `server.py` (opstart, ruter, TLS, tråde), `auth.py` (`settings()`, brugerstyring), `filehandler.py` (`addPath`), `assets.py`, `tableviewer.py` (`addTableViewer`) |
| `WebServer/auth.py` | Loginmotoren: hashing, sessioner, lockout, roller, audit, login-ruterne |
| `WebServer/microsoft.py` | Microsoft-login: OpenID Connect, Microsoft Graph, kobling af brugere |
| `WebServer/tableviewer.py` | TableViewers motor: spec, filtre, opslag, gem og slet |
| `WebServer/database/` | Kun SQL: `core.py` (forbindelse, skema, migreringer), `auth.py`, `tableviewer.py` |
| `WebServer/WebHandler.py` | Hver forespørgsel: rute, adgangskontrol, body-parsing, statiske filer |
| `WebServer/public/` | Rammeværkets egne js- og css-filer. En app kan overskrive hver af dem med en fil af samme navn i sin egen `public/` |
| `WebServer/__main__.py` | CLI til brugere, roller, sessioner, lockouts og audit |
| `docs/` | Brugerdokumentation (engelsk), designdokumentet `SignInForm.md`, og kontraktens mapper |
| `main.py`, `public/` | Eksempelappen og dens sider |

**Én funktion, ét modul pr. lag.** Login findes som `core/auth.py` (metoderne på `app`), `auth.py` (motoren) og `database/auth.py` (SQL'en). TableViewer følger samme deling. Ny funktionalitet lægges på samme måde.

## Begreber

- **Rammeværk, ikke app.** Det bruges af flere systemer. Ny funktionalitet er en parameter, typisk på `settings()`, og standardværdien bevarer den adfærd der var før. Intet app-specifikt hører i `WebServer/`.
- **`auth=True`** lukker alt bag login. Undtagelser markeres `public=True` på ruten eller siden.
- **Roller** er en streng på brugeren (`Users.Role`). `roles=[...]` på en rute kræver én af dem. Med `roleHierarchy` betyder det "den rolle eller højere"; uden den, præcis den.
- **Session** = et signeret JWT plus en række i `Sessions`. Rækken gør at en session kan tilbagekaldes.
- **Microsoft-login** er slået fra, indtil en app sætter `ssoDomains`. Formularen spørger så om navn først, og serveren afgør i `POST /api/login/start` om navnet går til Microsoft eller får et adgangskodefelt. `ssoOnly` og `localAccounts` styrer om adgangskoder er tilladt. En Microsoft-bruger er en række med `ExternalId` (Entras `oid`) og uden adgangskode.
- **AuditLog** er sikkerhedshændelser (login, brugerændringer, nægtet adgang). **`tableviewLedger`** er dataændringer via en TableViewer, med gamle og nye værdier.
- **Tråde:** serveren kører hver forespørgsel i sin egen tråd som standard (`threaded=True`). Delt tilstand i hukommelsen skal beskyttes med en lås. Det gør rammeværket selv for lockout og TableViewer-skrivninger.
- **Migreringer:** nye kolonner på rammeværkets tabeller tilføjes i `_MIGRATIONS` i `database/core.py`, for alle tre databaser, og køres når en app kalder `setDatabase()`.
