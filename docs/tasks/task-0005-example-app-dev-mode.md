---
nummer: task-0005
titel: Eksempelappen starter i udviklingstilstand
status: afsluttet
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
- `main.py`: `app = WebServer(port=8080)`, som lytter på `127.0.0.1`. Linjen til drift, `# app = WebServer(host="0.0.0.0", port=8080)`, står som kommentar lige under. `settings()` har fået `devUser={"username": "test", "groups": [os.environ["GROUP_ADMIN"]]}`, og linjen under siger hvad der skal ændres i drift: fjern `devUser`, brug `host="0.0.0.0"`, og `PROXY_SECRET` skal så også stå i `.env`. Kommentaren over `settings()` siger nu at kun `JWT_SECRET` og `GROUP_ADMIN` kræves lokalt. Databaseopsætning, tabeller og ruter er ikke rørt.
- `.env.example`: `GROUP_ADMIN=` uden værdi, under en overskrift for eksempelappen og en kommentar om at nøglen hører til eksempelappen, ikke rammeværket.

Holdt op mod *Færdig når*. `main.py` og `public/` blev kopieret til en midlertidig mappe og indlæst med `setDatabase` skiftet ud med SQLite og en ledig port. MSSQL og projektets `.env` er ikke rørt. Nøglerne kom fra processens miljø (22 tjek, alle holdt):
- **Kan bruges som admin uden proxy og Authentik:** `/` og `/cal` svarer 200 med HTML og `auth.js`. `/api/verify` giver brugeren `test` med rollen `admin`, og `POST /api/cal` med formulartokenet svarer 200. Ved start skrives `UDVIKLINGSTILSTAND: alle er "test" (admin)`.
- **Lytter kun på den lokale maskine:** `main.py` beder om `127.0.0.1` (standarden). Serveren kører på `127.0.0.1`, og et kald til maskinens netværksadresse på samme port bliver afvist.
- **Linjerne til drift**, ændret som kommentarerne siger (`devUser` fjernet, linjen med `0.0.0.0` taget i brug):
  - Uden `PROXY_SECRET` nægter appen at starte.
  - Med nøglen giver et kald uden den en nøgen 403, og en bruger i `GROUP_ADMIN` er admin. Efterprøvet bundet til `127.0.0.1`, ikke alle adresser, så maskinens firewall ikke blev involveret.
  - Ændres kun værten og `devUser` bliver stående, nægter appen at starte, før den lytter.
- **`.env.example`:** `GROUP_ADMIN`, `JWT_SECRET` og `PROXY_SECRET` står der, alle uden værdi.

Ny nøgle til README: `GROUP_ADMIN` (eksempelappen), Authentik-gruppen hvis medlemmer er admin. Lokalt kræver eksempelappen `JWT_SECRET` og `GROUP_ADMIN` i `.env`; i drift også `PROXY_SECRET`.

### Hvad er ikke lavet, og hvorfor
- Ikke set i en browser (kontraktens *Efterprøvning af en webflade*). Om siderne ser rigtige ud og TableViewer viser data, er ikke efterprøvet. TableViewer på `/api/forsorgshjem` kræver eksempelappens MSSQL-database, som efter opgaven ikke måtte bruges.
- Projektets egen `.env` er ikke læst eller rettet. Mangler `GROUP_ADMIN` i den, stopper `main.py` med en `KeyError` ved `os.environ["GROUP_ADMIN"]`. Mennesket skal selv lægge nøglen ind.

### Uklart
- Kommentarerne i `main.py` er på engelsk som filens øvrige kommentarer, ikke på dansk som i opgavens godkendte eksempel ("kun din maskine", "i drift: fjern devUser ..."). Koden er den samme som i eksemplet. Driftslinjen står som en hel kommentarlinje under `WebServer(port=8080)` i stedet for kun som en note efter `settings()`, så den kan tages i brug ved at fjerne `#`.
