---
nummer: task-0005
titel: Eksempelappen starter i udviklingstilstand
status: planlagt
kilde: interview
oprettet: 2026-11-11
---

# task-0005 — Eksempelappen starter i udviklingstilstand

## Hvad og hvorfor
Efter task-0001 er eksempelappen sat op til drift bag Authentik. Kørt lokalt
uden proxy svarer den 403 på alt. Den skal i stedet kunne køres direkte på en
udviklers maskine, så man ser rammeværket virke, før Authentik er sat op.
Driftsopsætningen skal stadig kunne læses i filen.

## Færdig når
- [ ] `.venv\Scripts\python.exe main.py` på en udviklers maskine giver en app der kan bruges i browseren, som en admin-bruger, uden proxy og uden Authentik.
- [ ] Appen lytter kun på den lokale maskine.
- [ ] Linjerne til drift står som kommentar lige ved, med hvad der skal ændres: fjern udviklingstilstanden og lyt på alle adresser.
- [ ] De nøgler eksempelappen selv kræver i `.env`, står i `.env.example` under en overskrift for eksempelappen, uden værdier.

## Sådan ser det ud i en app
Godkendt af mennesket.
```python
app = WebServer(port=8080)          # kun din maskine
app.settings(auth=True,
             roleHierarchy=["admin", "user"],
             authentikRoles={os.environ["GROUP_ADMIN"]: "admin"},
             devUser={"username": "test", "groups": [os.environ["GROUP_ADMIN"]]})
# i drift: fjern devUser og sæt host="0.0.0.0"
```

## Sådan bygger vi det
- Kun `main.py` og `.env.example`.
- `GROUP_ADMIN` tilføjes `.env.example` under en kommentar om at nøglen hører til eksempelappen, ikke rammeværket.

## Hvad vi ikke rører
- Rammeværket.
- Eksempelappens databaseopsætning, tabeller og ruter. Forretningsværdierne i den er et særskilt emne på tavlen.

## Afhænger af
task-0001

## Beslutninger
- BESLUTTET: Eksempelappen starter i udviklingstilstand; driften står som kommentar — menneskets valg, så den kan køres direkte lokalt.

## Åbne punkter

## Indvendinger

---

## Developers noter

<Alt over denne overskrift ejes af architect. Alt herunder skrives kun af
developer, som aldrig retter i definitionen ovenfor.>

### Hvad er lavet
### Hvad er ikke lavet, og hvorfor
### Uklart
