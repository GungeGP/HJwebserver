---
nummer: task-0001
titel: Login via Authentik i stedet for appens eget login
status: afsluttet
kilde: interview
oprettet: 2026-11-11
---

# task-0001 — Login via Authentik i stedet for appens eget login

## Hvad og hvorfor
Rammeværket gør det nemt for andre at bygge interne sider med login. Login skal
fremover kun ske med brugerens d1-konto, og det skal klares af Authentik foran
appen (forward auth i proxyen), som beskrevet i kontraktens `## En app bag
Authentik`. Appens eget login — adgangskoder, egne sessioner og Microsoft-login
inde i appen — fjernes. Roller kommer fra brugerens grupper i Authentik.

## Færdig når
- [ ] En app uden `auth=True` opfører sig som i dag: åben, uden tjek af nøgle eller headere.
- [ ] Med `auth=True` afvises ethvert kald uden den rigtige proxynøgle med `401` eller `403` uden indhold — også offentlige sider og statiske filer.
- [ ] Nøglen sammenlignes i konstant tid, og appen nægter at starte når den mangler eller er tom. Beskeden nævner nøglens navn, aldrig en værdi.
- [ ] Nøglen står aldrig i en logudskrift, en fejlbesked eller et svar — heller ikke den der blev sendt ved en afvisning.
- [ ] Authentiks brugerheadere læses først når nøglen er godkendt. Et kald med forfalsket brugernavn og uden nøgle afvises.
- [ ] Sider markeret som offentlige kan ses uden en bruger. Beskyttede sider og ruter kræver en bruger fra Authentik.
- [ ] En brugers rolle bestemmes af dens grupper i Authentik, efter den kobling appen sætter op. Med rangordning af roller gælder "denne rolle eller højere" som i dag. En bruger i ingen koblet gruppe får den laveste rolle.
- [ ] Hvert svar, også afvisninger, forbyder at siden vises i en ramme.
- [ ] Alt der ændrer noget for en logget ind bruger, kræver et token bundet til brugeren. Sider der bruger rammeværkets egne scripts, sender det automatisk, så en app-udvikler ikke skal gøre noget.
- [ ] Log ud sender brugeren til Authentiks log ud.
- [ ] En udviklingstilstand lader appen lokalt opføre sig som om en bestemt bruger med bestemte grupper er logget ind. Appen nægter at starte med den, hvis den ikke kun lytter på den lokale maskine, og skriver tydeligt ved start at den er slået til.
- [ ] Ved start med `auth=True` skriver appen listen over offentlige stier i en form der kan sættes direkte ind i Authentik som stier uden login.
- [ ] Adgangskode-login, lockout, egne sessioner, Microsoft-login i appen og appens egne tokens til scripts findes ikke længere. Det gør kommandolinjens bruger-, rolle-, sessions- og lockout-kommandoer heller ikke. Auditloggen findes stadig.
- [ ] Dokumentationen for rammeværket beskriver kun login via Authentik, herunder hvad der skal sættes i `.env`, og hvad der skal sættes op i Authentik og proxyen. Planen for Microsoft-login i appen står stadig, markeret som ikke i brug.
- [ ] Eksempelappen viser opsætningen med Authentik og opretter ingen bruger med adgangskode.
- [ ] En app-udvikler kan skrive hvert af de seks eksempler under *Sådan ser det ud i en app* præcis som de står, og de virker som beskrevet.
- [ ] Værdier fra `.env` kan læses i `main.py` lige efter at appen er oprettet, før `settings()` kaldes.

## Sådan ser det ud i en app
Godkendt af mennesket som målet. Det er grænsefladen der bygges til.

**1. Uden login, som i dag**
```python
app = WebServer(port=8080)
app.setDatabase(type="mssql", server="localhost", dbName=...)
app.addPath('/', 'public/index.html')
# ingen settings(auth=True): alt er åbent
```

**2. Alt bag login**
```python
app = WebServer(host="0.0.0.0", port=8080)
app.setDatabase(...)
app.settings(auth=True)          # kræver PROXY_SECRET i .env; brugeren kommer fra Authentik

@app.route('GET', '/api/me')
def me(request):
    send_json(request, 200, {"user": request.user})
    # request.user = {"username": "...", "name": "...", "email": "...", "role": "user", "groups": [...]}
```

**3. Nogle sider offentlige, resten bag login**
```python
app.settings(auth=True)
app.addPath('/', 'public/index.html', public=True)
app.addPath('/sager', 'public/sager.html')

@app.route('GET', '/api/aabningstider', public=True)
def aabningstider(request): ...
```
Ved start skriver appen de offentlige stier som regulære udtryk, én pr. linje, klar til Authentiks "stier uden login":
```
[ auth ] Offentlige stier — sæt dem ind i Authentik som "stier uden login":
^/$
^/api/aabningstider$
```

**4. Roller fra AD-grupper**
```python
import os
app = WebServer(host="0.0.0.0", port=8080)   # læser .env, så os.environ virker herefter
app.setDatabase(...)
app.settings(auth=True,
             roleHierarchy=["dev", "admin", "user"],
             authentikRoles={os.environ["GROUP_DEV"]: "dev",
                             os.environ["GROUP_ADMIN"]: "admin"})

@app.route('DELETE', '/api/sag', roles=["admin"])        # admin og dev må
def slet_sag(request): ...

app.addTableViewer('/api/sager', table=..., edit=["admin"], delete=["admin"])
```

**5. Lokal udvikling, uden Authentik**
```python
app = WebServer(port=8080)   # lytter kun på 127.0.0.1
app.settings(auth=True,
             roleHierarchy=["dev", "admin", "user"],
             authentikRoles={os.environ["GROUP_ADMIN"]: "admin"},
             devUser={"username": "test", "groups": [os.environ["GROUP_ADMIN"]]})
```
Ved start: `[ auth ] UDVIKLINGSTILSTAND: alle er "test" (admin)`. Nægter at starte hvis `host` ikke er den lokale maskine.

**6. I siden selv**
```html
<button id="logout">Log ud</button>
<script>
window.addEventListener('hj:ready', e => {
    document.getElementById('navn').textContent = e.detail.user.name;
    if (hjAuth.hasRole('admin')) { document.getElementById('slet').hidden = false; }
});
</script>
```
`fetch('/api/sag', {method: 'DELETE'})` får tokenet sat på af rammeværket.

**`.env` for et system:** `PROXY_SECRET`, `JWT_SECRET`, og appens egne gruppenøgler (fx `GROUP_ADMIN`, `GROUP_DEV`). Gruppenøglerne er appens, ikke rammeværkets — de står ikke i rammeværkets `.env.example`.

## Sådan bygger vi det
- Arbejd på grenen `task-0001-authentik-login`, lavet fra default-branch.
- **`.env` læses når `WebServer(...)` oprettes** (`load_dotenv()` i konstruktøren), ikke først i `settings()`, så eksempel 4 og 5 virker.
- **`request.user`** har `username`, `name`, `email`, `role` og `groups` (listen fra Authentik).
- **Lagdelingen bevares.** Motoren i `WebServer/auth.py` skrives om til: tjek af proxynøglen, læsning af `X-authentik-*`, kobling af grupper til roller, udviklingstilstand, token mod falske formularer. `core/auth.py` beholder `settings()`, `checkAuth`, `audit` og `getAuditLog`. `WebServer/microsoft.py` fjernes.
- **Headerne** fra Authentik: `X-authentik-username`, `X-authentik-groups` (adskilt af `|`), `X-authentik-email`, `X-authentik-name`. Brugernavnet normaliseres som i dag.
- **Proxynøglen** læses fra `.env` under nøglen `PROXY_SECRET` og sendes af proxyen i headeren `X-Proxy-Secret`. Sammenlign med `hmac.compare_digest`.
- **Grupper til roller:** ny parameter på `settings()`, `authentikRoles={"<gruppenavn>": "<rolle>"}`. Gruppenavnene er organisationens egne og læses fra `.env` i appen, ikke fra rammeværket. Med `roleHierarchy` vælges den højeste rolle blandt brugerens grupper; uden den den første match. Den eksisterende rangordning (`has_role`, `describe_roles`, `check_role`, `lowest_role`) genbruges uændret.
- **Token mod falske formularer:** HMAC af brugernavnet med `JWT_SECRET`. `GET /api/verify` returnerer det sammen med brugeren og `roleHierarchy`. `auth.js` lægger det i en header på alle ændrende kald (POST, PUT, DELETE), og `WebHandler` afviser ændrende kald til beskyttede ruter uden gyldigt token.
- **Udviklingstilstand:** ny parameter `devUser={"username": ..., "groups": [...]}`. Kun tilladt når `host` er `127.0.0.1`, `localhost` eller `::1`; ellers nægtes start. Slår tjekket af nøgle og headere fra og bruger den falske bruger.
- **Log ud:** Authentiks faste sti `/outpost.goauthentik.io/sign_out`. `GET /logout` og `hjAuth.logout()` sender dertil.
- **`auth.js`:** loginformularen, skift-adgangskode-formularen og Microsoft-flowet fjernes. Tilbage er `window.currentUser`, `hjAuth.user`, `hjAuth.hasRole`, `hjAuth.logout`, `hj:ready` og tokenet på ændrende kald. Bliver et kald afvist fordi brugeren ikke er logget ind (sjældent bag Authentik), genindlæses siden, så Authentik kan vise sit login.
- **Ruter der fjernes:** `/api/login`, `/api/login/start`, `/api/login-config`, `/api/change-password`, `/api/logout-all`, `/auth/microsoft/callback`. `/api/logout` erstattes af `GET /logout`.
- **`settings()`:** parametrene til adgangskoder, sessioner, lockout, loginformularen, bearer-tokens og Microsoft fjernes. Tilbage er `auth`, `csp`, `securityHeaders`, `trustProxy`, `auditLog`, `auditRetentionDays`, `roleHierarchy`, `authentikRoles` og `devUser`.
- **`.env.example`:** `PROXY_SECRET` tilføjes. `MS_*` fjernes. `JWT_SECRET` bliver, nu til tokenet.
- **`requirements.txt`:** `cryptography` fjernes; den blev kun brugt til Microsoft-login.
- **Dokumentationen:** `docs/auth.md`, `docs/users.md`, `docs/webserver.md`, `docs/frontend.md` og `docs/README.md` rettes. `docs/SignInForm.md` får en status øverst om at planen ikke er i brug, er erstattet af Authentik, og at koden findes i commit `620f265`.
- **Efterprøvning** med HTTP-kald mod egen server, efter kontraktens `## Efterprøvning af en webflade`: uden nøgle, med forkert nøgle, med rigtig nøgle, med forfalsket brugernavn uden nøgle, offentlig og beskyttet side, roller fra grupper, ændrende kald med og uden token, udviklingstilstand på og uden for den lokale maskine.

## Hvad vi ikke rører
- Databaselaget og skemaet. Ubrugte tabeller og kolonner (adgangskoder, sessioner, lockout, Microsoft) bliver stående. Ingen data slettes.
- TableViewer, ud over at den bruger brugeren og rollen fra den nye motor.
- Trådningen, filhåndteringen, rammeværkets øvrige scripts og styles, og sikkerhedsheaderne ud over ramme-forbuddet på afvisninger.
- `AuditLog` og `tableviewLedger`.

## Afhænger af
intet

## Beslutninger
- BESLUTTET: Login kun med d1 via Authentik foran appen (forward auth). Appens eget login og Microsoft-login i appen fjernes — brugerens valg; Microsoft-login i appen blev afvist, men planen bevares i `docs/SignInForm.md`.
- BESLUTTET: Roller kommer fra brugerens grupper i Authentik — én kilde, styret af IT; lokal rollestyring og `--pin` falder bort.
- BESLUTTET: `auth=True` slår beskyttelsen til; uden den er appen åben som i dag. `public=True` virker som i dag — brugerens krav.
- BESLUTTET: Udviklingstilstand med spærre til den lokale maskine — rammeværkets brugere skal kunne afprøve roller lokalt; risikoen ved at slå den til i drift tages af spærren.
- BESLUTTET: Appens egne tokens til scripts fjernes — kontrakten kræver at alle kald går gennem proxyen; scripts bruger en servicekonto i Authentik.
- BESLUTTET: En bruger i ingen koblet gruppe får den laveste rolle — Authentik har allerede afgjort at personen må bruge systemet.
- BESLUTTET: Kommandolinjens bruger-, rolle-, sessions- og lockout-kommandoer fjernes; auditloggen bliver.
- BESLUTTET: Databasen ændres ikke — systemet kører i drift; ubrugte tabeller og kolonner står.
- BESLUTTET: Andre systemer på rammeværket skal stå bag Authentik for at virke; udgivelsen er et brud-nummer.
- BESLUTTET: Grænsefladen i *Sådan ser det ud i en app* er målet — godkendt af mennesket som den måde en app-udvikler skriver det på.
- BESLUTTET: `.env` læses når appen oprettes — så gruppenavne kan læses med `os.environ` i `main.py` før `settings()`.

## Åbne punkter

## Indvendinger

---

## Developers noter

<Alt over denne overskrift ejes af architect. Alt herunder skrives kun af
developer, som aldrig retter i definitionen ovenfor.>

### Hvad er lavet

Gren `task-0001-authentik-login`, fem commits: `edd0a66` (motoren), `fe7f715` (auth.js), `4e7a178` (CLI), `84ebe0b` (eksempelappen), `46500ac` (dokumentation).

Holdt op mod *Færdig når*, punkt for punkt:

1. **Uden `auth=True` som i dag.** `WebHandler._proxy_allowed` og `_authorize` slipper alt igennem når `server.auth` er falsk. Efterprøvet: side, POST, statisk fil uden nøgle giver 200, `auth.js` injiceres ikke, `/api/verify` findes ikke.
2. **Afvisning uden nøgle.** `WebHandler.handle_request` kalder `_proxy_allowed()` som det første. Uden den rigtige `X-Proxy-Secret` svarer den `403` med `Content-Length: 0` (`_reject_bare`). Det gælder alle stier og metoder, også offentlige sider, statiske filer, `/js/auth.js`, `/logout` og ukendte stier. `send_error` er overskrevet, så http.servers egne fejl (501 for HEAD/PATCH/OPTIONS) også bliver til en tom 403 uden nøgle.
3. **Konstant tid og nægtet start.** `WebServer/auth.py: proxy_secret_ok` bruger `hmac.compare_digest`. `configure()` rejser `RuntimeError` når `PROXY_SECRET` mangler, er tom eller kun mellemrum, og når `JWT_SECRET` mangler eller er under 32 bytes. Beskeden nævner kun nøglens navn. Efterprøvet for mangler, tom og blank.
4. **Nøglen skrives ingen steder.** Ingen kode udskriver den. Efter godkendelse slettes headeren fra `request.headers`, så en handler ikke kan komme til at sende den tilbage. Efterprøvet: en handler der returnerer `dict(request.headers)`, ser den ikke, og hverken `PROXY_SECRET` eller `JWT_SECRET` står i serverens udskrift eller i svarene.
5. **Headerne læses først efter nøglen.** `resolve_user` kaldes kun fra `_authorize` og `checkAuth`, og begge kører efter `_proxy_allowed`. Efterprøvet: forfalsket `X-authentik-username` uden nøgle, og med forkert nøgle, giver en tom 403 på alle prøvede stier.
6. **Offentlige og beskyttede sider.** `public=True` virker som før. Uden bruger fra Authentik svarer en beskyttet rute `401` med JSON, en side `401` med kort HTML, og en statisk fil `401`. Siden-bag-loginformularen er fjernet sammen med `login_shell`.
7. **Roller fra grupper.** Ny parameter `authentikRoles` på `settings()`. `role_for_groups()` vælger den højeste rolle med `roleHierarchy` og ellers første match. Ingen match giver `lowest_role()`. Rollerne i `authentikRoles` tjekkes med `check_role`. `has_role`, `describe_roles`, `check_role` og `lowest_role` er uændrede. Efterprøvet: admin+dev giver dev, ingen koblet gruppe giver user, dev må `roles=["admin"]`, user får 403. TableViewers `edit=`/`delete=` virker med rollerne.
8. **Rammeforbud.** Den tomme 403 sender altid `Content-Security-Policy: frame-ancestors 'none'` og `X-Frame-Options: DENY`, uanset `csp`/`securityHeaders`. Andre svar har dem som før via standard-CSP'en. Efterprøvet på afvisninger, 401 og en offentlig side.
9. **Token mod falske formularer.** `form_token()` er HMAC-SHA256 af brugernavnet med `JWT_SECRET`. `GET /api/verify` returnerer det som `csrfToken` sammen med `user` og `roleHierarchy`. `_authorize` afviser POST, PUT, PATCH og DELETE til beskyttede ruter uden gyldigt `X-CSRF-Token` med `403` og auditter `form_token_rejected`. `auth.js` sætter headeren på alle ændrende `fetch()` til samme origin, så TableViewer og kalenderen sender den uden ændringer. Efterprøvet: uden token 403, med en anden brugers token 403, med eget token 200. Det gælder også TableViewers PUT og delete.
10. **Log ud.** `GET /logout` (offentlig) auditter `logout` og sender 302 til `/outpost.goauthentik.io/sign_out`. `hjAuth.logout()` og `<button id="logout">` går til `/logout`.
11. **Udviklingstilstand.** Ny parameter `devUser` på `settings()`. Den er kun tilladt med `host` `127.0.0.1`, `localhost` eller `::1`, ellers `RuntimeError` i `settings()`. Ved start skrives `[ auth ] UDVIKLINGSTILSTAND: alle er "test" (admin)`. Nøgle og headere tjekkes ikke, og formulartokenet tjekkes stadig. Efterprøvet på `0.0.0.0`, en IP, tom og et værtsnavn (nægtet) og på de tre lokale (tilladt).
12. **Offentlige stier ved start.** `on_server_start` skriver `[ auth ] Offentlige stier — sæt dem ind i Authentik som "stier uden login":` og én regex pr. linje (`public_path_patterns`). Appens egne kommer først, præcis som i eksempel 3 (`^/$`, `^/api/aabningstider$`). Bagefter kommer rammeværkets offentlige stier (scripts, styles, `/logout`), fx `^(/public)?/js/auth\.js$`. Se *Uklart* 1.
13. **Fjernet.** Adgangskoder, lockout og `_login_lock`, sessioner, cookies, bearer-tokens, `createAuth`, loginformularen og `login_shell`, `WebServer/microsoft.py`. Det gælder også metoderne `createUser`, `setPassword`, `setRole`, `disableUser`, `enableUser`, `deleteUser`, `getUser`, `listUsers`, `revokeSessions`, `unlock`, `getLockouts` og `getSessions`. Ruterne `/api/login`, `/api/login/start`, `/api/login-config`, `/api/change-password`, `/api/logout-all`, `/api/logout` og `/auth/microsoft/callback` er væk (efterprøvet: 404). I CLI'en (`WebServer/__main__.py`) er kun `audit` tilbage. `audit`, `getAuditLog` og `auditRetentionDays` virker. TableViewer-låsen og trådningen er urørt. `core/auth.py` beholder `settings`, `checkAuth`, `audit` og `getAuditLog`.
14. **Dokumentation.** `docs/auth.md` er skrevet om: `.env`, Authentik, proxyen (de linjer appen afhænger af), `request.user`, roller, token, log ud, udviklingstilstand, offentlige stier og audit. `docs/users.md` handler nu om roller og `audit`-kommandoen. `docs/webserver.md`, `docs/frontend.md` og `docs/README.md` er rettet. `docs/SignInForm.md` har fået status øverst med henvisning til `620f265`. Desuden er `docs/routes.md`, `docs/tableviewer.md` (afsnittet om tabellen bag loginformularen) og `docs/database.md` (de gamle tabeller, `app.createUser`) rettet, fordi de beskrev det fjernede login.
15. **Eksempelappen.** `main.py` bruger `host="0.0.0.0"`, `settings(auth=True, roleHierarchy=["admin", "user"], authentikRoles={os.environ["GROUP_ADMIN"]: "admin"})` og har `devUser` som kommentar. `createUser("admin", ...)` er fjernet. Efterprøvet ved at indlæse `main` mod en midlertidig SQLite i stedet for MSSQL.
16. **De seks eksempler.** Skrevet ordret i en testapp i scratchpad og kørt over HTTP. Eksempel 1–5 virker som beskrevet. To afvigelser: eksempel 2–4 kørte på `127.0.0.1` i stedet for `0.0.0.0`, for ikke at åbne firewallen, og det ændrer ikke adfærden. Eksempel 6 er kun efterprøvet så langt det kan uden browser, se *Hvad er ikke lavet*.
17. **`.env` i konstruktøren.** `ServerMixin.__init__` kalder `load_dotenv()` som det første. Efterprøvet med en udskiftet `load_dotenv`: værdien findes efter `WebServer(...)` og ikke før.

Andre filer: `.env.example` har fået `PROXY_SECRET`, `MS_*` er fjernet, og `JWT_SECRET` har ny forklaring. Fra `requirements.txt` er `cryptography` fjernet. I `core/server.py` sætter `useHttps` ikke længere cookieflaget. I `core/assets.py` er asset-ruterne mærket `_hj_framework`, så de kan stå efter appens egne stier.

**Til README (architect):**
- Nye indstillinger på `settings()`: `authentikRoles`, `devUser`.
- Fjernede indstillinger: `jwtSecret`, `tokenLifetimeHours`, `secureCookie`, `bearerTokens`, `maxLoginAttempts`, `lockoutMinutes`, `minPasswordLength`, `rememberMeDays`, `idleTimeoutMinutes`, `loginTitle`, `loginMessage`, `loginLogo`, `ssoDomains`, `ssoOnly`, `localAccounts` og alle `microsoft*`.
- Ny nøgle i `.env`: `PROXY_SECRET`. `JWT_SECRET` bliver, nu til tokenet. `MS_*` er væk. Eksempelappen kræver desuden sin egen `GROUP_ADMIN`.
- CLI: kun `python -m WebServer audit [--user NAME] [--limit N]`. Kommandoerne i `CLAUDE.md` (`listusers`) findes ikke længere.
- Ny header fra proxyen: `X-Proxy-Secret`. Ny header fra siderne: `X-CSRF-Token`. Ny rute: `GET /logout`. `GET /api/verify` har fået feltet `csrfToken`.

Efterprøvning: 101 HTTP-kontroller mod egne servere (SQLite i scratchpad) plus 16 direkte kontroller af `configure`, rollevalg og opstartstjek. Alle bestod i sidste kørsel. `auth.js` er syntakstjekket med `node --check`. Der er ingen linter i projektet, og alle Python-filer er kompileret med `py_compile`. Alle servere jeg startede, er stoppet.

### Hvad er ikke lavet, og hvorfor

- **Eksempel 6 i en browser er ikke efterprøvet.** At `hj:ready` kommer med navnet, at `hjAuth.hasRole` viser knappen, at `fetch(..., {method: 'DELETE'})` får tokenet på, og at siden genindlæses ved 401, kræver en browser. Agenter må ikke starte en. På serversiden er alt bekræftet: siden får `auth.js` injiceret, `/api/verify` giver bruger, `roleHierarchy` og token, og DELETE med token giver 200. Det skal prøves af architect eller mennesket.
- **Mod en rigtig Authentik og Nginx Proxy Manager er intet efterprøvet.** Headerne er sat i hånden. Det gælder især æøå i `X-authentik-name`. Jeg antager at de kommer som UTF-8 (Go sender dem rå), og `_header()` afkoder dem igen fra latin-1. Det er prøvet med UTF-8-bytes, ikke med Authentik.
- **`/logout` i udviklingstilstand** sender til Authentiks sign-out, som ikke findes lokalt (404). Det er bygget som opgaven siger, og står i `docs/auth.md`.
- **Hele suiten:** findes ikke. Opgaven beder ikke om en.

### Uklart

1. **De offentlige stier skrives med rammeværkets stier bagefter.** Eksempel 3 viser kun appens to linjer. En offentlig side henter dog `auth.js`, `webserver.js` m.fl. Står de ikke i Authentiks liste, sender Authentik dem til login for en der ikke er logget ind, og siden virker ikke. Jeg skriver derfor appens egne først, præcis som i eksemplet, og derefter rammeværkets 9 scripts og styles og `^/logout$`. Hver fil bliver én linje med `^(/public)?`. Skal rammeværkets linjer ud, eller stå under en egen overskrift?
2. **`/logout` er offentlig.** Så virker log ud også når Authentik-sessionen er udløbet, men `^/logout$` kommer med i listen, og auditten får kun brugernavnet hvis Authentik sender headerne på en sti uden login. Det alternative er en beskyttet `/logout`: altid brugernavn i auditten, men en udløbet bruger ser Authentiks login før log ud.
3. **"Første match" uden `roleHierarchy`** er tolket som den første gruppe i den rækkefølge `authentikRoles` står i, ikke rækkefølgen i Authentiks header. Begrundelse: app-udvikleren styrer den ene, ikke den anden.
4. **`PROXY_SECRET` kræves ikke i udviklingstilstand**, da nøglen ikke tjekkes der. `JWT_SECRET` kræves stadig, fordi tokenet også tjekkes lokalt.
5. **Rammeforbuddet på almindelige svar.** Afvisningerne har det altid. Almindelige svar har det kun via standard-CSP'en og `securityHeaders=True`, som før. *Hvad vi ikke rører* undtager sikkerhedsheaderne ud over afvisningerne. En app med `securityHeaders=False` eller en egen `csp` uden `frame-ancestors` kan derfor vises i en ramme. Skal `auth=True` tvinge forbuddet på alle svar?
6. **Navnene `X-CSRF-Token` (header) og `csrfToken` (felt i `/api/verify`)** stod ikke i opgaven. Jeg har valgt dem.
7. **Eksempelappen** lytter på `0.0.0.0` bag Authentik. Kørt lokalt uden proxy giver hver forespørgsel derfor 403, og den kræver `GROUP_ADMIN` i `.env` (ellers `KeyError`). Lokal brug står som kommentar (`devUser`). Skal eksempelappen hellere starte i udviklingstilstand?
8. **Fund uden for opgaven** (ikke rettet):
   - `PyJWT` bruges ikke længere. Tokenet er bygget med `hmac`, og opgaven nævner kun `cryptography` til fjernelse.
   - `FileHandler.py` sætter stadig `_hj_page`, som intet læser. Filhåndteringen var uden for opgaven.
   - `WebServer/public/css/auth.css` og ruten `/css/auth.css` er stadig der, men loginformularen de stylede, er væk.
   - `WebServer/database/auth.py` har ubrugte funktioner og en docstring der nævner `createUser`/`setRole`. Databaselaget var uden for opgaven.
   - `CLAUDE.md` beskriver stadig `microsoft.py`, `cryptography`, sessioner, Microsoft-login og `listusers`.
   - `load_dotenv()` uden argumenter leder efter `.env` opad fra rammeværkets egen mappe, ikke fra appens. Det virker når rammeværket eller dets `.venv` ligger i projektmappen, men ikke ved en global installation. Sådan var det også før.
   - git melder ved hver commit `failed to delete '.git/worktrees/stoic-chatelet-052376': Permission denied`. Det er en gammel worktree i `.claude/worktrees/`.
