---
nummer: task-0007
titel: Sidemenu som app-udvikleren slår til i main.py
status: afsluttet
kilde: interview
oprettet: 2026-11-11
---

# task-0007 — Sidemenu som app-udvikleren slår til i main.py

## Hvad og hvorfor
Apps bygget på rammeværket laver i dag deres egen navigation i hver side.
Rammeværket skal kunne give en færdig sidemenu i venstre side: en titel, punkter
med beskrivelse og tal, underpunkter, en Admin-knap og "Logget ind som …", hvor
punkter brugeren ikke må åbne, er skjult. Menuen slås til med ét kald i
`main.py`. Den kan også bruges uden rammeværkets tegning, og uden kaldet er alt
som i dag. Forlægget er menneskets skærmbilleder: menuen udfoldet og klappet
sammen.

## Færdig når
- [ ] Uden `app.menu(...)` er alt som i dag.
- [ ] Med `app.menu(items=[...])` har alle sider en menu i venstre side, og indholdet står til højre for den. En side registreret med `menu=False` har ingen menu.
- [ ] Titlen står øverst, når den er sat. Uden titel står der ingen overskrift.
- [ ] Hvert punkt viser sin titel og, når den er sat, en beskrivelse på linjen under.
- [ ] Et punkt med en tælleradresse viser tallet fra den adresse, hentet efter at siden er vist. Svarer adressen ikke, eller med noget der ikke er et tal, vises intet tal, og siden virker som før.
- [ ] Et punkt kan have underpunkter. Et klik på overpunktet åbner dets side. En pil klapper underpunkterne ud og ind. De står åbne, når man er på overpunktets side eller et af underpunkternes.
- [ ] Punktet for den side man står på, er fremhævet.
- [ ] Et punkt hvis side brugeren ikke må åbne, er skjult. Er punktet sat til `denied="disable"`, står det nedtonet og kan ikke klikkes.
- [ ] Menuen kan klappes sammen til en smal udgave og ud igen. Den smalle udgave viser punkternes korte navn, eller de første tegn af titlen. Valget huskes i browseren mellem sider.
- [ ] Nederst står en Admin-knap under "Kun for administratorer". Den vises kun for rollen `admin` (og højere med `roleHierarchy`) og fører til `/admin`. Har appen ikke selv en side på `/admin`, viser rammeværket en tom side med menuen dér. `admin=False` fjerner knappen og den tomme side.
- [ ] Findes rollen `admin` ikke i appens `roleHierarchy`, og er `admin` ikke sat til `False`, nægter appen at starte med en besked der siger hvad der skal gøres. Uden `auth=True` vises ingen Admin-knap.
- [ ] "Logget ind som <rolle>" står nederst som standard. `showUser=False` fjerner linjen. Uden `auth=True` står den ikke.
- [ ] Med `sidebar=False` tegnes ingen menu, men siden kan læse de punkter brugeren må se, med titel, adresse, beskrivelse, kort navn, tælleradresse, underpunkter og om punktet er det aktive.
- [ ] Peger et menupunkt på en adresse ingen side er registreret på, nægter appen at starte og nævner adressen.
- [ ] Et klik i menuen er et almindeligt sideskift. Sidernes egne scripts, også TableViewer og kalenderen, virker uændret.
- [ ] Menuen ligner skærmbillederne som standard. En `public/css/menu.css` i appen erstatter rammeværkets helt, som med de andre stylesheets.
- [ ] Titler, beskrivelser og korte navne kan ikke indsætte HTML i siden.
- [ ] Dokumentationen beskriver menuen med eksemplerne nedenfor.

## Sådan ser det ud i en app
Godkendt af mennesket i interviewet.

**Sider med `addPath` som i dag; menuen peger på dem**
```python
from WebServer import WebServer, MenuItem

app.addPath('/p109', 'public/p109.html')
app.addPath('/p110', 'public/p110.html')
app.addPath('/stamdata', 'public/stamdata.html')
app.addPath('/stamdata/tilbud', 'public/tilbud.html')
app.addPath('/stamdata/kommuner', 'public/kommuner.html', roles=["admin"])

@app.route('GET', '/api/p109/antal')
def antal_109(request):
    send_json(request, 200, 12)

app.menu(title="Ophold", items=[
    MenuItem("§ 109", "/p109", short="§109", desc="Ophold på kvindekrisecenter", count="/api/p109/antal"),
    MenuItem("§ 110", "/p110", short="§110", desc="Ophold på forsorgshjem og ...", count="/api/p110/antal"),
    MenuItem("Stamdata", "/stamdata", short="Data", items=[
        MenuItem("Tilbud", "/stamdata/tilbud"),
        MenuItem("Kommuner", "/stamdata/kommuner"),      # skjules for alle under admin: siden kræver admin
    ]),
])
```

**Valgmuligheder**
```python
app.menu(items=[...])                         # ingen titel øverst
app.menu(items=[...], showUser=False)         # ingen "Logget ind som"
app.menu(items=[...], admin=False)            # ingen Admin-knap og ingen tom /admin
MenuItem("Kommuner", "/stamdata/kommuner", denied="disable")   # nedtonet i stedet for skjult
app.addPath('/', 'public/forside.html', public=True, menu=False)  # en side uden menu
app.addPath('/admin', 'public/admin.html', roles=["admin"])       # egen admin-side i stedet for den tomme
```

**Egen navigation med rammeværkets punkter**
```python
app.menu(sidebar=False, items=[...])
```
```html
<nav id="min-nav"></nav>
<script>
window.addEventListener('hj:ready', () => {
    for (const item of hjMenu.items) {      // kun de punkter brugeren må se
        document.getElementById('min-nav').insertAdjacentHTML('beforeend',
            `<a href="${item.url}">${item.title}</a>`);
    }
});
</script>
```

**Ingen menu:** man kalder ikke `app.menu`.

## Sådan bygger vi det
- Der laves **ingen ny gren**; arbejd på `main`, som mennesket har bedt om for nu.
- **Lagdelingen:** `WebServer/core/menu.py` (`MenuMixin` med `menu()`) til `WebServer`-klassen, `WebServer/menu.py` (motoren: tjek af punkterne, punkterne for én bruger og én side), `MenuItem` eksporteres fra `WebServer`. Ingen database.
- **`menu=False` på `addPath`** markerer siden som uden menu. Ingen anden ændring af `addPath`.
- **Serveren sætter menuen ind** i hver side, i samme trin hvor rammeværkets scripts sættes ind (`page.py`): lige efter `<body>`, med punkterne beregnet for `request.user` og den side der vises. Punkterne lægges også som JSON i siden, så `menu.js` og `hjMenu.items` læser dem derfra.
- **Synlighed:** et punkt vises når `has_role(brugerens rolle, sidens roller)` er sandt, med sidens roller hentet fra rutetabellen for punktets adresse. Uden `auth=True` vises alle punkter.
- **`public/js/menu.js` og `public/css/menu.css`** i rammeværket. Scriptet indsættes kun når `app.menu` er kaldt (samme mekanisme som TableViewer). Det klarer sammenklapning (gemt i `localStorage`), pilene ved underpunkter og hentning af tal (`fetch` af adressen; et JSON-tal).
- **Tom admin-side:** rammeværket registrerer `GET /admin` med `roles=["admin"]`, men kun hvis appen ikke selv har en side dér, og kun med `admin` slået til.
- **Tjek ved start:** hver menuadresse skal findes i rutetabellen, og `admin` skal findes i `roleHierarchy` når den er sat og `admin` ikke er `False`. Fejl stopper starten med en besked.
- **Udseende:** som skærmbillederne. Mørk grøn for det aktive punkt, orange Admin-knap, tallet i en lille boks til højre, `«`/`»` til at klappe sammen.
- **Dokumentation:** en ny side i dokumentationen om menuen med eksemplerne ovenfor, og et link fra siden om frontend. Ligger dokumentationen i `docs/guide/` når opgaven bygges, kommer siden dér.
- **Efterprøvning:** HTTP-kald efter kontraktens `## Efterprøvning af en webflade`: menuen i HTML'en, skjulte og nedtonede punkter for forskellige roller, aktivt punkt, `menu=False`, den tomme `/admin` og en apps egen, start der nægtes ved forkert adresse og manglende `admin`-rolle, `sidebar=False`. Udseende, sammenklapning og tal i browseren efterprøves af architect.

## Hvad vi ikke rører
- Login, roller og sikkerhedsheadere.
- TableViewer, kalenderen, Dialog og `webserver.js`.
- `addPath` ud over den nye `menu=False`.

## Afhænger af
task-0001 — rollerne og brugeren kommer derfra, og dens kode skal være på `main`.

## Beslutninger
- BESLUTTET: Menuen slås til med `app.menu(...)`, og punkterne defineres i den — menneskets krav.
- BESLUTTET: Menupunkter peger på sider lavet med `addPath`; siderne laves ikke af menuen — én måde at lave en side på. At lade menupunkter lave siderne blev afvist.
- BESLUTTET: Roller sættes kun på siden; menuen skjuler selv punkter brugeren ikke må åbne.
- BESLUTTET: Almindelige sideskift, hvor serveren sætter menuen ind i hver side. At skifte kun indholdet med JavaScript blev afvist: sidernes scripts skulle så startes forfra. Mennesket: "lad os prøve det".
- BESLUTTET: `count=` peger på en adresse der svarer med tallet. En Python-funktion direkte i menuen blev afvist: den ville køre ved hver sideindlæsning.
- BESLUTTET: Admin-knappen er med som standard og fører til en tom side, som appens egen `/admin`-side erstatter. Ingen indbyggede admin-værktøjer — menneskets valg.
- BESLUTTET: `sidebar=False` er med fra start.
- BESLUTTET: Alle sider får menuen, når den er slået til; `menu=False` på `addPath` fravælger den.
- BESLUTTET: Punkter brugeren ikke må åbne, skjules; `denied="disable"` viser dem nedtonet.
- BESLUTTET: "Logget ind som" viser rollen, som på menneskets skærmbillede.

## Åbne punkter

## Indvendinger

---

## Developers noter

<Alt over denne overskrift ejes af architect. Alt herunder skrives kun af
developer, som aldrig retter i definitionen ovenfor.>

### Hvad er lavet

Bygget på `main` uden commits, jf. beslutningsloggen. Alt ligger i arbejdstræet.

**Filer**

- `WebServer/menu.py` (ny): motoren. `MenuItem(title, url, short=None, desc=None, count=None, items=None, denied="hide")`, og `Menu` med tjekket ved start (`check`), punkterne for én bruger og én side (`items_for`) og den markup der sættes ind (`render`). Al tekst escapes med `html.escape`. JSON'en escaper `<`, `>` og `&` som `\u003c`, `\u003e` og `\u0026`.
- `WebServer/core/menu.py` (ny): `MenuMixin` med `menu(items, title=None, showUser=True, admin=True, sidebar=True)`, `_menu_on_start()` (tjek og tom `/admin`) og `add_menu(content, request)`. `menu()` registrerer også ruterne `/js/menu.js` og `/css/menu.css`. Det sker først dér, så en app uden menu hverken får nye ruter eller nye offentlige stier til Authentik.
- `WebServer/__init__.py`: `MenuMixin` er sat på `WebServer`, og `MenuItem` eksporteres (`from WebServer import WebServer, MenuItem`).
- `WebServer/page.py`: ny `inject_menu(content, markup)` sætter markup ind lige efter `<body ...>`. En fil uden `<body>` (en partial) røres ikke.
- `WebServer/FileHandler.py` og `WebServer/core/filehandler.py`: `addPath(..., menu=True)`. `menu=False` udelader menuen. Ingen anden ændring af `addPath`.
- `WebServer/WebHandler.py`: HTML-filer der serveres direkte fra `public/`, får også menuen.
- `WebServer/core/server.py`: `start()` kalder `_menu_on_start()` før auth-tjekkene, og serveren får `add_menu`.
- `WebServer/core/assets.py`: `menu.js` står i `_CONDITIONAL_ASSETS` (kun når `app.menu` er kaldt), og `/public/js/menu.js` og `/public/css/menu.css` er tilføjet som aliaser.
- `WebServer/public/js/menu.js` (ny): `window.hjMenu.items`, sammenklapning (`localStorage`, nøglen `hj:menu-collapsed`), pilene og tallene. Tallene hentes efter `load`, og kun et endeligt JSON-tal vises.
- `WebServer/public/css/menu.css` (ny): udseendet. Aktivt punkt i mørk grøn `#00563B` (samme grøn som `auth.css`), orange Admin-knap, tallet i en lille boks til højre for punktet, `«`/`»` øverst og korte navne i den smalle udgave.
- `docs/guide/menu.md` (ny): siden om menuen, med alle eksemplerne fra opgaven.
- `docs/guide/frontend.md`: `menu.js` står i listen over indsatte scripts, `menu.css` er nævnt, og der er et nyt afsnit "Side menu" med link.
- `docs/guide/webserver.md`: `menu=` er med i `addPath`-tabellen, og der er et nyt afsnit om `app.menu(...)`.
- `docs/guide/README.md`: en ny række, "Side menu", i sidetabellen.

**Holdt op mod Færdig når.** Efterprøvet med HTTP-kald mod en testapp i udviklingstilstand og i proxy-tilstand, på SQLite i en midlertidig mappe. 92 påstande holdt.

| Kriterium | Efterprøvet |
|---|---|
| Uden `app.menu` er alt som i dag | Samme app er kørt mod `HEAD` (udtrukket med `git archive`) og mod arbejdstræet, med og uden `auth=True`. Rutetabel, offentlige stier og sidernes bytes var identiske. Ingen `menu.js`, ingen `/admin`. |
| Menu på alle sider, `menu=False` | Menuen står lige efter `<body>` på `addPath`-sider, på HTML fra `public/` og på den tomme `/admin`. En side med `menu=False` har ingen menu, men får stadig scripts. |
| Titel | Titlen vises når den er sat. Uden titel er der intet titelelement. |
| Beskrivelse | `hj-menu-desc` står under titlen. |
| Tal | Tælleradressen står som `data-hj-count` og hentes af `menu.js`. Om tallet faktisk vises i browseren, er ikke efterprøvet (se nedenfor). |
| Underpunkter | Et overpunkt har sit eget link og en pil. Det står `open` på sin egen side og på underpunkternes, ellers lukket. |
| Aktivt punkt | Punktet har `active` og `aria-current="page"`, og der er kun ét pr. side. På `/admin` er det Admin-knappen. |
| Skjult/nedtonet | `user` ser ikke Kommuner, hverken i menuen eller i JSON. Med `denied="disable"` står punktet som `<span aria-disabled>` uden link og uden tal. |
| Admin-knap | Vises for `admin`, ikke for `user` og ikke uden auth. Den tomme `/admin` giver 200 for admin, 403 for user og 404 uden auth eller med `admin=False`. En apps egen `/admin` bruges i stedet. |
| Start nægtes | Start nægtes med en roleHierarchy uden `admin`: `RuntimeError: app.menu: the Admin button is for the role 'admin', which is not in roleHierarchy. Add 'admin' to roleHierarchy in app.settings(), or pass app.menu(..., admin=False).` Med `admin=False` starter den. |
| "Logget ind som" | Linjen `Logget ind som <strong>admin</strong>` står der. Med `showUser=False` er den væk, og uden auth står den ikke. |
| `sidebar=False` | Ingen `<nav>` og ingen css. JSON'en har nøglerne `title, url, desc, short, count, active, disabled, items`, `active` følger siden, og `menu.js` er sat ind. |
| Ukendt adresse | Start nægtes: `RuntimeError: app.menu: no page is registered at /findes-ikke (menu item 'Findes ikke'). Register it with app.addPath('/findes-ikke', ...) or fix the address.` |
| Almindelige sideskift, TableViewer og kalender | Menupunkterne er almindelige `<a href>`. TableViewer-siden og kalendersiden får menuen og deres egne scripts, og TableViewers dataroute svarer. Intet i rammeværkets øvrige scripts afhænger af `<body>`s første barn. Dialogen bruger `<dialog>`, som ligger over menuen. |
| Ligner skærmbillederne, `public/css/menu.css` | CSS'en er skrevet efter beskrivelsen. Overskrivning sker med samme mekanisme som de andre filer (`_register_asset_route`). Udseendet er ikke efterprøvet. |
| Ingen HTML-indsættelse | En titel `<b>Kalender</b>`, en beskrivelse `"><script>alert(1)</script>`, et kort navn `<i>` og en menutitel `Ophold & <co>` vises escaped. JSON'en indeholder intet rå `<` eller `>`. |
| Dokumentation | `docs/guide/menu.md` med eksemplerne. Linktjek: 63 links, 0 brudte. |

Proxy-tilstand er også efterprøvet. Et kald uden nøgle får 403. På en offentlig side uden bruger viser menuen kun det offentlige punkt. Med Authentik-headere for en admin vises alle punkter.

**Linje til projektets README** (dokumentationslisten, efter Frontend):

```
- [Side menu](docs/guide/menu.md) - `app.menu(...)`: a menu on the left of every page, items hidden by role, Admin button
```

**Nyt for brugeren:** `app.menu(items, title=None, showUser=True, admin=True, sidebar=True)`, `MenuItem(...)` (importeres fra `WebServer`), `addPath(..., menu=False)` og `hjMenu.items` i siden. Ingen nye nøgler i `.env`.

**Sådan starter du testappen med flere roller.** Appen ligger uden for repoet, i
`C:\Users\d1misgu\AppData\Local\Temp\claude\20b2dc0acb4a4de2\f7a70dfd-84be-46bf-8615-3170309b32ec\scratchpad\menuapp\main.py`.
Den bruger udviklingstilstand og SQLite i `%TEMP%`. Kør fra projektroden i PowerShell:

```powershell
$env:PYTHONPATH = (Get-Location).Path
$env:JWT_SECRET = .venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
$env:TEST_ROLE = "admin"
.venv\Scripts\python.exe C:\Users\d1misgu\AppData\Local\Temp\claude\20b2dc0acb4a4de2\f7a70dfd-84be-46bf-8615-3170309b32ec\scratchpad\menuapp\main.py
```

Åbn `http://127.0.0.1:8091/p109`. Stop med Ctrl+C. Sæt så `$env:TEST_ROLE = "user"` og start igen for at se menuen som `user`.

| Variabel | Værdi | Viser |
|---|---|---|
| `TEST_ROLE` | `admin` | Alle punkter, Admin-knappen og "Logget ind som admin" |
| `TEST_ROLE` | `user` | Uden Kommuner og uden Admin-knap |
| `TEST_ROLE` | `none` | Uden `auth=True`: alle punkter, ingen Admin-knap, ingen "Logget ind som" |
| `TEST_VARIANT` | `disable` | Kommuner nedtonet for `user` |
| `TEST_VARIANT` | `notitle`, `nouser`, `noadmin`, `nosidebar`, `ownadmin` | De tilsvarende valgmuligheder. Med `nosidebar` viser `/egen-nav` opgavens eget-nav-eksempel |

Hvad der kan ses i testappen:

- **Tal:** `/p109` viser tallet 12. `/p110`s adresse svarer med en tekst, så dér skal der ikke stå noget tal.
- **TableViewer og kalender:** Kommuner (`/stamdata/kommuner`) har en TableViewer, og `/cal` har kalenderen.
- **Escaping:** Det fjerde punkt og menutitlen indeholder med vilje `<b>`, `<script>` og `<co>`. De skal stå som tekst.
- **`menu=False`:** `/` er en side uden menu.

### Hvad er ikke lavet, og hvorfor

- **Udseende, sammenklapning, pilene og om tallene vises i browseren er ikke efterprøvet.** Det kræver en browser, og den starter en agent ikke (kontraktens `## Efterprøvning af en webflade`). Opgaven lægger det hos architect. HTML'en, ruterne og `menu.js`' syntaks (`node --check`) er efterprøvet.
- **Hele suiten er ikke kørt.** Der findes ingen, og opgaven beder ikke om det. Der findes heller ingen linter i projektet. De ændrede Python-filer er kompileret med `py_compile`.
- **Mit testapparat er ikke lagt i repoet:** testappen, `run_checks.py` og `compare_nomenu.py` i scratchpad-mappen. Opgaven beder ikke om en maskinel kontrol.

### Uklart

1. **En offentlig side uden bruger.** På en side med `public=True` sætter `WebHandler` ikke `request.user`. Menuen spørger derfor selv `resolve_user` om brugeren (proxyens nøgle er allerede tjekket). Er der ingen logget ind, viser jeg kun punkter for offentlige sider; de øvrige skjules eller nedtones efter `denied`. Den anden mulighed var at vise dem, fordi Authentik ville bede om login ved klik.
2. **`hj:ready` findes kun med `auth=True`.** Det godkendte eksempel med `sidebar=False` lytter på `hj:ready`, som `auth.js` sender. Uden auth sendes den aldrig. Jeg har ikke ændret `auth.js` (uden for opgaven). I stedet sættes `hjMenu` før `DOMContentLoaded`, og `menu.md` siger at man bruger `DOMContentLoaded` uden auth. Skal `menu.js` sende `hj:ready` når `auth.js` ikke er der, er det en ny beslutning.
3. **`menu.css` linkes af serveren, ikke af `menu.js`.** Det afviger fra de andre stylesheets. Hvert klik i menuen er en hel sideindlæsning, og et stylesheet som scriptet sætter ind, blokerer ikke tegningen. Menuen ville derfor blinke ustylet ved hvert klik. `<link>` står lige før `<nav>`, så den kan stadig overskrives på samme måde. Af samme grund står der et lille inline-script efter `<nav>`, der klapper menuen sammen før første tegning. Med standard-CSP'en virker det (`'unsafe-inline'`). Med en strengere `csp=` blokeres det, og så klapper `menu.js` menuen sammen lidt senere: den blinker åben.
4. **HTML-filer direkte fra `public/` får menuen og kan ikke fravælge den.** `menu=False` findes kun på `addPath`, og opgaven siger "ingen anden ændring". Filer uden `<body>`-tag får ingen menu, så partials er ikke ramt.
5. **Kort navn uden `short=`:** de første fire tegn af titlen. Det tal er mit valg.
6. **Danske tekster i rammeværket.** "Kun for administratorer" og "Logget ind som" står i opgaven og er brugt som de står. Knappernes hjælpetekster ("Klap menuen sammen", "Fold menuen ud", "Vis eller skjul underpunkter") har jeg også skrevet på dansk. Rammeværkets øvrige tekster er engelske (Dialogs `OK`/`Cancel`, TableViewers `Yes`/`No`).
7. **Små valg i reglerne.** Et nedtonet punkt henter ikke sit tal: adressen er sandsynligvis lige så lukket som siden, og hver afvisning skrives i auditloggen. Er et overpunkt skjult, er dets underpunkter det også. Er et overpunkt nedtonet, vises underpunkterne efter deres egen regel. Underpunkter kan have egne underpunkter; tegningen er den samme for alle niveauer.
