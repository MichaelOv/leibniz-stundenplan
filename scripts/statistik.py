#!/usr/bin/env python3
"""Ausfall- und Vertretungsstatistik aus der Git-Historie.

Die Pipeline committet bei jedem Lauf den Stand von heute, morgen und der
Woche. Damit liegt die Vergangenheit vollstaendig im Repository, ohne dass
ein zusaetzliches Archiv noetig waere: fuer jeden Tag wird der Stand aus
dem spaetesten Commit genommen, in dem er vorkommt, also der letzte
bekannte und damit endgueltige.

Laeuft nur lokal (braucht das Git-Repo), nicht in der Pipeline.

    python scripts/statistik.py                    # seit Schuljahresbeginn
    python scripts/statistik.py --seit 2026-09-02
    python scripts/statistik.py --fach Mathe       # nur ein Fach, mit Liste
"""
import argparse
import json
import subprocess
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from constants import DAYS_DE, SCHOOL_YEAR_START_MONTH

BASE = Path(__file__).resolve().parents[1]
DATEIEN = ["data/today_7c.json", "data/tomorrow_7c.json", "data/week_7c.json"]
AUSFALL, VERTRETUNG = "frei", "vertretung"


def schuljahr_beginn(heute: date) -> date:
    """Erster August des laufenden Schuljahrs."""
    jahr = heute.year if heute.month >= SCHOOL_YEAR_START_MONTH else heute.year - 1
    return date(jahr, SCHOOL_YEAR_START_MONTH, 1)


def _blobs(anfragen: list[str]) -> list[bytes | None]:
    """Liest viele Git-Objekte in einem Rutsch.

    Bewusst binaer: die Laengenangabe im Kopf einer cat-file-Antwort zaehlt
    Bytes. Im Textmodus verschiebt schon ein einziger Umlaut den Versatz,
    und ab da werden stillschweigend falsche Objekte zugeordnet.
    """
    p = subprocess.run(["git", "cat-file", "--batch"], cwd=BASE,
                       input="\n".join(anfragen).encode(), capture_output=True)
    roh, inhalte, pos = p.stdout, [], 0
    for _ in anfragen:
        ende = roh.find(b"\n", pos)
        if ende == -1:
            break
        kopf = roh[pos:ende]
        if kopf.endswith(b" missing"):
            inhalte.append(None)
            pos = ende + 1
        else:
            laenge = int(kopf.split()[-1])
            inhalte.append(roh[ende + 1:ende + 1 + laenge])
            pos = ende + 1 + laenge + 1
    return inhalte


def historie(seit: str) -> dict[str, list]:
    """Datum -> Plan, je aus dem spaetesten Commit, der den Tag enthaelt."""
    log = subprocess.run(
        ["git", "log", "--reverse", "--format=%H %ct", f"--since={seit}"],
        cwd=BASE, capture_output=True, text=True, check=True)
    commits = [z.split() for z in log.stdout.strip().splitlines()]
    if not commits:
        return {}

    inhalte = _blobs([f"{c}:{f}" for c, _ in commits for f in DATEIEN])
    stand, i = {}, 0
    for _, ts in commits:
        ts = int(ts)
        for _ in DATEIEN:
            b = inhalte[i] if i < len(inhalte) else None
            i += 1
            if not b:
                continue
            try:
                d = json.loads(b.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            tage = d.get("days") if isinstance(d.get("days"), list) else [d]
            for t in tage:
                datum = t.get("date")
                if datum and isinstance(t.get("plan"), list):
                    if datum not in stand or ts >= stand[datum][0]:
                        stand[datum] = (ts, t["plan"])
    return {datum: plan for datum, (_, plan) in stand.items()}


def auswerten(stand: dict, seit: str, bis: str) -> dict:
    """Zaehlt je Fach Stunden, Ausfaelle und Vertretungen.

    Reine Funktion ohne Git, damit sie sich testen laesst.
    """
    faecher = defaultdict(lambda: {"gesamt": 0, "ausfall": 0, "vertretung": 0})
    liste, tage = [], set()
    for datum in sorted(stand):
        if not (seit <= datum <= bis):
            continue
        plan = stand[datum]
        if plan:
            tage.add(datum)
        for p in plan:
            fach = p.get("fach") or "(ohne Fach)"
            status = p.get("status")
            f = faecher[fach]
            f["gesamt"] += 1
            if status == AUSFALL:
                f["ausfall"] += 1
                liste.append((datum, p, AUSFALL))
            elif status == VERTRETUNG:
                f["vertretung"] += 1
                liste.append((datum, p, VERTRETUNG))
    return {"faecher": dict(faecher), "liste": liste, "schultage": len(tage)}


def _zeile(name, w, breite):
    quote = 100 * w["ausfall"] / w["gesamt"] if w["gesamt"] else 0
    vtg = w.get("vertretung", 0)
    return (f"  {name:<{breite}} {w['gesamt']:>6} {w['ausfall']:>8} "
            f"{vtg:>12} {quote:>7.1f} %")


def ausgeben(e: dict, fach_filter: str = "") -> None:
    faecher = e["faecher"]
    if fach_filter:
        faecher = {k: v for k, v in faecher.items() if k.lower() == fach_filter.lower()}
        if not faecher:
            print(f"Kein Fach '{fach_filter}' in den Daten. Vorhanden: "
                  + ", ".join(sorted(e["faecher"])))
            return

    breite = max([len(k) for k in faecher] + [len("Fach")])
    print(f"Ausgewertete Schultage: {e['schultage']}")
    print()
    print(f"  {'Fach':<{breite}} {'Stunden':>6} {'Ausfall':>8} {'Vertretung':>12} {'Quote':>9}")
    print("  " + "-" * (breite + 39))
    for name, w in sorted(faecher.items(), key=lambda x: (-x[1]["ausfall"], x[0])):
        print(_zeile(name, w, breite))

    gesamt = {"gesamt": sum(w["gesamt"] for w in faecher.values()),
              "ausfall": sum(w["ausfall"] for w in faecher.values()),
              "vertretung": sum(w["vertretung"] for w in faecher.values())}
    print("  " + "-" * (breite + 39))
    print(_zeile("Summe", gesamt, breite))

    liste = [x for x in e["liste"]
             if not fach_filter or (x[1].get("fach") or "").lower() == fach_filter.lower()]
    if liste:
        print()
        print("Einzelne Vorkommnisse")
        for datum, p, art in liste:
            d = date.fromisoformat(datum)
            marke = "Ausfall   " if art == AUSFALL else "Vertretung"
            rest = p.get("hinweis") or ""
            if art == VERTRETUNG and p.get("vertreter"):
                rest = f"-> {p['vertreter']} {rest}".strip()
            print(f"  {marke} {DAYS_DE[d.weekday()]:<11}{d.strftime('%d.%m.%Y')}  "
                  f"{p['stunde']}. Std  {p.get('fach','')} ({p.get('lehrer','')})  {rest}".rstrip())


def main(argv=None) -> int:
    heute = date.today()
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seit", default=schuljahr_beginn(heute).isoformat(),
                    help="Startdatum (Vorgabe: Beginn des laufenden Schuljahrs)")
    ap.add_argument("--bis", default=heute.isoformat(), help="Enddatum (Vorgabe: heute)")
    ap.add_argument("--fach", default="", help="nur dieses Fach auswerten")
    a = ap.parse_args(argv)

    stand = historie(a.seit)
    if not stand:
        print("Keine Daten in der Git-Historie fuer diesen Zeitraum.")
        return 1
    print(f"Zeitraum {a.seit} bis {a.bis}")
    ausgeben(auswerten(stand, a.seit, a.bis), a.fach)
    return 0


if __name__ == "__main__":
    sys.exit(main())
