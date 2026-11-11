---
nummer: task-0004
titel: Læs .env fra appens mappe
status: planlagt
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
### Hvad er ikke lavet, og hvorfor
### Uklart
