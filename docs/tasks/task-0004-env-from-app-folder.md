---
nummer: task-0004
titel: Læs .env fra appens mappe
status: afsluttet
kilde: interview
oprettet: 2026-11-11
---

# task-0004 — Læs .env fra appens mappe

## Hvad og hvorfor
Rammeværket leder i dag efter `.env` opad fra sin egen mappe, ikke fra appens.
Det virker kun når rammeværket ligger i appens projektmappe. Er det installeret
som pakke, finder det ikke appens `.env`, og så starter appen ikke, eller
`os.environ` i `main.py` mangler værdierne. Eksemplerne fra task-0001 bygger på
at `.env` er læst når appen oprettes. Fundet i developers noter til task-0001.

## Færdig når
- [ ] `.env` i mappen med appens startfil findes, også når rammeværket er installeret et andet sted.
- [ ] Findes der ingen `.env` dér, bruges `.env` i den mappe appen startes fra.
- [ ] Værdier der allerede står i miljøet, overskrives ikke af `.env`.
- [ ] Eksemplerne fra task-0001 virker som før, når rammeværket ligger i projektmappen.

## Sådan ser det ud i en app
Intet ændres. Det her virker nu også med rammeværket installeret som pakke:
```python
app = WebServer(port=8080)
os.environ["GROUP_ADMIN"]
```

## Sådan bygger vi det
- I `ServerMixin.__init__`: `load_dotenv` med en eksplicit sti — først mappen med `sys.argv[0]`, ellers `find_dotenv(usecwd=True)`. Samme mønster som rammeværket allerede bruger for at finde `public/`.

## Hvad vi ikke rører
- Hvilke nøgler der kræves, og hvornår.

## Afhænger af
task-0001

## Beslutninger
- BESLUTTET: Appens startfils mappe først, derefter arbejdsmappen — det er der appens `public/` også findes.

## Åbne punkter

## Indvendinger

---

## Developers noter

<Alt over denne overskrift ejes af architect. Alt herunder skrives kun af
developer, som aldrig retter i definitionen ovenfor.>

### Hvad er lavet
- `WebServer/core/server.py`: ny funktion `_app_dotenv()`, som returnerer `.env` i mappen med `sys.argv[0]` hvis den findes, ellers `find_dotenv(usecwd=True)`, ellers `None`. `ServerMixin.__init__` kalder `load_dotenv` med den sti i stedet for `load_dotenv()` uden sti, og springer kaldet over når der ingen fil er. Det sker stadig først i `__init__`, så `os.environ` virker i `main.py` fra linjen efter `WebServer(...)`. `override` er ikke sat (standard `False`), så værdier i miljøet vinder.
- `docs/guide/auth.md` (afsnittet om `.env`) og `docs/guide/webserver.md` (om `WebServer(...)`): siger hvor `.env` findes, og at nøgler i miljøet ikke overskrives.

Holdt op mod *Færdig når*, efterprøvet med egne servere på SQLite i midlertidige mapper. Rammeværket var kopieret til en separat mappe og hentet via `PYTHONPATH`, som en installeret pakke (13 tjek, alle holdt):
- **`.env` ved startfilen, rammeværket et andet sted:** `PROXY_SECRET`, `JWT_SECRET` og `GROUP_ADMIN` kommer fra filen. Kald med nøglen fra filen går igennem, gruppen fra filen giver admin, og `os.environ` i appen har værdierne lige efter `WebServer(...)`. Modprøve: samme opsætning med `server.py` fra `HEAD` finder ikke filen og stopper på `GROUP_ADMIN`.
- **Ingen `.env` ved startfilen:** `.env` i den mappe appen startes fra, bliver brugt. Findes begge, vinder den ved startfilen.
- **Miljøet vinder:** `GROUP_ADMIN` og en egen nøgle sat i miljøet beholder deres værdi; filens værdi bruges ikke.
- **Rammeværket i projektmappen som i dag**, med eksemplet fra task-0001 (`authentikRoles` og `devUser` fra `os.environ["GROUP_ADMIN"]`): appen starter, og testbrugeren er admin.
- **Kommandolinjen:** `python -m WebServer --app app:app audit` kørt fra appens mappe finder appens `.env`. Her er `sys.argv[0]` pakkens `__main__.py`, så det er arbejdsmappen der bruges.
- task-0002's og task-0003's tjek kørt igen bagefter; alle holdt.

Ingen nye kommandoer eller indstillinger.

### Hvad er ikke lavet, og hvorfor
intet

### Uklart
- `find_dotenv(usecwd=True)` leder også i mapperne over arbejdsmappen, ikke kun i den. Det følger opgavens "Sådan bygger vi det"; kriteriet siger kun "den mappe appen startes fra". Dokumentationen nævner det.
- Ændret adfærd i ét tilfælde: lå `.env` før kun i en mappe over *rammeværket* (fx projektroden) mens appen startes et helt andet sted fra, blev den fundet før og bliver det ikke nu. Det er netop meningen med opgaven, men en udrulning der har levet af det, mister sine nøgler.
