# SEC-01: Session- und Autoritätsgenerationen (lokale Simulation)

**CRITICAL / OPEN — keine echten Effekte, kein Serve.** Auf dem zuletzt vom Betreiber bestätigten Stand waren 335 Tests erfolgreich. Die zehn vorherigen Remote-Precommit-Tests (erwartet 345) wurden noch nicht vom Betreiber bestätigt. Dieser Schritt ergänzt neun Tests; nach erfolgreicher Validierung wären **354** Tests zu erwarten.

## Implementierung

`server/sec01_epoch_bound_proof_sim.py` ergänzt den bisherigen Proof um eine HMAC-authentifizierte lokale Hülle mit dem Hash der **konkret ausstellenden Session** und einem Snapshot von monotonen Autoritätsgenerationen. SQLite-Trigger schreiben Änderungen an Alpha-Session, Benutzer, Agent, Grant, Host und Agent-Host-Zuordnung innerhalb derselben Transaktion in `alpha_sec01_epochs`. Das schließt im simulierten Online-Precheck die offensichtliche Revoke/Regrant-ABA-Lücke: Ein widerrufener und erneut gewährter Grant hat eine andere Generation, auch wenn `revoked` wieder null ist. Gleiches gilt für Host-Deaktivierung und Reaktivierung.

Der Precheck verifiziert Hüllen-MAC, ursprüngliche Session (nicht widerrufen, nicht abgelaufen), Snapshot und den bisherigen Online-Autoritätszustand. Ein späterer Login mit einem neuen Session-Token darf einen alten Proof nicht wiederbeleben.

## Begrenzungen

- Dies ist ein **Precheck**, keine atomare entfernte Effekt-Zulassung. Zwischen Generationenprüfung und dem separaten Online-Precheck und zwischen Online-Precheck und einem späteren Executor-Commit können Änderungen eintreten. Ein positives Ergebnis darf **nicht** zu einem echten Effekt führen.
- Bestehende Datensätze werden bei Installation der Trigger nicht rückwirkend mit Generationen initialisiert; unveränderte Bestandsdaten erhalten Snapshot 0. Jede folgende Änderung erzeugt eine Generation ab 1. Das ist für diese lokale Simulation ausreichend, aber keine migrationsfeste Produktionssemantik.
- Der Nachweis bleibt ein symmetrischer HMAC-Testnachweis. Ein kompromittierter oder nicht vertrauenswürdiger Executor könnte damit nicht sicher abgegrenzt werden. Kein externes Trust-Modell.
- Das Snapshot enthält die konkrete Session und aktuelle Rollen/Grant-/Host-Identitäten. Diese Form ist **kein** veröffentlichtes MAP-Wire-Format.
- Session-Ablauf und Widerruf werden im Check geprüft; es wird keine reale laufende Arbeit abgebrochen.
- Für die finale Lösung müssen Generationenprüfung und tatsächlicher Effekt-Commit **in einer durch den Effekt-Eigentümer kontrollierten Transaktion** verbunden werden. Falls Autorität und Executor getrennt sind, muss der endgültige Sicherheitsvertrag den verbleibenden verteilten Widerrufs-Race explizit behandeln.

## Windows-Validierung

```powershell
git pull --ff-only
python -B -m unittest discover -s tests/conformance -p "test_sec01_remote_precommit_sim.py" -v
python -B -m unittest discover -s tests/conformance -p "test_sec01_epoch_bound_proof.py" -v
python -B -m unittest discover -s tests/conformance -p "test_*.py"
python -B tests/conformance/validate_map_v01.py
git diff --check
git status --short
```

Die Tests benötigen weder neue Alpha-Konten noch einen Gateway-Neustart. Die Änderung ist ausschließlich ein isolierter SEC-01-Testbaustein.
