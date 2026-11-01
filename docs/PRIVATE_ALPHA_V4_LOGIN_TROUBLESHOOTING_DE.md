# Private Alpha v4 — Login-Fehler nach Logout diagnostizieren

**Stand:** Lokaler Entwickler-Test, kein Serve, keine externen Benutzer, keine echten Effekte.

Der Benutzer hat erfolgreich 307/307 Tests bestätigt, aber beim manuellen Test gelang eine erneute Passwortanmeldung nach Logout nicht. Der HTTP-Test `test_redeem_logout_then_login_same_password` prüft nun explizit, dass **ein Session-Logout das Passwort nicht löscht** und ein neues Bearer-Token mit denselben Zugangsdaten ausgestellt wird.

Die bisherige UI zeigte für alle Login-Fehler nur `Anmeldung fehlgeschlagen`. Das war zu ungenau, denn `/api/login` unterscheidet:

| Status | Bedeutung | Vorgehen |
| --- | --- | --- |
| **200** | Neues Session-Token erteilt | Automatischer Connect |
| **401** `invalid_credentials` | Benutzername/Passwort nicht akzeptiert; Konto ohne Passwort oder gesperrt möglich | Benutzer-ID prüfen (z. B. `user.daniel`, **nicht** `agent.daniel`), Passwort prüfen; ggf. lokalen Operator-Reset verwenden |
| **429** `try_again_later` | Mehr als fünf zusammengefasste Registrierungs-/Login-/Passwortänderungsversuche innerhalb von 60 Sekunden | Mindestens 60 Sekunden keine weiteren Versuche; dann genau einmal anmelden |
| **403** `local_origin_required` | Origin oder Host passt nicht zum lokalen Gateway | `http://127.0.0.1:8767/` öffnen; Proxy/Tailscale nicht verwenden |
| **400** `invalid_login` | Fehlerhaftes Login-Format | Benutzer-ID und Passwort korrekt eingeben |

**Wichtig:** Zwei verschiedene Identitäten: `user.daniel` ist die Benutzer-ID für die Anmeldung; `agent.daniel` ist keine Benutzeranmeldung, sondern die Agenten-ID.

## Schnelltest nach aktuellem Fix

```powershell
git pull --ff-only
python -B -m unittest discover -s tests/conformance -p "test_private_alpha_password_http.py" -v
python -B -m unittest discover -s tests/conformance -p "test_private_alpha_gateway.py" -v
python -B -m unittest discover -s tests/conformance -p "test_*.py"
git diff --check
git status --short
```

Erwartet: 4 Passwort-HTTP-Tests, 7 Gateway-Tests, **308 Tests insgesamt**. Das ist eine Erwartung, noch keine bestätigte Windows-Baseline.

Im Browser nach einem Gateway-Neustart die Seite mit `Ctrl+F5` neu laden, aber keinen neuen Testbenutzer erzeugen. Unter **Wieder anmelden ohne neue Einladung** die **Benutzer-ID** und das beim Einlösen gesetzte Passwort eingeben. Bei einer Fehlermeldung ausschließlich **Status/Fehlercode** teilen, niemals Passwort, Einladung oder Session-Token.

Ist das Passwort tatsächlich unbekannt, kann der lokale Operator das vorhandene Konto zurücksetzen, ohne Agenten oder Jobs zu löschen:

```powershell
$alphaDb = "$env:LOCALAPPDATA\Minglefield\private-alpha-v4.sqlite"
python -B server/private_alpha_admin.py --db $alphaDb reset-password user.daniel
```

Die Passwort-Eingabe findet verborgen in PowerShell statt und widerruft alte Sessions. Für diese Diagnose ist Reset **nicht** der erste Schritt. Erst den tatsächlichen HTTP-Status prüfen.
