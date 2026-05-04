Hier das fertige README:

```markdown
# Leibniz Stundenplan ������

Automatisches System zur Zusammenführung von Untis-Stundenplan und Vertretungsplan für Klasse 6c des Leibniz-Gymnasiums. Bei Änderungen wird eine Push-Benachrichtigung via ntfy.sh gesendet.

## Features

- Lädt den Vertretungsplan täglich als PDF und extrahiert relevante Einträge für Klasse 6c
- Parst den Untis-HTML-Stundenplan (inkl. Doppelstunden via rowspan)
- Führt beide Quellen zusammen und erkennt Vertretungen, Ausfälle und Raumänderungen
- Sendet Push-Benachrichtigungen via [ntfy.sh](https://ntfy.sh) — nur bei echten Änderungen
- Stellt den Tagesplan als JSON bereit, abrufbar über ein Web-Dashboard

## Projektstruktur

```
leibniz-stundenplan/
├── scripts/
│   ├── run_all.py          # Hauptscript: führt alle Schritte aus
│   ├── fetch_and_build.py  # Schritt 1: Vertretungsplan (PDF) laden & parsen
│   ├── parse_untis.py      # Schritt 2: Untis-HTML parsen → untis_6c.json
│   ├── build_today.py      # Schritt 3: Tagesplan zusammenführen → today_6c.json
│   ├── notify.py           # ntfy.sh Push-Benachrichtigung
│   ├── check_login.py      # Hilfscript: Login prüfen
│   ├── debug_pdf.py        # Debug: PDF-Inhalt ausgeben
│   ├── debug_untis.py      # Debug: Untis-HTML analysieren
│   └── debug_untis2.py     # Debug: Untis rowspan/colspan analysieren
├── data/
│   ├── fach_mapping.json       # Fachkürzel → Anzeigename (editierbar)
│   ├── untis_6c.json           # Geparster Wochenstundenplan
│   ├── latest_6c.json          # Aktueller Vertretungsplan
│   ├── today_6c.json           # Fertiger Tagesplan (Output)
│   ├── untis_last_modified.txt # Cache: letzter Untis-Abruf
│   └── last_ntfy_hash.txt      # Cache: verhindert doppelte Benachrichtigungen
├── index.html                      # Stundenplan-Übersicht (statisch)
├── vertretungsplan-dashboard.html  # Dashboard für Tagesplan
├── server.py                       # Einfacher HTTP-Server für Dashboard
├── setup_alpine.sh                 # Einrichtungsscript für Alpine Linux
└── requirements.txt
```

## Installation

```bash
# Abhängigkeiten installieren
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Verwendung

```bash
# Manuell ausführen (Zieldatum = nächster Werktag)
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
PDF (Vertretungsplan)  →  fetch_and_build.py  →  latest_6c.json
Untis HTML             →  parse_untis.py      →  untis_6c.json
                                    ↓
                            build_today.py    →  today_6c.json
                                    ↓
                              notify.py       →  ntfy.sh Push
```

## Abhängigkeiten

- `requests` — HTTP-Anfragen
- `beautifulsoup4` — HTML-Parsing (Untis)
- `pdfplumber` — PDF-Parsing (Vertretungsplan)
```