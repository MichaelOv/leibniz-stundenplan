# Leibniz Stundenplan

Automatisches System zur Zusammenführung von Untis-Stundenplan und Vertretungsplan für Klasse 6c des Leibniz-Gymnasiums. Bei Änderungen wird eine Push-Benachrichtigung via ntfy.sh gesendet.

## Features

- Lädt den Vertretungsplan täglich als PDF und extrahiert relevante Einträge für Klasse 6c
- Parst den Untis-HTML-Stundenplan (inkl. Doppelstunden via rowspan)
- Führt beide Quellen zusammen und erkennt Vertretungen, Ausfälle und Raumänderungen
- Sendet Push-Benachrichtigungen via [ntfy.sh](https://ntfy.sh) — nur bei echten Änderungen
- Stellt den Tagesplan als JSON bereit, abrufbar über ein Web-Dashboard
- Unterstützt Heute/Morgen-Ansicht im Dashboard

## Projektstruktur

```
leibniz-stundenplan/
├── scripts/
│   ├── run_all.py              # Hauptscript: führt alle Schritte aus
│   ├── fetch_and_build.py      # Schritt 1: Vertretungsplan (PDF) laden & parsen
│   ├── parse_untis.py          # Schritt 2: Untis-HTML parsen → untis_6c.json
│   ├── build_today.py          # Schritt 3: Tagesplan zusammenführen
│   ├── notify.py               # ntfy.sh Push-Benachrichtigung
│   ├── check_login.py          # Hilfscript: Login prüfen
│   ├── debug_pdf.py            # Debug: PDF-Inhalt ausgeben
│   ├── debug_untis.py          # Debug: Untis-HTML analysieren
│   └── debug_untis2.py         # Debug: Untis rowspan/colspan analysieren
├── data/
│   ├── fach_mapping.json           # Fachkürzel → Anzeigename (editierbar)
│   ├── untis_6c.json               # Geparster Wochenstundenplan
│   ├── latest_6c.json              # Vertretungsplan heute
│   ├── latest_6c_tomorrow.json     # Vertretungsplan morgen
│   ├── today_6c.json               # Fertiger Tagesplan heute (Output)
│   ├── tomorrow_6c.json            # Fertiger Tagesplan morgen (Output)
│   ├── untis_last_modified.txt     # Cache: letzter Untis-Abruf
│   ├── last_ntfy_hash_today.txt    # Cache: verhindert doppelte Benachrichtigungen
│   └── last_ntfy_hash_tomorrow.txt # Cache: verhindert doppelte Benachrichtigungen
├── index.html          # Web-Dashboard (Heute/Morgen-Ansicht)
├── server.py           # Einfacher HTTP-Server für Dashboard
├── setup_alpine.sh     # Einrichtungsscript für Alpine Linux
└── requirements.txt
```

## Installation

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Credentials in `.env` hinterlegen:

```
ISERV_USER=benutzername
ISERV_PASS=passwort
```

## Verwendung

```bash
# Manuell ausführen
python scripts/run_all.py

# Bestimmtes Datum
python scripts/run_all.py 2026-05-06

# Dashboard starten
python server.py
```

## Cron-Job (täglich 06:00 Uhr)

```bash
crontab -e
# Eintrag:
0 6 * * 1-5 cd /root/leibniz-stundenplan && venv/bin/python scripts/run_all.py
```

## Benachrichtigungslogik

- **Vor 09:00 Uhr:** Benachrichtigung für heute
- **Ab 09:00 Uhr:** Benachrichtigung für morgen
- Doppelte Benachrichtigungen werden per Hash-Vergleich unterdrückt

## Konfiguration

### Fach-Mapping anpassen

`data/fach_mapping.json` enthält die Übersetzung von Untis-Kürzeln zu Anzeigenamen:

```json
{
  "D":    "Deutsch",
  "SPSW": "Sport Schwimmen"
}
```

### ntfy.sh Topic ändern

In `scripts/notify.py`:

```python
NTFY_TOPIC = "dein-eigenes-topic"
```

Topic in der [ntfy App](https://ntfy.sh) abonnieren — fertig.

## Datenfluss

```
PDF (Vertretungsplan heute)   →  fetch_and_build.py  →  latest_6c.json
PDF (Vertretungsplan morgen)  →  fetch_and_build.py  →  latest_6c_tomorrow.json
Untis HTML                    →  parse_untis.py      →  untis_6c.json
                                          ↓
                                  build_today.py     →  today_6c.json / tomorrow_6c.json
                                          ↓
                                    notify.py        →  ntfy.sh Push
```

## Abhängigkeiten

- `requests` — HTTP-Anfragen
- `beautifulsoup4` — HTML-Parsing (Untis)
- `pymupdf` — PDF-Parsing (Vertretungsplan)
- `python-dotenv` — Laden der `.env`-Datei
README
```

Dann committen:

```bash
git add README.md
git commit -m "Update README"
git push
```
