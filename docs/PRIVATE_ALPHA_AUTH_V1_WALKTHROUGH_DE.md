# Private Alpha Auth v1 — Windows-Anleitung für Einladungen und Login

**Nur lokaler Simulationstest. Nicht über Tailscale Serve/Funnel freigeben.** Es gibt noch keine Registrierungsoberfläche für externe Alpha-Tester.

## Ganz wichtig: Zwei verschiedene Codes

- **Einladungscode:** Wird durch `invite` erzeugt. Er wird **ausschließlich in der PowerShell** beim Befehl `redeem` eingegeben. Er ist einmalig und standardmäßig eine Stunde gültig.
- **Session-Token:** Wird **erst nach erfolgreichem `redeem`** angezeigt. **Nur dieser** gehört in das Eingabefeld der Alpha-Webseite. Die Session läuft nach 15 Minuten ab.
- Der Einladungscode ist **kein Login-Token**. Mit ihm im Browser entsteht erwartungsgemäß `401 unauthorized`.

## Schritt 1: Zwei PowerShell-Fenster öffnen

Öffne **Fenster A (Server)** und **Fenster B (Administration)**. Beide müssen im Minglefield-Repository stehen:

```powershell
cd "C:\Users\Shadow\Documents\Codex\shared\Minglefield\PUBLIC\Minglefield"
```

**In BEIDEN Fenstern** dieselbe Datenbankvariable setzen. PowerShell-Variablen werden zwischen Fenstern nicht übertragen:

```powershell
$alphaDb = "$env:LOCALAPPDATA\Minglefield\private-alpha.sqlite"
New-Item -ItemType Directory -Force (Split-Path $alphaDb) | Out-Null
Write-Host $alphaDb
```

Die Datenbank liegt absichtlich außerhalb des Git-Repositories.

## Schritt 2: Gateway in PowerShell-Fenster A starten

```powershell
python -B server/private_alpha_gateway.py --auth-db $alphaDb --port 8767
```

Lasse **Fenster A geöffnet**. Es wird durch den Server blockiert – das ist normal. Im Auth-v1-Modus gibt der Server **keinen** Login-Token aus. Wenn `agent.demo` statt eines registrierten Agenten erscheint, läuft wahrscheinlich noch der ältere Demo-Modus ohne `--auth-db`. Diesen mit `Ctrl+C` beenden.

## Schritt 3: Einladung in PowerShell-Fenster B erstellen

```powershell
python -B server/private_alpha_admin.py --db $alphaDb invite user.alice
```

Die Ausgabe enthält eine Zeile `Invitation secret: ...`. Den dort angezeigten Einladungscode vorübergehend sicher aufbewahren. **Nicht in das Token-Feld der Webseite einfügen.**

## Schritt 4: Einladung in PowerShell-Fenster B einlösen

```powershell
python -B server/private_alpha_admin.py --db $alphaDb redeem --agent agent.alice
```

Jetzt erscheint die interaktive Aufforderung:

```text
Invitation secret:
```

Hier den **Einladungscode aus Schritt 3** einfügen und **Enter** drücken. Während der Eingabe erscheinen absichtlich **keine Zeichen und keine Sternchen** (`getpass`).

Erst danach erscheint bei Erfolg:

```text
Session bearer (local test only; never share): [NEUER SESSION-TOKEN]
```

**Nur diesen neuen Session-Token im Browser verwenden.** Er wird nicht später erneut angezeigt.

## Schritt 5: Webseite verwenden

1. Im Browser `http://127.0.0.1:8767/` öffnen.
2. Im Feld **Session-Token** den `Session bearer` aus Schritt 4 einfügen.
3. `Connect` klicken. Erwartet: `agents.status = 200`, Benutzer `user.alice`, Agent `agent.alice`.
4. `Simulate action` klicken. Erwartet: HTTP **201** mit `state: "simulated_no_effect"`.
5. Wieder `Connect` klicken, um die persistent gespeicherte Jobliste zu prüfen.

Das Browser-Token bleibt nur im Speicher dieses Tabs. Nach einem Reload muss es neu eingegeben werden, sofern es nicht abgelaufen ist.

## Zweiten Benutzer testen

In **Fenster B**:

```powershell
python -B server/private_alpha_admin.py --db $alphaDb invite user.bob
python -B server/private_alpha_admin.py --db $alphaDb redeem --agent agent.bob
```

Beim zweiten Befehl den **neuen** Einladungscode eingeben. Danach mit dem **neuen** Session-Token in einem separaten Browserfenster testen. `user.bob` darf keine Jobs von `user.alice` sehen.

## Fehler und häufige Stolpersteine

| Beobachtung | Ursache und Vorgehen |
| --- | --- |
| `401 unauthorized` unmittelbar nach `Connect` | Einladungscode statt Session-Token, Tippfehler, falsche Datenbank, falscher Gateway-Modus oder widerrufene Session. |
| Erst HTTP 200/201, später `401` | Wahrscheinlich **15-Minuten-Ablauf** oder Widerruf. Die Antwort allein verrät den genauen Grund nicht. |
| `Invitation secret:` bleibt scheinbar leer | Das ist die **unsichtbare** Eingabe. Code einfügen und Enter drücken. |
| `Invitation invalid, used, expired or agent occupied` | Einladung falsch, abgelaufen oder bereits eingelöst; oder die Agenten-ID existiert schon. |
| Session-Token verloren oder abgelaufen | Auth v1 bietet noch **keine normale Wiederanmeldung und keinen Refresh**. Für einen neuen isolierten Test einen **neuen** Benutzernamen und eine **neue** Agenten-ID verwenden. Nicht die Datenbank unüberlegt löschen. |
| Gateway findet einen gerade erstellten Benutzer nicht | `$alphaDb` **in beiden PowerShell-Fenstern** vergleichen. `--auth-db $alphaDb` muss beim Serverstart gesetzt sein. |
| Browser zeigt `agent.demo` | Alter Demo-Modus aktiv. Server mit `Ctrl+C` beenden und mit `--auth-db` neu starten. |
| HTTP 429 | Pro Benutzer sind höchstens fünf verschiedene simulierte Jobs vorgesehen. |

Zum vollständigen Sperren von `user.alice` lokal in Fenster B:

```powershell
python -B server/private_alpha_admin.py --db $alphaDb disable-user user.alice
```

Das widerruft die Sessions des Benutzers. Es gibt derzeit keinen Reaktivierungsbefehl.

## Grenzen

Die dokumentierten 278/278 Conformance-Tests und der erfolgreiche manuelle Login belegen einen lokalen Auth-v1-Simulationstest, **keine Freigabe für echte Benutzer, Tailscale Serve oder ComfyUI-Effekte**. Der Operator muss die Einladung noch selbst einlösen; für Freunde wird später ein eigenes, einladungsgebundenes Browser-Onboarding entwickelt. Keine Einladungscodes, Session-Tokens oder Datenbanken ins öffentliche Git-Repository übernehmen.
