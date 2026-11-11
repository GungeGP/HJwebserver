---
nummer: task-0008
titel: Menuens udseende som skærmbillederne
status: afsluttet
kilde: interview
oprettet: 2026-11-11
---

# task-0008 — Menuens udseende som skærmbillederne

## Hvad og hvorfor
Menuen fra task-0007 virker og har den rigtige opbygning, men den ligner ikke
menneskets skærmbilleder i farver og detaljer. Afvigelserne blev set af
architect i browseren, da task-0007 blev vurderet.

## Færdig når
- [ ] Menuens baggrund er hvid med en tynd, lys grå kant mod indholdet.
- [ ] Det aktive punkt er mørk skifergrå, ikke grøn, med hvid fed tekst og runde hjørner.
- [ ] Admin-knappen er brændt orange, som en afrundet pille med fed hvid tekst.
- [ ] "Kun for administratorer" står centreret, fed, med små versaler i grå. "Logget ind som …" står centreret under knappen.
- [ ] Titlen øverst er større og fed.
- [ ] Pilen ved et åbent overpunkt peger op, ved et lukket ned.
- [ ] I den smalle udgave er Admin-knappen en rund knap med det første bogstav.
- [ ] Tallet står i en lys grå boks med mørk tekst, også på det aktive punkt.
- [ ] Indholdet ved siden af menuen har luft til den.
- [ ] Alt fra task-0007 virker uændret. En `public/css/menu.css` i appen erstatter stadig rammeværkets.

## Sådan ser det ud i en app
Intet ændres i appens kode.

## Sådan bygger vi det
- Kun `WebServer/public/css/menu.css`, og `menu.js` hvis den runde Admin-knap kræver et bogstav i markuppen. Ingen ændring af grænsefladen.
- Farverne aflæses af skærmbillederne: aktivt punkt omkring `#2F3E40`, Admin-knap omkring `#B9520F`. Ret dem efter øjemål, ikke til den grønne fra `auth.css`.
- Luften til indholdet gives af menuens egen regel for `body.hj-has-menu`, ikke af siderne.
- Udseendet efterprøves af architect i browseren.

## Hvad vi ikke rører
- Menuens opbygning, regler og grænseflade fra task-0007.

## Afhænger af
task-0007

## Beslutninger
- BESLUTTET: Skærmbillederne er forlægget, ikke rammeværkets øvrige farver — task-0007 sagde "ligner skærmbillederne".

## Åbne punkter

## Indvendinger

---

## Developers noter

<Alt over denne overskrift ejes af architect. Alt herunder skrives kun af
developer, som aldrig retter i definitionen ovenfor.>

### Hvad er lavet

Afvist af architect før den blev bygget: mennesket har godkendt menuens nuværende udseende. Se beslutningsloggen.
### Hvad er ikke lavet, og hvorfor
### Uklart
