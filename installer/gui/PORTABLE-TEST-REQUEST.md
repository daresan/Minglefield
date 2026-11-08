# M2.11 — korrigierter portabler Installer für die Shadow-Abnahme (2026-11-08)

**Einmaliger T4-Meilensteinbuild der korrigierten Produktoberfläche.** Diese Datei ist der
bereits vorhandene, auf diesen Pfad begrenzte Build-Marker; keine neuen Workflows,
keine normalen Push-Builds und keine mehrfachen Paketierungsversuche ohne konkret
identifizierten Buildfehler. Dies ist ein unsignierter Alpha-Abnahmebuild, kein Release,
keine Bereitstellung, kein Merge und keine Hostübernahme.

**Branch:** `feat/game-integration-updates`
**Verifizierter Implementierungsstand vor diesem Marker:** `dc2d5db12da324a2a87abeda1fc1d3fd7de0e7af`
**Paket-SHA:** ausschließlich der durch diesen Marker entstehende Workflow-Commit,
nicht ein älterer erfolgreicher Build.
**Altes Artefakt #42410071158:** für die neue Abnahme ungeeignet. Seine GUI enthält
noch die inzwischen entfernten Benutzer-Diagnoseschritte.

## Abzunehmende Produktfunktionen

Die GUI besitzt sechs Seiten; nur Seite 6 enthält die einzige
`Installation durchführen`-Checkbox mit der Schaltfläche `Installieren`.
Keine langen Bestätigungswörter, kein vom Benutzer auszuführender
SQLCipher-, Schreib-, Migrations- oder Starttest, keine separaten
Installationsaktionen. Seite 6 zeigt ausschließlich die gewählten Optionen,
den Bereitschaftsstatus und nach der Installation den tatsächlichen
Abschluss-/Startstatus.

Seite 5 **behält** den vollständigen zuvor vorhandenen Dateneditor:
Anmeldung, Hosts, Effekte, Jobs, Games und sonstige registrierte Tabellen.
Die ausgewählte vorhandene DB wird nur lesend entsperrt; die typisierten
Datenänderungen bleiben bis zum Installieren vorgemerkt. Registrierte
fehlende Schemaobjekte werden angezeigt; die Frage zur
**Schemamigration (Ja/Nein)** entscheidet über die Übernahme der fehlenden
registrierten Objekte in die neue verschlüsselte Datenbank. Die
`mingleadmin`-Einrichtung kommt auf Seite 5 **zusätzlich** zum Editor.

Eine einzige bestätigte Installation führt intern die nötigen Schritte
geordnet aus: verschlüsselte Datenbank erstellen, vorhandene Quelle
ggf. mit den vorgemerkten Zeilen und ausgewählten Schemaobjekten migrieren
oder ein vorhandenes gültiges Ziel übernehmen; offizielles, inventarverifiziertes
Anwendungspaket installieren bzw. nach Sicherung bisheriger managed-Dateien
aktualisieren; `mingleadmin` hinzufügen, wenn er fehlt, **auch wenn andere
User oder Host-Eigentümer bestehen**, ohne deren Berechtigungen oder Passwörter
zu ändern; danach die native `Minglefield.exe` mit der ausgewählten SQLCipher-DB
starten und unabhängig vom Installer laufen lassen.

Ein bereits vorhandener Appordner oder ein vorhandenes SQLCipher-Ziel ergibt
eine Warnung mit **Weiter/Abbruch**, keinen pauschalen Installationsstopp.
Ein gültiges vorhandenes SQLCipher-Ziel wird unverändert übernommen und niemals
durch eine Datenmigration stillschweigend überschrieben. Bereits vorhandene
Anwendungs- und Fremddateien dürfen nicht ungefragt zerstört werden.
Die Test-/Überprüfungsarbeiten gehören ausschließlich in Backend und CI.

Der Nutzerbericht, dass Jobs nach Installation nicht mehr bis zu ComfyUI
gelangen, bleibt ein **separater offener Anwendungs-Regressionsfall**.
Der Korrekturstand zeigt einen echten ComfyUI-Eingang nur mit bestätigter
`prompt_id` und berücksichtigt eng an den lokalen Host gebundene
Administratoren. Vollständige externe ComfyUI-Jobausführung wird mit
diesem Installerpaket **nicht** als CI-abgenommen behauptet.

## Abgeschlossene Vorprüfungen nach MDCI T1–T3

- [Installer GUI frontend #42431455191](https://github.com/daresan/Minglefield/actions/runs/42431455191):
  **success**, inklusive Dateneditor, Schemaentscheidung, neuer
  `mingleadmin`-Eingabeprüfung und genau einer Installationscheckbox.
- [Tauri native/backend #42430616946](https://github.com/daresan/Minglefield/actions/runs/42430616946):
  **success**, Erstellung des Installations-IPC-Auftrags mit echten
  vorgemerkten Zeilenänderungen und ausgewählten Schemaergänzungen.
- [Ubuntu Installer Rust + CLI #42431323228](https://github.com/daresan/Minglefield/actions/runs/42431323228):
  **success**, reale SQLCipher-Kopiertransaktion mit zugleich angewendeter
  Zeilenkorrektur und Schemaergänzung sowie Alpha-Host-/Startintegration.
- [Windows/macOS Native Security #42431323194](https://github.com/daresan/Minglefield/actions/runs/42431323194):
  **beide success**, einschließlich des realen nativen Programm-/SQLCipher-
  und lokalen Host-Integrationspfades.
- [AGENTS security guard #42431455672](https://github.com/daresan/Minglefield/actions/runs/42431455672):
  **success**. Keine Lockerung der Integritäts-/SQLCipher-/Host-Guards.

## Einziger T4-Paketierungslauf und erwartete Artefakte

Die vorhandene
`.github/workflows/installer-portable-milestone.yml` führt nur für diesen
Marker die unveränderte `installer-tauri-packaging.yml` aus.
Erwartet werden:
`tauri-portable-windows-exe` (komplettes Verzeichnis inklusive
`minglefield-installer-gui.exe`, `managed-alpha/` und darin `Minglefield.exe`),
`tauri-portable-linux-appimage` und `tauri-portable-macos-app`.
Windows lädt das hochgeladene Artefakt nochmals herunter und prüft das
gepinnt vollständige Dateiinventar. Eine unvollständige Dateiablage,
fehlendes natives Programm oder ein fehlgeschlagener OS-Runner ist
**kein Abnahmeerfolg**.

## Danach: einmalige Bedienungsabnahme auf Shadow

Der Eigentümer soll ausschließlich die normale **Installation als Benutzer**
durchführen: gegebenenfalls eine vorhandene Quelle auswählen,
Datenbankwerte und gewünschte Schemaergänzungen auf Seite 5 prüfen/bearbeiten,
`mingleadmin` konfigurieren, auf Seite 6 die einzige
`Installation durchführen`-Checkbox setzen und auf **Installieren**
klicken. Bei vorhandenen Zielordnern nur die normale Weiter/Abbruch-Warnung.
Keine Entwicklerproben, keine Testkopien, keine separaten Großbuchstabenfelder,
keine internen Migrations- oder Dateikopiertests.
Erfolg ist ein mit der gewählten DB unabhängig laufendes
Minglefield mit funktionierender normaler Anmeldung, nicht bloß ein
grüner CI-/Startprobe-Status.

**Manuelle Windows-Shadow-Abnahme: OFFEN.**
**Produktivfreigabe und vollständige M2.11-/ComfyUI-/Silent-CLI-Abnahme: OFFEN.**
