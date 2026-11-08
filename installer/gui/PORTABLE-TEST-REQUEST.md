# M2.11 – korrigierter Shadow-Abnahmebuild nach fünf gemeldeten Regressionen (2026-11-08)

**Gezielter zweiter T4-Paketierungslauf, auf Basis des bereits vorhandenen portablen Workflows.**
Der frühere T4-Abnahmebuild aus Commit `c50e7d2` wurde auf Shadow **ausdrücklich abgelehnt**.
Dieser neue Marker wird ausschließlich geschrieben, weil nach den konkreten fünf
Fehlerbehebungen die Windows-spezifischen und dreifachen Plattform-Gates grün sind.
Keine automatische Nachforderung weiterer Builds, kein Branchwechsel, Merge,
Release oder Deployment. Paketierung allein bestätigt keine Windows-Bedienung.

**Branch:** `feat/game-integration-updates`
**Geprüfte Quellcodebasis:** `4863c7503e86e87495c8db8838be99547fe73769`
**Abnahmeartefakt:** ausschließlich der durch *diesen Marker* ausgelöste
aktuelle Build; frühere ZIPs dürfen für die erneute Shadow-Abnahme nicht
wiederverwendet werden.

## Unveränderte Bedienung und die fünf konkret korrigierten Punkte

Der Setup Manager bleibt **portabel und sechsstufig**. Seite 5 enthält
weiterhin den vollständigen lesbaren/bearbeitbaren Datenbankeditor,
Schemaüberprüfung und Ja/Nein-Schemamigration sowie die zusätzliche
`mingleadmin`-Konfiguration. Seite 6 ist nur die Übersicht gewählter
Optionen mit genau **einer** Checkbox `Installation durchführen` und
**einem** Button `Installieren`. Keine manuellen Schreib-/Migrationstests,
keine Testdatenbank und keine Bestätigungswörter in Großbuchstaben.

1. **DB-Vorschläge automatisch bei Start:** Nur lesende Suche im
   bekannten Standard-Datenverzeichnis, unter Windows
   `%LOCALAPPDATA%\Minglefield`. Bekannte SQLite- und verschlüsselte
   SQLCipher-Kandidaten werden angezeigt; manuelle Dateiauswahl bleibt erhalten.
   Header/Dateiendung allein sind keine Freigabe für Datenbankänderungen.
2. **Belegtes SQLCipher-Ziel:** Warnung `Weiter`/`Abbruch` statt
   blockierender Pflicht-Testdatenbank. Eine schon in einem früheren
   Installationsversuch erzeugte gültige verschlüsselte Zieldatenbank wird
   bei passendem Schlüssel und passenden vorgemerkten Zeilen-/Schemaänderungen
   **unverändert wiederverwendet**; sie wird nicht automatisch gelöscht,
   überschrieben oder neu verschlüsselt. Inkonsistenzen ergeben einen
   klaren Abbruch bei erhaltenen Daten.
3. **Tatsächlich vorhandene lokale Host-ID:** Eine importierte
   `host.local`- oder andere bestehende Host-ID wird aus der DB gelesen;
   bei Mehrdeutigkeit ist der richtige Host auf Seite 5 auszuwählen.
   `mingleadmin` erhält die fehlende gezielte Adminzuordnung auf
   genau diesem Host, auch wenn andere Benutzer (z. B. `user.daniel`)
   bereits Hostbesitzer sind. Ihre Rechte und Zugangsdaten bleiben bestehen.
   Ein vormals einem falschen Host zugeordneter bestehender
   `mingleadmin` kann zusätzlich die korrekte lokale Hostzuordnung erhalten,
   ohne alte Berechtigungen stillschweigend zu löschen.
4. **Feste Anwendungslokaladresse:** Standardstart
   `http://127.0.0.1:8765/` statt zufälliger Browserports; nur isolierte
   interne Startproben bleiben bei `port=0`. Ein bereits belegter
   Anwendungsport ist ein sichtbarer Konflikt, **kein Anlass**, nebenher
   unkontrolliert neue Instanzen an weiteren Ports zu starten.
5. **Echte Windows-Anwendung:** Der Eintrag in `Installierte Apps`
   gehört zur installierten **Minglefield-Anwendung**, nicht zum
   portablen Setup Manager. Die Benutzer-Deinstallation entfernt ausschließlich
   inventarisierte, verwaltete App-Dateien und lässt Datenbanken,
   Sicherungen und Fremddateien unberührt. Die unabhängige
   `Minglefield.exe` besitzt unter Windows ein Infobereich-/Taskleisten-Icon
   mit `Minglefield im Browser öffnen` und `Minglefield beenden`.
   Das Beenden beendet den zu dieser Instanz gehörigen Python-Prozessbaum
   und entfernt das Icon; andere Python-Prozesse bleiben unberührt.

## Erfolgreiche T1–T3-Gates dieses Korrekturstands

- [Tauri Windows, Ubuntu, macOS #42440572611](https://github.com/daresan/Minglefield/actions/runs/42440572611):
  **alle drei erfolgreich** inklusive 103 Frontendtests sowie
  Windows-Tauri-Rust-Tests für bestehende `host.local`, unveränderte
  SQLCipher-Zieldateien und **tatsächlich ausgeführte Deinstallation
  auf einem Wegwerfverzeichnis** (28 Tests, keiner fehlgeschlagen).
- [Native Security Windows/macOS #42440335701](https://github.com/daresan/Minglefield/actions/runs/42440335701):
  **beide erfolgreich** – einschließlich des echten installierten
  Alpha-/SQLCipher-/Host-/Login-Integrationspfades und der gesondert
  geprüften PowerShell-Tray-Syntax.
- [Ubuntu Installer Rust + CLI #42440335667](https://github.com/daresan/Minglefield/actions/runs/42440335667):
  **erfolgreich** – native und verschlüsselte lokale Installation.
- [AGENTS security guard #42440572585](https://github.com/daresan/Minglefield/actions/runs/42440572585):
  **erfolgreich**.

## Einmalige portable Paketierung und konkrete Abnahme auf Shadow

Der bestehende Workflow
`.github/workflows/installer-portable-milestone.yml` reagiert nur
auf **diese Markeränderung** und verwendet unverändert
`installer-tauri-packaging.yml`.
Erwartet werden:
`tauri-portable-windows-exe` mit `minglefield-installer-gui.exe`,
`managed-alpha/` und `managed-alpha/Minglefield.exe`;
`tauri-portable-linux-appimage`;
`tauri-portable-macos-app`.
Die vorhandene Windows-Build-Prüfung lädt das hochgeladene portable
Artefakt wieder herunter und verifiziert das vollständige gepinnte
Inventar. Ein unvollständiges Archiv ist keine fertige Abnahmevorlage.

**Manuelle Abnahme auf Shadow (noch offen):** normale Installation ohne
Entwicklerprüfungen; erkannte Alt-DB auswählen oder vorhandene SQLCipher-DB
weiterverwenden; auf Seite 5 vorhandene Daten/Schema und lokale Host-ID
prüfen; auf Seite 6 `Installation durchführen` und `Installieren`.
Sicherstellen, dass die vorhandenen Nutzerrechte bestehen bleiben,
die Anwendung unter der festen Adresse startet, Windows
`Installierte Apps` die Anwendung (nicht Setup) anzeigt,
der Infobereich beide Aktionen bietet und `Beenden` tatsächlich
native App **und eingebettetes Python** entfernt. Die Deinstallation
soll Anwendungsdateien, nicht persönliche DB-Daten entfernen.
**ComfyUI-Jobzustellung bleibt ein ausdrücklich offener separater
Regressionsfall.**

**Produktfreigabe: NEIN. Shadow-Abnahme: OFFEN.**
