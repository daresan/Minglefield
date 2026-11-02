# Alpha UI und Jobrechte – Stand November 2026

## Bereits implementiert
- Login-gesteuerte Tabs: Anmeldung, Hosts, Effekte, Jobs und Agenten. Der Hostbereich und der Effektbereich verwenden derzeit dieselbe Host-Datenquelle.
- Auswahl existierender Hostregeln, Effekte und Hostjobs; Auswahl füllt vorhandene Eingabefelder. Layout auf flexible Felder umgestellt.
- Hostbesitzer oder in `requested_by` gespeicherter Auftraggeber dürfen eigene `queued`-/`waiting`-Jobs abbrechen oder `reserved`-Mock-Slots freigeben. Andere Benutzer werden abgewiesen.
- `reserved` ist weiterhin **nur Mock-Slot**, keine Ausführungsberechtigung.

## Noch nicht implementiert
- **Fremdauftraggeber:** Die aktuelle Alpha-API `manual_start_mock` erlaubt ausschließlich dem Hostbesitzer die Jobanlage. Daher ist die neue Auftraggeber-Prüfung vorbereitet, aber nicht durch echte Delegation aus dem UI erreichbar. Die Agent-/Grant-/Host-Admission muss vor einer Freigabe externer Auftraggeber mit atomarer Autorisierung verbunden werden.
- **Startgrenze:** Kein `starting`/`running`-Executor. Eine starre 60-Sekunden-Sperre wäre unzuverlässig; später gelten Fencing-Token und atomare Zustandsübergänge. Nach Start nur Stoppanfrage, keine fälschlich bestätigte Stornierung.
- **Host-Telemetrie:** `trusted_telemetry_required` bedeutet `idle_only=true` oder `gpu_max_percent != null` in der ersten zeitlich passenden aktiven Regel. Der Mock erhält keine vertrauenswürdigen Werte. Zur Reservierung in der lokalen Simulation nur für den Test beide Bedingungen deaktivieren. `parallel_limit_reached` erscheint erst, wenn ein Slot belegt ist.
- **Vollständige Objektverwaltung:** Ein-Klick-Auswahl ist vorhanden; Löschung von Effekten/Agenten/Hosts und dedizierte Jobfilter sowie Detailansichten sind noch nicht vorhanden.
- **E-Mail/Passwortreset:** Kein E-Mail-Feld, kein Versand und kein Reset-Endpunkt. Benötigt verifizierte Adressen, sichere einmalige zeitbegrenzte Reset-Token, Rate-Limits, nicht verräterische Antworten und eine konfigurierte Mailzustellung. Agentenidentitäten sollten vorzugsweise widerrufbare Zugangsdaten verwenden; E-Mail optional als Kontakt.
- **Sicherheitsstatus:** SEC-01 CRITICAL/OPEN; keine echten Effekte, kein Tailscale Serve.

## Verifikation
```powershell
git pull --ff-only
python -B -m unittest discover -s tests/conformance -p "test_private_alpha_host_owner_ui.py" -v
python -B -m unittest discover -s tests/conformance -p "test_*.py"
python -B tests/conformance/validate_map_v01.py
git diff --check
git status --short
```
