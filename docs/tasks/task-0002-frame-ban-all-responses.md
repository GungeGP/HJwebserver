---
nummer: task-0002
titel: Rammeforbud på alle svar bag Authentik
status: afsluttet
kilde: interview
oprettet: 2026-11-11
---

# task-0002 — Rammeforbud på alle svar bag Authentik

## Hvad og hvorfor
Kontraktens `## En app bag Authentik` kræver at hvert svar forbyder at siden
vises i en ramme. Efter task-0001 gælder det altid for afvisninger, men på
almindelige svar kun med standardindstillingerne. Slår en app
sikkerhedsheaderne fra eller sætter sin egen CSP uden `frame-ancestors`, kan
dens sider vises i en ramme. Fundet kom frem i developers noter til task-0001.

## Færdig når
- [ ] Med `auth=True` bærer hvert svar forbuddet mod rammer, uanset `securityHeaders` og `csp`.
- [ ] En app der selv sætter en CSP, beholder sine egne regler; forbuddet mod rammer lægges til, hvis det mangler.
- [ ] Uden `auth=True` er headerne som i dag.
- [ ] `docs/auth.md` siger at forbuddet ikke kan slås fra bag Authentik.

## Sådan ser det ud i en app
Intet ændres i appens kode. Det her virker som før, men siderne kan ikke længere vises i en ramme:
```python
app.settings(auth=True, securityHeaders=False)
app.settings(auth=True, csp="default-src 'self'")   # forbuddet lægges til
```

## Sådan bygger vi det
- I `ServerMixin._security_headers`: med `self.auth` sendes altid `X-Frame-Options: DENY`, og `frame-ancestors 'none'` lægges til en CSP der mangler det. Uden CSP sendes `Content-Security-Policy: frame-ancestors 'none'`.
- En handler der selv har sat headeren, vinder stadig som i dag — undtagen at `frame-ancestors` lægges til.

## Hvad vi ikke rører
- Afvisningerne fra task-0001, som allerede har forbuddet.
- Alle andre sikkerhedsheadere.

## Afhænger af
task-0001

## Beslutninger
- BESLUTTET: Forbuddet tvinges kun med `auth=True` — kontraktens krav gælder apps bag Authentik; apps uden login styrer selv deres headere som i dag.

## Åbne punkter

## Indvendinger

---

## Developers noter

<Alt over denne overskrift ejes af architect. Alt herunder skrives kun af
developer, som aldrig retter i definitionen ovenfor.>

### Hvad er lavet
- `WebServer/core/server.py`: ny `with_frame_ban(csp)` og konstanten `FRAME_BAN`. Funktionen lægger `frame-ancestors 'none'` til en CSP der mangler det, sætter det i stedet for en `frame-ancestors` der tillader rammer, og lader resten af politikken stå. En CSP der allerede har `frame-ancestors 'none'` (fx standardpolitikken) returneres uændret. Ingen CSP giver `frame-ancestors 'none'` alene.
- `WebServer/core/server.py`, `ServerMixin._security_headers`: med `self.auth` sendes altid `X-Frame-Options: DENY` og en CSP med forbuddet, også med `securityHeaders=False` og `csp=None`. Uden `auth` er logikken den samme som før (kun omstruktureret, så forbuddet kan lægges på til sidst).
- `WebServer/WebHandler.py`, `send_header`: en CSP som en handler selv sætter, får forbuddet lagt til med `auth` slået til. Handlerens øvrige regler står. Handlerens egen `X-Frame-Options` vinder som i dag; forbuddet ligger i CSP'en, og browsere følger `frame-ancestors` frem for `X-Frame-Options`.
- `docs/guide/auth.md`, afsnittet *Security headers*: siger at forbuddet ikke kan slås fra bag Authentik, med en tabel over hvad der sendes for hver indstilling. Eksemplet med en strengere CSP viser nu at forbuddet lægges til. Opgaven siger `docs/auth.md`; filen ligger i `docs/guide/` efter task-0006.
- `docs/guide/webserver.md`: rækkerne for `csp` og `securityHeaders` i tabellen over `settings()` nævner forbuddet med en halv sætning hver, så de ikke modsiger `auth.md`.

Holdt op mod *Færdig når*, efterprøvet med HTTP-kald mod egne servere på SQLite i en midlertidig mappe (13 opsætninger, 339 tjek, alle holdt):
- Med `auth=True` — standard, `securityHeaders=False`, egen CSP, `csp=None`, CSP med `frame-ancestors 'self'`, og i udviklingstilstand med og uden menu — bærer hver side, statisk fil, API-svar, 401, 404, rammeværkets egne filer og den nøgne 403 (uden nøgle og med forkert nøgle) `X-Frame-Options: DENY` og en CSP med `frame-ancestors 'none'`.
- Egen CSP `default-src 'self'` sendes som `default-src 'self'; frame-ancestors 'none'`. En handler-CSP `default-src 'none'` sendes med forbuddet lagt til.
- Uden `auth=True` er headerne som før for standard, `securityHeaders=False` (ingen headere), egen CSP og `csp=None`; en handlers egen CSP med `frame-ancestors 'self'` står urørt.
- Menuen fra task-0007 virker uændret: menuen står i siden, `/admin` svarer 200 for en admin, `menu.css` svarer 200 med forbuddet.

Ingen nye kommandoer eller indstillinger.

### Hvad er ikke lavet, og hvorfor
intet

### Uklart
- En app-CSP med `frame-ancestors 'self'` (eller en anden kilde) får den udskiftet med `'none'` bag Authentik. Jeg læste kriteriet "uanset `csp`" som at forbuddet skal gælde, også når appen selv tillader rammer; at lægge et ekstra `frame-ancestors` til ville ikke virke, fordi browsere kun læser det første. Er det forkert, er ændringen én linje i `with_frame_ban`.
- En handler der selv sætter `X-Frame-Options: SAMEORIGIN`, beholder den, som opgaven siger ("vinder stadig som i dag"). Svaret er stadig forbudt i en ramme via CSP'en, men bærer ikke `X-Frame-Options: DENY` ordret som kontraktens punkt 6 skriver. Rammeværkets egen kode sætter aldrig den header i en handler.
