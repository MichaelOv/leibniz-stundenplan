# Leibniz Stundenplan

Automatisches System, das taeglich den Vertretungsplan des Leibniz-Gymnasiums Gelsenkirchen mit dem regulaeren Untis-Stundenplan zusammenfuehrt, speziell fuer Klasse 6c. Das Ergebnis ist ein fertiger Tagesplan als JSON-Datei, der im Web-Dashboard angezeigt wird. Bei Aenderungen (Ausfall, Vertretung, Raumwechsel) wird automatisch eine Push-Benachrichtigung aufs Handy geschickt.

## Wie es funktioniert

Das System hat zwei Datenquellen:

1. **Untis-Stundenplan** (`parse_untis.py`): Der regulaere Wochenplan der Klasse wird von einer oeffentlich zugaenglichen HTML-Seite der Schule geladen. Er enthaelt fuer jeden Wochentag und jede Stunde Fach, Lehrkraft und Raum. Dieser Plan aendert sich selten und wird nur neu geladen, wenn sich die Seite geaendert hat.

2. **Vertretungsplan** (`fetch_and_build.py`): Die Schule stellt taeglich ein PDF ueber iServ bereit, das alle Vertretungen, Ausfaelle und Raumänderungen fuer den jeweiligen Tag enthaelt. Der Zugriff erfordert einen Schuelerzugang.

`build_today.py` gleicht dann beide Quellen ab: Fuer jede Stunde aus dem Untis-Plan wird geprueft, ob es im Vertretungsplan einen passenden Eintrag gibt. Wenn ja, wird der Status auf `vertretung`, `frei` oder `info` gesetzt. Das Ergebnis landet in `data/today_6c.json` und `data/tomorrow_6c.json`.

`run_all.py` orchestriert alle Schritte und schickt am Ende, falls es Aenderungen gibt, eine Push-Benachrichtigung via [ntfy.sh](https://ntfy.sh).

```
iServ PDF (Vertretungsplan)  ->  fetch_and_build.py  ->  latest_6c.json
Untis HTML (Wochenplan)      ->  parse_untis.py      ->  untis_6c.json
                                           |
                               build_today.py        ->  today_6c.json / tomorrow_6c.json
                                           |
                                 notify.py           ->  ntfy.sh Push-Benachrichtigung
```

## Voraussetzungen

- **Python 3.10+**
- **iServ-Schuelerzugang** des Leibniz-Gymnasiums. Es muss ein Schuelerzugang sein, da nur damit der Zugriff auf die Vertretungsplan-PDFs funktioniert.
- **ntfy-App** auf dem Handy ([Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy) / [iOS](https://apps.apple.com/app/ntfy/id1625396347)), um Push-Benachrichtigungen zu empfangen

## Installation

### 1. Python-Umgebung einrichten

```bash
cd leibniz-stundenplan
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Die virtuelle Umgebung (`venv/`) isoliert die Abhaengigkeiten vom System-Python. Nach einmaliger Installation muss sie bei jedem neuen Terminal-Start mit `source venv/bin/activate` aktiviert werden, oder man verwendet immer den direkten Pfad `venv/bin/python`.

### 2. Zugangsdaten hinterlegen

Eine Datei `.env` im Projektordner anlegen:

```
ISERV_USER=vorname.nachname
ISERV_PASS=dein-passwort
NTFY_TOPIC=leibniz-stundenplan-6c   # frei waehlen, muss einmalig sein
```

- `ISERV_USER` und `ISERV_PASS` sind die Login-Daten eines Schueleraccounts fuer [gym-leibniz-ge.de/iserv](https://gym-leibniz-ge.de/iserv). Das System meldet sich an, laedt das PDF herunter und meldet sich wieder ab.
- `NTFY_TOPIC` ist ein frei waehlbarer Name fuer den Benachrichtigungskanal (wie ein Gruppenname). Jeder, der dieses Topic in der ntfy-App abonniert, bekommt die Benachrichtigungen. Sicherheitshalber etwas Einzigartiges waehlen, z.B. `leibniz-6c-abc123`. Der Wert ist optional, ohne Angabe wird `leibniz-gym-ge-plan-jeo` verwendet.

### 3. ntfy-App einrichten

1. App installieren und oeffnen
2. Neues Abonnement hinzufuegen: den gewaehlten `NTFY_TOPIC`-Namen eingeben, Server bleibt `ntfy.sh`
3. Fertig, Benachrichtigungen kommen nun automatisch an

### 4. Ersten Lauf testen

```bash
venv/bin/python scripts/run_all.py
```

Erwartete Ausgabe:

```
=== Schritt 1: Vertretungsplan heute laden (2026-05-06) ===
PDF geladen: 84321 bytes
TREFFER: {'klasse': '06c', 'stunde': '3', ...}
Gesamt: 2 Eintraege

=== Schritt 2: Vertretungsplan morgen laden (2026-05-07) ===
...

=== Schritt 3: Untis-Stundenplan laden ===
Tage: ['Montag', 'Dienstag', ...]
Std 1 Montag: [{'fach': 'D', 'lehrer': 'MUS', 'raum': '210'}]
...

=== Schritt 4: Heute ===
Tag: Mittwoch | 6 Stunden | 1 Aenderungen
  Std 3 Deutsch (MUS) 210 [FREI] | Entfall

=== Fertig ===
```

Falls etwas schiefgeht:

```bash
# Login pruefen
venv/bin/python scripts/check_login.py

# PDF-Inhalt ansehen (was das System aus dem PDF liest)
venv/bin/python scripts/debug_pdf.py

# Untis-HTML analysieren
venv/bin/python scripts/debug_untis.py
```

## Dashboard starten

```bash
venv/bin/python server.py
```

Danach im Browser oeffnen: [http://localhost:8080](http://localhost:8080)

Das Dashboard zeigt die Heute/Morgen-Ansicht des Tagesplans. Es liest die JSON-Dateien aus `data/` und aktualisiert sich automatisch alle 5 Minuten. Der "Stand"-Zeitstempel in der Uebersicht zeigt, wann die Daten zuletzt generiert wurden.

Ueber den Refresh-Button im Dashboard kann `run_all.py` auch manuell ausgeloest werden (dauert ca. 30-60 Sekunden).

## Automatisierung

### Cron-Job (Linux/macOS, taeglich 06:00 Uhr)

```bash
crontab -e
```

Folgenden Eintrag hinzufuegen (Pfad anpassen):

```
0 6 * * 1-5 cd /pfad/zu/leibniz-stundenplan && venv/bin/python scripts/run_all.py >> /tmp/stundenplan.log 2>&1
```

Der Job laeuft nur montags bis freitags (`1-5`). Die Ausgabe wird in `/tmp/stundenplan.log` gespeichert und kann dort zur Fehlersuche eingesehen werden.

### GitHub Actions (alternativ, ohne eigenen Server)

Die Datei `.github/workflows/update.yml` enthaelt einen Workflow, der taeglich um 04:00 UTC (06:00 MESZ) ausgefuehrt wird. Er fuehrt `run_all.py` aus und committet die aktualisierten JSON-Dateien zurueck ins Repository, so dass die Daten auch ohne laufenden Server ueber GitHub Pages bereitgestellt werden koennen.

Dazu muessen im GitHub-Repository unter *Settings -> Secrets and variables -> Actions* zwei Secrets angelegt werden:
- `ISERV_USER`
- `ISERV_PASS`

## Benachrichtigungslogik

Das System unterscheidet, ob es eher morgens oder tagsüber laeuft:

- **Vor 09:00 Uhr:** Benachrichtigung bezieht sich auf **heute**, damit man noch vor der Schule weiss, ob etwas ausfaellt.
- **Ab 09:00 Uhr:** Benachrichtigung bezieht sich auf **morgen**, da der heutige Tag bereits laeuft.

Damit keine doppelten Benachrichtigungen verschickt werden, wird ein MD5-Hash des Benachrichtigungsinhalts in `data/last_ntfy_hash_today.txt` bzw. `data/last_ntfy_hash_tomorrow.txt` gespeichert. Nur wenn sich der Inhalt gegenueber der letzten Benachrichtigung geaendert hat, wird eine neue verschickt.

## Konfiguration

### Faechernam anpassen (`data/fach_mapping.json`)

Untis verwendet interne Kuerzel (z.B. `SPSW`), die im Dashboard nicht selbsterklaerend sind. Diese Datei uebersetzt sie in lesbare Namen:

```json
{
  "D":    "Deutsch",
  "M":    "Mathe",
  "SPSW": "Sport Schwimmen"
}
```

Eintraege koennen jederzeit ergaenzt oder geaendert werden, ohne Code-Aenderung.

### Lehrer-Fach-Zuordnung (`data/lehrer_fach.json`)

Manche Vertretungsplan-Eintraege enthalten nur das Lehrerkuerzel, aber kein Fach. Diese Datei ordnet bekannte Lehrerkuerzel einem Fachkuerzel zu, damit das Fach trotzdem angezeigt werden kann:

```json
{
  "EBR": "RE",
  "AVS": "IR"
}
```

Wenn ein Lehrer in einem Eintrag vorkommt, dessen Fach nicht aus dem Untis-Plan herleitbar ist, wird hier nachgeschlagen.

### Klasse oder Schule wechseln

Das System ist auf Klasse 6c des Leibniz-Gymnasiums Gelsenkirchen ausgerichtet. Fuer eine andere Klasse oder Schule muessen folgende Stellen angepasst werden:

| Was | Datei | Variable/Wert |
|---|---|---|
| Zielklasse (Vertretungsplan) | `scripts/fetch_and_build.py` | `TARGET_CLASS = "06c"` |
| Untis-URL | `scripts/parse_untis.py` | `UNTIS_URL` |
| iServ-Basis-URL | `scripts/fetch_and_build.py` | `BASE_URL` |
| ntfy-Topic | `.env` | `NTFY_TOPIC` |

## Abhaengigkeiten

| Paket | Zweck |
|---|---|
| `requests` | HTTP-Anfragen (iServ-Login, Untis, ntfy) |
| `beautifulsoup4` | HTML-Parsing des Untis-Stundenplans |
| `pymupdf` | Text-Extraktion aus dem Vertretungsplan-PDF |
| `python-dotenv` | Laden der Zugangsdaten aus der `.env`-Datei |
| `flask` | HTTP-Server fuer das Web-Dashboard |
