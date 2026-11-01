# Alpha: eigener Host und eigene Effekte in der Oberfläche

## Korrigiertes Rollenmodell

Der **Hostbesitzer** ist ein gewöhnlicher Minglefield-Benutzer, der die Ausführung auf seinem eigenen Host kontrolliert. Er braucht keine Windows-/Linux-Administratorrechte und keine globalen Minglefield-Adminrechte. Er darf eigene Effektdefinitionen, manuelle Startabsichten und Host-Regeln verwalten. Ein Agentenbesitzer oder Auftraggeber erhält dadurch **keine** automatische Hostfreigabe.

Die bisherige lokale Host-Administrator-Fixture bleibt für ältere Tests bestehen, ist aber für neue eigene Hosts nicht erforderlich.

## Lokalen Host über die Alpha-Oberfläche übernehmen

1. Gateway **lokal mit** `--auth-db` starten. In der PowerShell erscheint ein temporärer `LOCAL host claim bootstrap code`.
2. Als Minglefield-Benutzer anmelden, in Abschnitt **5. Host-Verwaltung** eine Host-ID und den Konsolencode eintragen und auf **Diesen lokalen Host übernehmen** klicken.
3. Die Hostzuordnung wird dauerhaft in der Alpha-SQLite-DB gespeichert. Danach erscheinen eigene Hosts unter **Hosts und Regeln laden**. Ein anderer Benutzer kann einen bereits beanspruchten Host nicht übernehmen.
4. Regeln für GPU-Grenze, Parallelitätslimit, manuelle Freigabe und Zeitpläne anlegen und ändern.
5. Unter **Eigene Effekte** Effekt-ID, Beschreibung und Aktivierungsstatus speichern. **Manuellen Start simulieren** erzeugt nur eine Antwort, keinen realen Prozess.

Der Konsolencode ist ein zusätzlicher Nachweis, dass der Benutzer Zugriff auf den lokal gestarteten Gateway-Prozess hat. Die Hostübernahme prüft zudem Loopback-Adresse und lokalen Host-/Origin-Header. **Dieser Nachweis ist noch kein produktionsreifes Host-Pairing.** Insbesondere dürfen lokale Browserzugriffe, Reverse-Proxies und kompromittierte Hostprozesse nicht als sichere globale Eigentumsnachweise gelten. Code nicht weitergeben. Gateway weiterhin ausschließlich an 127.0.0.1 binden.

## Sicherheitsgrenze und nächste Schritte

Die neue Host-Eigentümertabelle `sec01_host_owners` ist unabhängig von Agenten- und Grant-Tabellen. Die Effekttabelle `sec01_host_effect_definitions` speichert **nur Textmetadaten**; keine Skripte, Shell-Kommandos, Dateipfade oder ComfyUI-Workflows werden interpretiert oder ausgeführt. Manuelle Starts sind **noch keine Ausführungsfreigabe**.

Noch erforderlich: UI-gesteuerte sichere Löschung und Auswahl von Effekten, echte Warteschlange, verifizierte Hostbindung, sichere Ausführungsadapter mit Allowlists, persistente Leases/Recovery, vertrauenswürdige GPU-Telemetrie und atomare Session-/Epoch-Prüfung. **SEC-01 bleibt CRITICAL/OPEN; keine echten Effekte und kein Tailscale Serve.**

## Validierung

```powershell
git pull --ff-only
python -B -m unittest discover -s tests/conformance -p "test_private_alpha_host_owner_ui.py" -v
python -B -m unittest discover -s tests/conformance -p "test_private_alpha_host_ui.py" -v
python -B -m unittest discover -s tests/conformance -p "test_*.py"
python -B tests/conformance/validate_map_v01.py
git diff --check
git status --short
```

Vorher bestätigte Baseline: 373/373; danach 377 Tests erwartet, aber vom Betreiber noch nicht bestätigt. Neu: vier Tests. **381 Tests erwartet**, nach Windows-Validierung.
