# PlanFlow 6C Prototype

Dieses Repo ist ein startbarer Prototyp für einen automatisch aktualisierten Tagesstundenplan auf Basis von IServ-Vertretungsplan und Untis-Stundenplan.

## Schneller Deploy

### GitHub Pages
1. Neues GitHub-Repository anlegen.
2. `vertretungsplan-dashboard.html` nach `index.html` umbenennen.
3. Dateien hochladen.
4. In GitHub unter **Settings → Pages** den Branch `main` auswählen.
5. Optional die GitHub Action aus `.github/workflows/update.yml` ergänzen.

### Cloudflare Pages
1. Repository mit Cloudflare Pages verbinden.
2. Framework preset: `None`.
3. Build command leer lassen, Output directory `/`.

## Architektur
- `scripts/fetch_and_build.py`: holt PDF + Stundenplan, erkennt Änderungen, schreibt `data/latest.json`.
- `vertretungsplan-dashboard.html`: einfache Oberfläche.
- `.github/workflows/update.yml`: plant alle 5 Minuten einen Refresh.

## Nächster Schritt
Zuerst das konkrete PDF-Layout einmal sauber parsen und Testfälle mit echten Vertretungsdaten für 6C anlegen.
