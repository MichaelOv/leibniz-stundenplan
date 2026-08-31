#!/usr/bin/env python3
"""Baut die Wochenuebersicht (Mo bis Fr) aus dem Untis-Plan und den
vorhandenen Vertretungsdaten nach data/week_7c.json.

Der regulaere Wochenplan liegt vollstaendig in untis_7c.json vor. Vertretungen
gibt es quellenbedingt nur fuer die Tage, fuer die die Schule ein PDF
veroeffentlicht hat (praktisch heute und morgen). Tage ohne Vertretungsdaten
werden mit has_vertretungsplan=False gekennzeichnet, damit im Frontend kein
falscher Eindruck von Vollstaendigkeit entsteht.
"""
import json, sys
from pathlib import Path
from datetime import datetime, date, timedelta, timezone

from build_today import build_plan, load_json
from constants import DAYS_DE

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"

# Vertretungsdateien, die run_all.py bereitstellt. Zuordnung erfolgt ueber das
# date-Feld in der Datei, nicht ueber die Reihenfolge.
VTG_FILES = ["latest_7c.json", "latest_7c_tomorrow.json"]


def week_start(d: date) -> date:
    """Montag der Woche, die d enthaelt."""
    return d - timedelta(days=d.weekday())


def vtg_file_by_date() -> dict:
    """Mappt Datum -> Vertretungsdateiname fuer die vorhandenen Dateien."""
    mapping = {}
    for name in VTG_FILES:
        data = load_json(DATA / name)
        d = data.get("date")
        if d:
            mapping[d] = name
    return mapping


def build_week(target_date: str | None = None) -> dict:
    if target_date:
        base_day = date.fromisoformat(target_date)
    else:
        base_day = datetime.now(timezone.utc).date()
    monday = week_start(base_day)
    by_date = vtg_file_by_date()

    days = []
    untis_stale = False
    untis_schuljahr = ""
    for offset in range(5):
        d = monday + timedelta(days=offset)
        iso = d.isoformat()
        vtg = by_date.get(iso)
        # Ohne passende Vertretungsdatei einen leeren Platzhalter verwenden,
        # damit build_plan den regulaeren Plan liefert.
        plan_data = build_plan(iso, vtg_file=vtg or "__keine__.json")
        if plan_data is None:
            continue
        untis_stale = untis_stale or plan_data["untis_stale"]
        untis_schuljahr = untis_schuljahr or plan_data["untis_schuljahr"]
        days.append({
            "date": iso,
            "day": DAYS_DE[d.weekday()],
            "plan": plan_data["plan"],
            "vtg_count": plan_data["vtg_count"],
            "has_vertretungsplan": vtg is not None,
            "pdf_stand": plan_data["pdf_stand"],
        })

    return {
        "week_start": monday.isoformat(),
        "class": "07c",
        "days": days,
        "untis_schuljahr": untis_schuljahr,
        "untis_stale": untis_stale,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    out_file = sys.argv[2] if len(sys.argv) > 2 else "week_7c.json"
    if not (DATA / "untis_7c.json").exists():
        print("FEHLER: untis_7c.json fehlt – bitte parse_untis.py ausführen.")
        sys.exit(1)

    week = build_week(target)
    if not week["days"]:
        print("FEHLER: Keine Tage gebaut.")
        sys.exit(1)

    with open(DATA / out_file, "w", encoding="utf-8") as f:
        json.dump(week, f, indent=2, ensure_ascii=False)

    if week["untis_stale"]:
        print("WARNUNG: Untis-Plan ist aus Schuljahr " + week["untis_schuljahr"]
              + ", regulaere Stunden koennen falsch sein.")
    print("Woche ab " + week["week_start"] + ":")
    for tag in week["days"]:
        vtg = "mit Vertretungsplan" if tag["has_vertretungsplan"] else "nur regulaer"
        stunden = len({p["stunde"] for p in tag["plan"]})
        print(f"  {tag['day']:<11} {tag['date']}  {stunden} Std, "
              f"{tag['vtg_count']} Aenderungen ({vtg})")
