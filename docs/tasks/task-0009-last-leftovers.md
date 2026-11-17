---
nummer: task-0009
titel: Ryd de sidste rester af det gamle login og den forældede pakkeinfo
status: afsluttet
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
Arbejdet ligger direkte på `main`, uden ny gren og uden commit, som mennesket har besluttet. Kun sletningen af `HJwebserver.egg-info` er staged.

- **Ingen beskrivelser af bruger- og sessionsstyring, loginformular eller adgangskodeskift**
  - `WebServer/__init__.py`: i klassens docstring står `AuthMixin` nu som "settings(auth=...), checkAuth(), audit" i stedet for "user/session/audit management".
  - `WebServer/core/__init__.py`: tilsvarende for `auth.py` i pakkens docstring.
  - `WebServer/page.py`, `inject_js_scripts`: markøren `data-hj-page="public"` "tells auth.js never to reload this page on a 401". Selve markøren er urørt og læses stadig af `auth.js`.
  - `WebServer/public/js/TableViewer.js`: de to kommentarer om loginformularen siger nu at `auth.js` genindlæser siden, så Authentik kan vise sit login, og at skelettet bliver stående efter en 401.
- **TableViewer tjekker ikke længere for adgangskodeskift**: `WebServer/public/js/TableViewer.js` siger nu `if (res.status === 401) return this;`, og tjekket på `password_change_required` er væk. Serveren sender aldrig det svar (ingen forekomster i `WebServer/`).
- **Aliaset `check_auth` er fjernet**: `check_auth = resolve_user` og kommentaren over det er slettet fra `WebServer/auth.py`. Intet i repoet brugte det; `checkAuth` kalder `resolve_user` direkte.
- **`HJwebserver.egg-info` er ikke længere versionsstyret**: `git rm -r --cached HJwebserver.egg-info` er kørt, og de fire filer står staged som slettede. Mappen ligger stadig på disken, og `*.egg-info/` i `.gitignore` udelukker den nu.
- **Alt virker uændret**, efterprøvet med HTTP-kald mod en egen server: en lille app med `auth=True`, `roleHierarchy`, `authentikRoles`, en TableViewer med `edit`/`delete=["admin"]`, en sidemenu og en offentlig side. Den kørte på SQLite i en midlertidig mappe, og serveren er stoppet igen. Alle 25 kontroller holdt:
  - Proxynøglen: uden `X-Proxy-Secret` fik både en lukket og en offentlig side `403`.
  - Login via Authentik: uden bruger gav `/api/verify` `401`. Med `X-authentik-*` gav den brugeren, rollen og formulartokenet. `app.checkAuth()` på en offentlig rute gav `None` uden bruger og brugeren med.
  - Roller: en bruger i admin-gruppen fik `admin`, andre fik `user`. En side med `roles=["admin"]` gav `403` til `user` og `200` til `admin`.
  - Formulartoken: `PUT` uden token gav `403`, og det gjorde `PUT` med en anden brugers token også. Med det rigtige token gik `PUT` og sletning igennem som admin.
  - Audit: `access_denied`, `form_token_rejected` og `logout` stod i `AuditLog`.
  - TableViewer: læsning virkede, `canDelete` fulgte rollen, og redigering og sletning ændrede tabellen. Begge ændringer stod i `tableviewLedger` med gamle og nye værdier.
  - Sidemenuen: den blev sat ind i siden, og punktet til admin-siden var skjult for `user`.
  - Rammeforbud: svarene bar `X-Frame-Options: DENY` og `frame-ancestors 'none'`.
  - Den offentlige side bar `data-hj-page="public"`, og den leverede `TableViewer.js` var den rettede.
- `node --check WebServer/public/js/TableViewer.js` gik igennem, og `py_compile` gik igennem på de fire ændrede Python-filer. Der findes ingen tests og ingen linter i projektet.
- Ingen nye kommandoer eller indstillinger. Intet til README.

### Hvad er ikke lavet, og hvorfor
intet

### Uklart
- Uden for opgavens filliste, ikke rettet:
  - `WebServer/database/core.py`, `_MIGRATIONS`: kommentaren `# Microsoft login: ExternalId is the account's Entra object id (oid).` står over en kolonne på den gamle `Users`-tabel. Den nævner hverken bruger- eller sessionsstyring, loginformularen eller adgangskodeskift, men den beskriver et login der ikke er bygget (`docs/guide/SignInForm.md`). Tabellen oprettes stadig, så kolonnen og migreringen er rigtige; kun ordlyden kan vildlede.
  - Andre steder der nævner login eller sessioner, er korrekte og står urørt: `auth.js` ("there is no login form here"), `__main__.py` ("there are no user, role, session or lockout commands"), `core/server.py` og `database/auth.py`, der siger at `Users` og `Sessions` stadig oprettes.
- `WebServer/core/__pycache__/users.cpython-314.pyc` ligger på disken fra et modul der ikke findes længere. Den er ikke versionsstyret, og Python indlæser den ikke uden kildefilen. Den gør intet, men dukker op når man søger i mappen. Ikke rørt.
