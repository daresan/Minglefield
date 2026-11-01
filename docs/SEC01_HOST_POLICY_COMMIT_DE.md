# SEC-01 Host Administration und regelbasierte Mock-Commit-Autorität

**Status: CRITICAL / OPEN — nur lokale Simulation, keine echte Ausführung.**

## Zuständigkeit

Die endgültige Ausführung eines Effekts wird **vom Host beziehungsweise seinen bevollmächtigten Administratoren** gesteuert, nicht allein vom Agentenbesitzer, Auftraggeber oder einer zentralen Minglefield-Admission. Ein Host kann die Kontrolle an eine lokal autorisierte Automatisierung delegieren; diese benötigt dieselben Host-Rechte und muss die konfigurierten Policies beachten.

`server/sec01_host_commit_policy_sim.py` implementiert ein erstes persistentes, hostbezogenes Regelmodell. Administratoren werden nur durch eine **vertrauenswürdige lokale Test-Fixture** eingetragen. Noch keine Benutzeroberfläche, HTTP-API, echte Administrator-Authentifizierung oder GPU-Abfrage.

## Mehrere Regeln je Host

Jede Regel hat eine eindeutige `rule_id`, Priorität, Aktivierung und editierbare Konfiguration. Administratoren können Regeln anlegen, verändern, deaktivieren, reaktivieren und löschen. Die Regeln werden nach aufsteigender Priorität und danach nach ID ausgewertet. Die **erste zeitlich passende aktive Regel ist maßgeblich**; blockierende Bedingungen werden nicht durch eine spätere großzügigere Regel umgangen. Gibt es keine passende Regel, wird gewartet.

Regelparameter:
- `mode`: `automatic` oder `manual` (manuelle Bestätigung für konkreten Effect-Key).
- `idle_only`: warten, solange andere Effekte laufen.
- `gpu_max_percent`: optionaler Grenzwert 0–100; Ausführung nur **unter** diesem Wert.
- `timezone`: IANA-Zeitzone, `weekdays`: 0=Montag bis 6=Sonntag.
- `start_minute` und `end_minute`: Zeitfenster [Start, Ende), derzeit nur innerhalb desselben Kalendertags.

Die Bedingungen einer Regel sind logisch **UND**. Nicht vorhandene erforderliche Telemetrie führt zum Warten, nicht zu einer automatischen Freigabe. In dieser Simulation werden Uhrzeit, GPU-Auslastung und Anzahl laufender Effekte vom Test übergeben. **Für einen echten Host müssen diese Werte aus einer vertrauenswürdigen lokalen Quelle stammen.** Zeitfenster über Mitternacht, Feiertagskalender, Reservierungen, Prioritätsklassen und GPU-Auslastungs-Mittelung sind noch nicht umgesetzt.

## Mock-Commit und Sicherheit

Die Commit-Entscheidung und das lokale Ledger erfolgen in derselben SQLite-Transaktion wie die erneute Prüfung der gespeicherten Alpha-Admission, des Eigentümers, des Requesters, des Grants, der Host-Identität und der Agent-/Host-Zuordnung. Doppelte Effect-Keys erzeugen keinen zweiten Mock-Commit. Nach simuliertem Neustart bleibt das Ledger erhalten.

**Wichtige Einschränkungen:** Das Modul akzeptiert derzeit nur den gespeicherten Admission-Binding-String; es führt selbst noch **keine** Session-/Epoch-Proof-Prüfung aus. Es ist daher **kein produktionsfähiger Final Commit Authority Service**. Außerdem wird keinerlei Effekt ausgeführt; das Ledger beschreibt nur eine simulierte Freigabe. Eine atomare Kopplung mit einer externen GPU-Aufgabe, einem Game-Effect oder einem entfernten Executor ist noch offen. Ein bereits protokollierter Mock-Commit wird bei einem späteren Widerruf nicht rückwirkend gelöscht.

## Validierung

```powershell
git pull --ff-only
python -B -m unittest discover -s tests/conformance -p "test_sec01_host_commit_policy.py" -v
python -B -m unittest discover -s tests/conformance -p "test_*.py"
python -B tests/conformance/validate_map_v01.py
git diff --check
git status --short
```

Letzter vom Betreiber bestätigter Stand: **354/354**. Hinzugefügt: **14 Tests**. Erwartet: **368/368**, nach Windows-Validierung.

## Nächste Stufen

1. Authentifizierte Host-Administratoren und Automatisierungsidentitäten, getrennt von Agentenbesitzern.
2. Atomare Einbindung der Epoch-/Session-Proof-Prüfung in dieselbe Commit-Transaktion; Revoke/Commit-Race-Tests.
3. Host-eigene GPU-/Busy-Telemetrie, Job-Queue, Kalender und Freigabe-UI.
4. Dauerhafte Reservation/Lease-/Effect-Lifecycle-Semantik und crash-sichere Idempotenz.
5. Erst danach Prüfung einer echten Executor-Schnittstelle. **Kein Serve, keine realen Effekte.**
