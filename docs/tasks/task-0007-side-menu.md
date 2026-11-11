---
nummer: task-0007
titel: Sidemenu som app-udvikleren slår til i main.py
status: planlagt
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
### Hvad er ikke lavet, og hvorfor
### Uklart
