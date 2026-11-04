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
from build_today import schulfrei_grund
from constants import DAYS_DE, SCHOOL_YEAR_START_MONTH, expected_schuljahr, zeitraum_fuer

BASE = Path(__file__).resolve().parents[1]
AUSFALL, VERTRETUNG = "frei", "vertretung"

# Die Klasse steckt im Dateinamen und wechselt mit dem Schuljahr
# (data/today_6c.json, spaeter data/today_7c.json). Fest verdrahtet waeren
# die frueheren Schuljahre unsichtbar, obwohl sie im Repo liegen.
MUSTER = ("data/today_*.json", "data/tomorrow_*.json", "data/week_*.json")


def plan_dateien() -> list[str]:
    """Alle Plandateien, die es in der Historie je gegeben hat."""
    # Ohne --diff-filter: die 7c-Dateien sind durch Umbenennung entstanden
    # und tauchen deshalb nie als Neuanlage auf.
    r = subprocess.run(["git", "log", "--all", "--pretty=format:", "--name-only",
                        "--"] + list(MUSTER),
                       cwd=BASE, capture_output=True, text=True, check=True)
    return sorted({z.strip() for z in r.stdout.splitlines() if z.strip()})


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


def historie(seit: str = "", mit_klasse: bool = False) -> dict:
    """Datum -> Plan, je aus dem spaetesten Commit, der den Tag enthaelt.

    Ohne seit wird die gesamte Historie gelesen. Das ist noetig, um auch
    frueheren Schuljahren nachzugehen, deren Daten unter dem Dateinamen der
    damaligen Klasse liegen.

    Mit mit_klasse steht je Tag (plan, klasse) statt nur plan. Die Klasse
    gehoert an den Tag, nicht an den Zeitraum: die Umstellung von 6c auf 7c
    geschah mitten in den Sommerferien.
    """
    befehl = ["git", "log", "--reverse", "--format=%H %ct"]
    if seit:
        befehl.append(f"--since={seit}")
    log = subprocess.run(befehl, cwd=BASE, capture_output=True, text=True, check=True)
    commits = [z.split() for z in log.stdout.strip().splitlines()]
    if not commits:
        return {}

    dateien = plan_dateien()
    inhalte = _blobs([f"{c}:{f}" for c, _ in commits for f in dateien])
    stand, i = {}, 0
    for _, ts in commits:
        ts = int(ts)
        for _ in dateien:
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
                        # In week_*.json steht die Klasse nur im Dokument,
                        # nicht je Tag.
                        klasse = t.get("class") or d.get("class", "")
                        stand[datum] = (ts, t["plan"], klasse)
    if mit_klasse:
        return {datum: (plan, kl) for datum, (_, plan, kl) in stand.items()}
    return {datum: plan for datum, (_, plan, _kl) in stand.items()}


def auswerten(stand: dict, seit: str, bis: str) -> dict:
    """Zaehlt je Fach Stunden, Ausfaelle und Vertretungen.

    Reine Funktion ohne Git, damit sie sich testen laesst.
    """
    leer = lambda: {"gesamt": 0, "ausfall": 0, "vertretung": 0}
    faecher = defaultdict(leer)
    wochen = defaultdict(leer)        # Kalenderwoche -> Verlauf
    wochentage = defaultdict(leer)    # 0 bis 4
    stunden = defaultdict(leer)       # Stundennummer
    liste, tage = [], set()
    for datum in sorted(stand):
        if not (seit <= datum <= bis):
            continue
        # Ferientage tragen in alten Staenden noch den reguaeren Plan: die
        # Ferien wurden erst spaeter in schulfrei.json gepflegt. Ohne diese
        # Pruefung zaehlen sie als Schultage voller stattgefundener Stunden.
        if schulfrei_grund(datum):
            continue
        plan = stand[datum]
        if plan:
            tage.add(datum)
        d = date.fromisoformat(datum)
        jahr, kw, _ = d.isocalendar()
        schluessel = [faecher[p.get("fach") or "(ohne Fach)"] for p in plan]
        for p, f in zip(plan, schluessel):
            status = p.get("status")
            eimer = [f, wochen[f"{jahr}-KW{kw:02d}"], wochentage[d.weekday()],
                     stunden[p.get("stunde", 0)]]
            for e in eimer:
                e["gesamt"] += 1
            if status == AUSFALL:
                for e in eimer:
                    e["ausfall"] += 1
                liste.append((datum, p, AUSFALL))
            elif status == VERTRETUNG:
                for e in eimer:
                    e["vertretung"] += 1
                liste.append((datum, p, VERTRETUNG))
    return {"faecher": dict(faecher), "liste": liste, "schultage": len(tage),
            "wochen": dict(wochen), "wochentage": dict(wochentage),
            "stunden": dict(stunden)}


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
    ap.add_argument("--halbjahr", choices=("1", "2"),
                    help="nur das erste oder zweite Schulhalbjahr")
    ap.add_argument("--schuljahr", metavar="JJJJ/JJ",
                    help="ein ganzes Schuljahr, z.B. 2025/26")
    a = ap.parse_args(argv)

    if a.schuljahr or a.halbjahr:
        sj = a.schuljahr or expected_schuljahr(heute)
        teil = "hj" + a.halbjahr if a.halbjahr else "jahr"
        von, bis = zeitraum_fuer(sj, teil)
        a.seit, a.bis = von.isoformat(), min(bis, heute).isoformat()

    if a.seit > a.bis:
        print(f"Dieser Zeitraum beginnt erst am {a.seit}.")
        return 1
    stand = historie(a.seit)
    if not stand:
        print("Keine Daten in der Git-Historie fuer diesen Zeitraum.")
        return 1
    print(f"Zeitraum {a.seit} bis {a.bis}")
    ausgeben(auswerten(stand, a.seit, a.bis), a.fach)
    return 0


if __name__ == "__main__":
    sys.exit(main())
