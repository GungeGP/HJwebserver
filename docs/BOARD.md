# BOARD

Tilstandsrapport. Svarer på: **hvad er åbent, og hvad venter på mig.** Skal kunne skimmes på ti sekunder.

**Skrives af `architect`**, som er den eneste rolle der opretter opgaver, sætter statusser og triagerer rapporter. Opdateres før tråden lukkes. Ingen agent skriver her.

`status` skriver den ikke — den læser den, holder den op mod filerne, og siger til hvis den er skredet. **Er BOARD uenig med en fil, er filen rigtig.**

**Ingen prosa i tabellerne.** Ingen commit-hashes, filstier, datoer eller begrundelser. Begrundelser hører i `docs/decisions/log.md`.

## Rapporter klar til behandling

| Nr. | Rolle | Uafhentede punkter |
|---|---|---|

<En rapport står her indtil hvert af dens fund er blevet en opgave eller er
afvist i beslutningsloggen. Det er det eneste sted et fund kan forsvinde —
en rapport der har stået her i dagevis, er et fund på vej til at blive glemt.>

## Opgaver

| Nr. | Titel | Status | Kilde |
|---|---|---|---|
| task-0002 | Rammeforbud på alle svar bag Authentik | planlagt | interview |
| task-0003 | Fjern resterne af det gamle login | planlagt | interview |
| task-0004 | Læs .env fra appens mappe | planlagt | interview |
| task-0005 | Eksempelappen starter i udviklingstilstand | planlagt | interview |

<`Status` er `planlagt`, `i-gang` eller `afsluttet`. `Kilde` er `interview`
eller nummeret på den rapport opgaven kom af.>

## Kommende

| Emne |
|---|
| Flyt forretningsspecifikke værdier — databasenavn, tabel- og kolonnenavne, maildomæne — ud af eksempelappen og dokumentationen |
| Lav en testsuite i projektet, startende med de midlertidige test af login og samtidighed |
| Afklar om databaseadgang og logning skal følge organisationens præferencer eller stå som afvigelse |
| Sæt linjeskift til LF for alle tekstfiler |
| Hold Claudes lokale indstillinger og alle miljøfiler ude af versionsstyringen |

<Den grove liste: hvad architect kan se der skal laves. **Ingen numre.**
Et emne får først et nummer når interviewet har gjort det udførbart —
ellers fyldes `docs/tasks/` med halve idéer.>

## Afsluttet

| Nr. | Titel | Udfald |
|---|---|---|
| task-0001 | Login via Authentik i stedet for appens eget login | bygget |
| task-0006 | Rammeværkets dokumentation i sin egen mappe | bygget |
| task-0007 | Sidemenu som app-udvikleren slår til i main.py | bygget |
| task-0008 | Menuens udseende som skærmbillederne | afvist |

<`Udfald` er `bygget` eller `afvist`. Flyt hertil når architect har vurderet
opgaven — ikke når udrulningen er sket; udrulning er ikke en status.
Slet ikke herfra; historikken er billig.>
