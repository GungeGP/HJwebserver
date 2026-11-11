---
nummer: task-0002
titel: Rammeforbud på alle svar bag Authentik
status: planlagt
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
### Hvad er ikke lavet, og hvorfor
### Uklart
