#!/usr/bin/env python3
"""Statistikseite fuer Ausfaelle und Vertretungen der 7c.

Laeuft nur lokal: die Auswertung liest die Git-Historie und braucht daher
das Repository. Registriert im Service-Portal, siehe README.
"""
import json
import subprocess
import sys
from datetime import date, timedelta
from urllib.parse import quote as url_quote
from pathlib import Path

from flask import Flask, Response, request

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE / "scripts"))

from build_today import schulfrei_grund
from statistik import auswerten, historie
from constants import DAYS_DE, expected_schuljahr, halbjahr_grenze, zeitraum_fuer

app = Flask(__name__, static_folder=None)   # kein static_folder: sonst waere .env lesbar

_cache: dict = {}


def _head() -> str:
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=BASE,
                       capture_output=True, text=True)
    return r.stdout.strip()


def gesamthistorie() -> dict:
    """Die komplette Historie, gecacht nach HEAD-Commit.

    Bewusst einmal vollstaendig statt je Zeitraum: das Lesen aus Git ist der
    teure Teil, das Filtern danach kostet nichts. So laedt ein Wechsel des
    Filters nicht erneut.
    """
    key = _head()
    if key not in _cache:
        _cache.clear()
        _cache[key] = historie(mit_klasse=True)
    return _cache[key]


def daten(seit: str, bis: str) -> dict:
    return auswerten({d: plan for d, (plan, _) in gesamthistorie().items()}, seit, bis)


def klassen_im(seit: str, bis: str) -> str:
    """Welche Klasse(n) im Zeitraum tatsaechlich Unterricht hatten.

    Die Klasse steckt in den Daten jedes Tages. Ohne das traegt die Seite
    fuer ein frueheres Schuljahr die heutige Klasse im Titel und behauptet
    damit etwas Falsches. Unterrichtsfreie Tage zaehlen nicht: die
    Umstellung von 6c auf 7c geschah mitten in den Sommerferien.
    """
    gefunden = {kl.lstrip("0") for d, (plan, kl) in gesamthistorie().items()
                if kl and plan and seit <= d <= bis and not schulfrei_grund(d)}
    return ", ".join(sorted(gefunden))


def schuljahre() -> list[str]:
    """Schuljahre mit auswertbaren Daten, neuestes zuerst.

    Unterrichtsfreie Tage zaehlen nicht: das Repo enthaelt auch ein paar
    Staende aus den Sommerferien, die sonst ein Schuljahr vortaeuschen,
    unter dem dann eine leere Seite liegt.
    """
    vorhanden = {expected_schuljahr(date.fromisoformat(d))
                 for d, (plan, _) in gesamthistorie().items()
                 if plan and not schulfrei_grund(d)}
    vorhanden.add(expected_schuljahr(date.today()))
    return sorted(vorhanden, reverse=True)


def zeitraum(sj: str, teil: str) -> tuple[str, str, str]:
    """Zeitraum und Beschriftung. Das Ende wird bei heute gekappt: die
    Pipeline haelt auch kommende Tage vor, die noch nicht stattgefunden
    haben und deshalb nichts zur Statistik beitragen duerfen."""
    heute = date.today()
    if teil == "monat":
        start = max(heute.replace(day=1), zeitraum_fuer(sj, "jahr")[0])
        return start.isoformat(), heute.isoformat(), "Laufender Monat"
    von, bis = zeitraum_fuer(sj, teil)
    titel = {"hj1": "1. Halbjahr", "hj2": "2. Halbjahr"}.get(teil, "Ganzes Schuljahr")
    return von.isoformat(), min(bis, heute).isoformat(), titel


def balken(zeilen, max_wert, einheit=""):
    """Horizontale Balken: Ausfall und Vertretung nebeneinander.

    Zahlen stehen direkt am Balken, die Farbe traegt also nie allein die
    Aussage. Die Tabelle weiter unten enthaelt dieselben Werte.
    """
    if max_wert <= 0:
        max_wert = 1
    out = []
    for name, w in zeilen:
        a = 100 * w["ausfall"] / max_wert
        v = 100 * w["vertretung"] / max_wert
        quote = 100 * w["ausfall"] / w["gesamt"] if w["gesamt"] else 0
        # Beide Serien werden beziffert: der Balken allein traegt die Aussage nie,
        # und ein oranger Balken ohne Zahl war nicht zuzuordnen.
        vtg = f' · {w["vertretung"]} vertr.' if w["vertretung"] else ""
        out.append(f'''<div class="zeile">
  <div class="name" title="{name}">{name}</div>
  <div class="spur">
    <div class="balken">
      <div class="bar bar-a" style="width:{a:.2f}%" title="{w['ausfall']} Ausfälle"></div>
      <div class="bar bar-v" style="width:{v:.2f}%" title="{w['vertretung']} Vertretungen"></div>
    </div>
    <span class="wert"><b>{w['ausfall']}</b>{einheit} ausgef.{vtg}<span class="sub"> · {w['gesamt']} Std · {quote:.0f} %</span></span>
  </div>
</div>''')
    return "\n".join(out)


def tabelle(liste):
    if not liste:
        return '<p class="leer">Keine Ausfälle oder Vertretungen im Zeitraum.</p>'
    zeilen = []
    for datum, p, art in reversed(liste):
        d = date.fromisoformat(datum)
        marke = ('<span class="pill pill-a">Ausfall</span>' if art == "frei"
                 else '<span class="pill pill-v">Vertretung</span>')
        rest = p.get("hinweis") or ""
        if art == "vertretung" and p.get("vertreter"):
            rest = f"→ {p['vertreter']} {rest}".strip()
        zeilen.append(
            f"<tr><td>{marke}</td><td>{DAYS_DE[d.weekday()]}, {d.strftime('%d.%m.%Y')}</td>"
            f"<td>{p.get('stunde','')}.</td><td>{p.get('fach','')}</td>"
            f"<td>{p.get('lehrer','')}</td><td>{rest}</td></tr>")
    return ('<table><thead><tr><th>Art</th><th>Tag</th><th>Std</th><th>Fach</th>'
            '<th>Lehrkraft</th><th>Hinweis</th></tr></thead><tbody>'
            + "".join(zeilen) + "</tbody></table>")


SEITE = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ausfallstatistik</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Crect x='1' y='9' width='3' height='6' fill='%232a78d6'/%3E%3Crect x='6' y='5' width='3' height='10' fill='%23eb6834'/%3E%3Crect x='11' y='2' width='3' height='13' fill='%232a78d6'/%3E%3C/svg%3E">
<style>
  :root {
    color-scheme: light;
    --plane:#f9f9f7; --surface:#fcfcfb;
    --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
    --grid:#e1e0d9; --rand:rgba(11,11,11,.10);
    --ausfall:#2a78d6; --vertretung:#eb6834;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      color-scheme: dark;
      --plane:#0d0d0d; --surface:#1a1a19;
      --ink:#f0efec; --ink2:#c3c2b7; --muted:#898781;
      --grid:#2c2c2a; --rand:rgba(255,255,255,.10);
      --ausfall:#3987e5; --vertretung:#d95926;
    }
  }
  :root[data-theme="dark"] {
    color-scheme: dark;
    --plane:#0d0d0d; --surface:#1a1a19;
    --ink:#f0efec; --ink2:#c3c2b7; --muted:#898781;
    --grid:#2c2c2a; --rand:rgba(255,255,255,.10);
    --ausfall:#3987e5; --vertretung:#d95926;
  }
  * { box-sizing:border-box; }
  body {
    margin:0; padding:24px 16px 64px; background:var(--plane); color:var(--ink);
    font:15px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  }
  .wrap { max-width:960px; margin:0 auto; }
  h1 { font-size:1.5rem; margin:0 0 4px; }
  .unter { color:var(--ink2); margin:0 0 20px; font-size:.9rem; }
  .filter { display:flex; flex-direction:column; gap:8px; margin-bottom:18px; }
  .filterzeile { display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
  .flabel { color:var(--muted); font-size:.78rem; min-width:66px; }
  .warnbox { background:var(--surface); border:1px solid var(--rand);
             border-left:3px solid var(--vertretung); border-radius:8px;
             padding:12px 14px; margin:0 0 18px; color:var(--ink2); font-size:.88rem; }
  .filter a {
    padding:6px 14px; border:1px solid var(--rand); border-radius:999px;
    text-decoration:none; color:var(--ink2); background:var(--surface); font-size:.875rem;
  }
  .filter a[aria-current="page"] { background:var(--ausfall); color:#fff; border-color:transparent; }
  .filter a:focus-visible { outline:2px solid var(--ausfall); outline-offset:2px; }
  .kacheln { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin-bottom:28px; }
  .kachel { background:var(--surface); border:1px solid var(--rand); border-radius:10px; padding:14px 16px; }
  .kachel .zahl { font-size:1.9rem; font-weight:650; letter-spacing:-.02em; }
  .kachel .label { color:var(--ink2); font-size:.8rem; }
  section { background:var(--surface); border:1px solid var(--rand); border-radius:10px; padding:18px 18px 20px; margin-bottom:20px; }
  section > h2 { font-size:1rem; margin:0 0 2px; }
  section > .hinweis { color:var(--muted); font-size:.8rem; margin:0 0 16px; }
  .legende { display:flex; gap:16px; font-size:.8rem; color:var(--ink2); margin-bottom:14px; }
  .legende span { display:flex; align-items:center; gap:6px; }
  .punkt { width:10px; height:10px; border-radius:3px; display:inline-block; }
  .zeile { display:grid; grid-template-columns:minmax(80px,150px) 1fr; gap:12px; align-items:center; margin-bottom:7px; }
  .name { color:var(--ink2); font-size:.85rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .spur { display:flex; align-items:center; min-height:18px; border-left:1px solid var(--grid); padding-left:6px; }
  /* Eigener Container, damit die beiden Segmente eines Balkens nie umbrechen. */
  .balken { display:flex; gap:2px; flex:1 1 auto; min-width:0; }
  .bar { height:16px; border-radius:0 4px 4px 0; }
  .bar-a { background:var(--ausfall); }
  .bar-v { background:var(--vertretung); }
  .wert { font-size:.8rem; color:var(--ink2); margin-left:8px; white-space:nowrap; }
  .wert .sub { color:var(--muted); }
  .wert b { color:var(--ink); font-weight:650; }
  table { width:100%; border-collapse:collapse; font-size:.85rem; }
  th { text-align:left; color:var(--ink2); font-weight:600; border-bottom:1px solid var(--grid); padding:8px 6px; }
  td { padding:8px 6px; border-bottom:1px solid var(--grid); color:var(--ink2); vertical-align:top; }
  td:nth-child(4) { color:var(--ink); }
  .pill { font-size:.72rem; padding:2px 8px; border-radius:999px; color:#fff; white-space:nowrap; }
  .pill-a { background:var(--ausfall); }
  .pill-v { background:var(--vertretung); }
  .leer { color:var(--muted); }
  .fuss { color:var(--muted); font-size:.78rem; margin-top:24px; }
  .tabellenrahmen { overflow-x:auto; }
  @media (max-width:560px) {
    /* Nebeneinander bleibt fuer den Balken zu wenig Platz: Name, Balken und
       Zahl stehen dann untereinander statt in einer gequetschten Zeile. */
    .zeile { grid-template-columns:1fr; gap:3px; margin-bottom:14px; }
    .name { white-space:normal; font-size:.8rem; }
    .spur { flex-wrap:wrap; border-left:none; padding-left:0; }
    .balken { flex:0 0 100%; }
    .bar { border-radius:4px; }
    .wert { width:100%; margin-left:0; }
    table { font-size:.78rem; }
    td, th { padding:7px 5px; }
    .tabellenrahmen { border:1px solid var(--grid); border-radius:8px; }
  }
</style>
</head>
<body>
<div class="wrap">
  <h1>Ausfallstatistik__KLASSE__</h1>
  <p class="unter">__ZEITRAUM__</p>

  <nav class="filter" aria-label="Zeitraum">__FILTER__</nav>
  __HINWEIS__

  <div class="kacheln">
    <div class="kachel"><div class="zahl">__SCHULTAGE__</div><div class="label">Schultage</div></div>
    <div class="kachel"><div class="zahl">__STUNDEN__</div><div class="label">Stunden gesamt</div></div>
    <div class="kachel"><div class="zahl">__AUSFALL__</div><div class="label">Ausgefallen</div></div>
    <div class="kachel"><div class="zahl">__VERTRETUNG__</div><div class="label">Vertreten</div></div>
    <div class="kachel"><div class="zahl">__QUOTE__ %</div><div class="label">Ausfallquote</div></div>
  </div>

  <div class="legende">
    <span><i class="punkt" style="background:var(--ausfall)"></i> Ausfall</span>
    <span><i class="punkt" style="background:var(--vertretung)"></i> Vertretung</span>
  </div>

  <section>
    <h2>Nach Fach</h2>
    <p class="hinweis">Sortiert nach Ausfällen. Dazu die Zahl der Ausfälle, der Vertretungen, die Gesamtstunden und die Ausfallquote.</p>
    __FACH__
  </section>

  <section>
    <h2>Verlauf nach Kalenderwoche</h2>
    <p class="hinweis">Ferienwochen fehlen, dort gab es keinen Unterricht.</p>
    __WOCHE__
  </section>

  <section>
    <h2>Nach Schulstunde</h2>
    <p class="hinweis">Randstunden fallen erfahrungsgemäß am ehesten aus.</p>
    __STUNDE__
  </section>

  <section>
    <h2>Nach Wochentag</h2>
    __TAG__
  </section>

  <section>
    <h2>Alle Vorkommnisse</h2>
    <p class="hinweis">Neueste zuerst. Dieselben Zahlen wie in den Diagrammen.</p>
    <div class="tabellenrahmen">__TABELLE__</div>
  </section>

  <p class="fuss">Quelle: Git-Historie des Stundenplan-Repos, Stand __STAND__.
     Je Tag zählt der zuletzt bekannte Stand. Unterrichtsfreie Tage sind ausgenommen.</p>
</div>
</body>
</html>"""


TEILE = (("jahr", "Ganzes Schuljahr"), ("hj1", "1. Halbjahr"),
         ("hj2", "2. Halbjahr"), ("monat", "Dieser Monat"))


def _wahl() -> tuple[str, str]:
    jahre = schuljahre()
    sj = request.args.get("sj", jahre[0])
    if sj not in jahre:
        sj = jahre[0]
    teil = request.args.get("t", "jahr")
    if teil not in {k for k, _ in TEILE}:
        teil = "jahr"
    return sj, teil


@app.route("/")
def seite():
    sj, teil = _wahl()
    seit, bis, titel = zeitraum(sj, teil)
    e = daten(seit, bis)

    f = e["faecher"]
    gesamt = sum(w["gesamt"] for w in f.values())
    ausfall = sum(w["ausfall"] for w in f.values())
    vertretung = sum(w["vertretung"] for w in f.values())
    quote = 100 * ausfall / gesamt if gesamt else 0

    jahre = schuljahre()
    jahr_links = "".join(
        f'<a href="?sj={url_quote(j, safe="")}&t={teil}"'
        f'{" aria-current=\"page\"" if j == sj else ""}>{j}</a>' for j in jahre)
    teil_links = "".join(
        f'<a href="?sj={url_quote(sj, safe="")}&t={k}"'
        f'{" aria-current=\"page\"" if k == teil else ""}>{b}</a>' for k, b in TEILE)
    links = (f'<div class="filterzeile"><span class="flabel">Schuljahr</span>{jahr_links}</div>'
             f'<div class="filterzeile"><span class="flabel">Zeitraum</span>{teil_links}</div>')

    # Ein Halbjahr, das noch nicht angefangen hat, waere sonst nur eine leere Seite
    hinweis = ""
    erster = min(gesamthistorie(), default="")  # frueheste Aufzeichnung
    if erster and seit < erster <= bis:
        # Sonst sieht ein angebrochen aufgezeichnetes Schuljahr aus wie ein
        # vollstaendiges mit auffallend wenigen Schultagen.
        hinweis = ('<p class="warnbox">Aufzeichnung beginnt erst am '
                   + date.fromisoformat(erster).strftime("%d.%m.%Y")
                   + ". Frühere Tage dieses Zeitraums fehlen.</p>")
    if seit > bis:
        hinweis = (f'<p class="warnbox">Dieser Zeitraum hat noch nicht begonnen. '
                   f'Das 2. Halbjahr {sj} startet am '
                   f'{(halbjahr_grenze(sj) + timedelta(days=1)).strftime("%d.%m.%Y")}.</p>')
    elif e["schultage"] == 0:
        hinweis = '<p class="warnbox">Für diesen Zeitraum liegen keine Daten vor.</p>'


    fach_zeilen = sorted(f.items(), key=lambda x: (-x[1]["ausfall"], x[0]))
    max_fach = max([w["ausfall"] + w["vertretung"] for _, w in fach_zeilen] or [1])

    wochen = sorted(e["wochen"].items())
    max_woche = max([w["ausfall"] + w["vertretung"] for _, w in wochen] or [1])

    stunden = sorted(e["stunden"].items())
    max_std = max([w["ausfall"] + w["vertretung"] for _, w in stunden] or [1])

    tage = sorted(e["wochentage"].items())
    max_tag = max([w["ausfall"] + w["vertretung"] for _, w in tage] or [1])

    # Bei einem Zeitraum, der noch nicht begonnen hat, liegt das bei heute
    # gekappte Ende vor dem Anfang. Dann die geplanten Grenzen zeigen.
    a_von, a_bis = (zeitraum_fuer(sj, teil) if seit > bis
                    else (date.fromisoformat(seit), date.fromisoformat(bis)))
    kl = klassen_im(seit, bis) if seit <= bis else ""
    klasse = (" " + kl) if kl else ""
    html = (SEITE
            .replace("__KLASSE__", klasse)
            .replace("__ZEITRAUM__", f"{titel}: {a_von.strftime('%d.%m.%Y')} "
                                     f"bis {a_bis.strftime('%d.%m.%Y')}")
            .replace("__FILTER__", links)
            .replace("__HINWEIS__", hinweis)
            .replace("__SCHULTAGE__", str(e["schultage"]))
            .replace("__STUNDEN__", str(gesamt))
            .replace("__AUSFALL__", str(ausfall))
            .replace("__VERTRETUNG__", str(vertretung))
            .replace("__QUOTE__", f"{quote:.1f}")
            .replace("__FACH__", balken(fach_zeilen, max_fach))
            .replace("__WOCHE__", balken([(k.replace("2026-", "").replace("2027-", ""), w)
                                          for k, w in wochen], max_woche))
            .replace("__STUNDE__", balken([(f"{k}. Stunde", w) for k, w in stunden], max_std))
            .replace("__TAG__", balken([(DAYS_DE[k], w) for k, w in tage], max_tag))
            .replace("__TABELLE__", tabelle(e["liste"]))
            .replace("__STAND__", date.today().strftime("%d.%m.%Y")))
    return Response(html, mimetype="text/html; charset=utf-8")


@app.route("/daten.json")
def daten_json():
    """Rohdaten, falls man selbst rechnen will."""
    sj, teil = _wahl()
    seit, bis, titel = zeitraum(sj, teil)
    e = daten(seit, bis)
    return Response(json.dumps({
        "schuljahr": sj,
        # seit > bis heisst: der Zeitraum liegt noch in der Zukunft
        "zeitraum": {"teil": teil, "titel": titel, "seit": seit, "bis": bis,
                     "begonnen": seit <= bis},
        "schultage": e["schultage"],
        "faecher": e["faecher"],
        "wochen": e["wochen"],
        "stunden": {str(k): v for k, v in e["stunden"].items()},
        "wochentage": {DAYS_DE[k]: v for k, v in e["wochentage"].items()},
    }, ensure_ascii=False, indent=2), mimetype="application/json; charset=utf-8")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081)
