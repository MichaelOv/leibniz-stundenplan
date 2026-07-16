#!/usr/bin/env python3
import json, re, sys
from pathlib import Path
from datetime import datetime, date, timezone
from constants import DAYS_DE

BASE = Path(__file__).resolve().parents[1]

def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def load_fach_map():
    return load_json(BASE / "data" / "fach_mapping.json")

def load_untis(target_date: str) -> dict:
    main = load_json(BASE / "data" / "untis_6c.json")
    valid_from = main.pop("valid_from", None)
    if valid_from and target_date < valid_from:
        prev_path = BASE / "data" / "untis_6c_prev.json"
        if prev_path.exists():
            prev = load_json(prev_path)
            prev.pop("valid_from", None)
            print("Stundenplan: nutze Vorversion (gültig ab " + valid_from + ")")
            return prev
    return main

def load_lehrer_fach():
    return load_json(BASE / "data" / "lehrer_fach.json")

def clean(v):
    return "" if v in ("---", None) else str(v).strip()
def clean_lehrer(v):
    s = clean(v)
    if not s:
        return ""
    parts = s.split()
    return parts[0] if parts else ""

def fach_name(kuerzel: str, fach_map: dict) -> str:
    key = kuerzel.lstrip(".")
    return fach_map.get(key, key)

def resolve_vtg_fach(sub_fach: str, hinweis: str, fach_map: dict) -> str:
    """Fachkürzel einer Vertretung bestimmen, wenn sie das Fach wechselt.
    1. strukturiertes Fach aus dem Vertretungsplan (sub['fach'])
    2. bekanntes Fachkürzel am Zeilenanfang direkt vor 'statt'/'verlegt'
       ('BI statt Do. 9.7. ...'). Bewusst eng: das folgende Schlüsselwort
       verhindert, dass z.B. Namens-Initialen ('M. Müller ...') als Fach
       missdeutet werden.
    Sonst '' (dann bleibt das reguläre Untis-Fach stehen, sicherer Fallback)."""
    if sub_fach:
        return sub_fach.lstrip(".")
    m = re.match(r'\s*([A-ZÄÖÜ]{1,4})\s+(\w+)', hinweis or "")
    if m and m.group(1) in fach_map and m.group(2).lower() in ("statt", "verlegt"):
        return m.group(1)
    return ""

def parse_stunden(raw):
    """'7 - 8 ROM' → ([7,8], 'ROM'), '3' → ([3], ''), '1 - 2 MAT' → ([1,2], 'MAT')"""
    parts = str(raw).replace("-", " ").split()
    stunden, lehrer_raw = [], ""
    for p in parts:
        if p.isdigit():
            stunden.append(int(p))
        else:
            lehrer_raw = p
    return stunden, lehrer_raw

def merge(target_date=None, out_file="today_6c.json", vtg_file="latest_6c.json"):
    FACH = load_fach_map()
    LEHRER_FACH = load_lehrer_fach()

    if not target_date:
        now = datetime.now(timezone.utc)
        target_date = now.strftime("%Y-%m-%d")
        weekday = now.weekday()
    else:
        d = date.fromisoformat(target_date)
        weekday = d.weekday()

    if weekday > 4:
        print("FEHLER: Zieldatum ist ein Wochenende.")
        sys.exit(1)

    day_name = DAYS_DE[weekday]
    if not (BASE / "data" / "untis_6c.json").exists():
        print("FEHLER: untis_6c.json fehlt – bitte parse_untis.py ausführen.")
        sys.exit(1)
    untis = load_untis(target_date)
    vtg_data = load_json(BASE / "data" / vtg_file)
    subs = vtg_data.get("substitutions", [])
    pdf_stand = vtg_data.get("pdf_stand", "")

    sub_by_lehrer = {}
    sub_by_hour   = {}

    parsed_subs = []
    for s in subs:
        stunden_list, lhr_aus_stunde = parse_stunden(clean(s.get("stunde", "")))
        parsed_subs.append({
            "stunden_list": stunden_list,
            "lhr":  clean_lehrer(s.get("lehrer", "")) or lhr_aus_stunde,
            "vtg":  clean(s.get("vertreter", "")),
            "raum": clean(s.get("raum", "")),
            "fach": clean(s.get("fach", "")),
            "text": clean(s.get("text", "")),
        })

    for ps in parsed_subs:
        lhr = ps["lhr"]
        entry = {"lehrer": lhr, "vertreter": ps["vtg"], "raum": ps["raum"], "fach": ps["fach"], "text": ps["text"]}
        for stunde_nr in ps["stunden_list"]:
            h = str(stunde_nr)
            if lhr:
                sub_by_lehrer[(h, lhr)] = entry
            sub_by_hour.setdefault(h, []).append(entry)

    plan = []
    matched_sub_keys = set()

    for stunde_str, days in untis.items():
        stunde = int(stunde_str)
        if stunde == 0:
            continue
        lessons = days.get(day_name, [])
        for lesson in lessons:
            fach_key = lesson["fach"].lstrip(".")
            if fach_key.upper().startswith("NK"):
                continue
            fname = fach_name(fach_key, FACH)
            lehrer = lesson["lehrer"]
            raum   = lesson["raum"]
            entry = {
                "stunde": stunde, "fach": fname, "fach_kurz": fach_key,
                "lehrer": lehrer, "raum": raum,
                "status": "normal", "vertreter": "", "hinweis": ""
            }
            sub_key = (str(stunde), lehrer)
            sub = sub_by_lehrer.get(sub_key)
            if sub:
                matched_sub_keys.add(sub_key)
            else:
                fallbacks = sub_by_hour.get(str(stunde), [])
                fallback = next((f for f in fallbacks if f.get("lehrer", "") == lehrer), None)
                if fallback:
                    sub = fallback
                    matched_sub_keys.add(("HOUR", str(stunde)))

            if sub:
                text = sub.get("text","").lower()
                vtg  = sub.get("vertreter","")
                raum_neu = sub.get("raum","")
                if "frei" in text or "entfall" in text or vtg.lower() in ("frei","entfall"):
                    entry["status"] = "frei"
                    entry["hinweis"] = sub.get("text","") or "Entfall"
                elif vtg and vtg != lehrer:
                    entry["status"] = "vertretung"
                    entry["vertreter"] = vtg
                    if raum_neu:
                        entry["raum"] = raum_neu
                    entry["hinweis"] = sub.get("text","")
                    # Fachwechsel: Originalfach behalten (durchgestrichen), neues zusätzlich
                    neu_fach = resolve_vtg_fach(sub.get("fach",""), sub.get("text",""), FACH)
                    if neu_fach and neu_fach.lstrip(".") != entry["fach_kurz"]:
                        entry["fach_neu"]      = fach_name(neu_fach, FACH)
                        entry["fach_neu_kurz"] = neu_fach
                elif vtg == lehrer:
                    # Lehrer vertritt sich selbst: kein echter Wechsel, nur Raum/Hinweis
                    if raum_neu:
                        entry["raum"] = raum_neu
                    entry["hinweis"] = sub.get("text","")
            plan.append(entry)

    # Nicht gematchte Vertretungen (z.B. Gruppen wie 06ac)
    for ps in parsed_subs:
        lhr  = ps["lhr"]
        vtg  = ps["vtg"]
        text = ps["text"]
        for stunde_nr_u in ps["stunden_list"]:
            fach = ps["fach"]
            raum = ps["raum"]
            h = str(stunde_nr_u)
            key = (h, lhr)
            if key not in matched_sub_keys and ("HOUR", h) not in matched_sub_keys and h:
                if not fach:
                    untis_lektionen = untis.get(h, {}).get(day_name, [])
                    les = next((les for les in untis_lektionen if les["lehrer"] == lhr), None)
                    if les:
                        fach = les["fach"].lstrip(".")
                if not fach:
                    for neighbor in ps["stunden_list"]:
                        nb_lektionen = untis.get(str(neighbor), {}).get(day_name, [])
                        nb_les = next((les for les in nb_lektionen if les["lehrer"] == lhr), None)
                        if nb_les:
                            fach = nb_les["fach"].lstrip(".")
                            if not raum:
                                raum = nb_les.get("raum", "")
                            break
                if not fach:
                    fach = LEHRER_FACH.get(lhr, "")
                # NK-Stunden ohne Vertretung nur anzeigen wenn explizit im Vertretungsplan
                # (text enthält z.B. "entfällt")
                if fach.upper().startswith("NK") and not vtg and "entfall" not in text.lower() and "entfällt" not in text.lower():
                    continue
                fname = fach_name(fach, FACH) if fach else "Gruppe"
                status = "frei" if ("frei" in text.lower() or "entfall" in text.lower() or "entfällt" in text.lower() or vtg.lower() in ("frei","entfall")) else ("vertretung" if vtg else "info")
                extra = {
                    "stunde": stunde_nr_u, "fach": fname, "fach_kurz": fach,
                    "lehrer": lhr, "raum": raum if raum else "\u2014",
                    "status": status,
                    "vertreter": "" if vtg.lower() in ("frei","entfall") else vtg,
                    "hinweis": text or ("Entfall" if status == "frei" else "")
                }
                plan.append(extra)

    plan.sort(key=lambda x: x["stunde"])

    # Doppelte Info-Zeilen zusammenfassen (gleiche Stunde/Fach/Raum/Hinweis,
    # nur anderer Lehrer, z.B. Klassenleitungstag pro Lehrkraft gelistet).
    seen_info = set()
    deduped = []
    for e in plan:
        if e["status"] == "info":
            key = (e["stunde"], e["fach"], e["raum"], e["hinweis"])
            if key in seen_info:
                continue
            seen_info.add(key)
        deduped.append(e)
    plan = deduped

    # "verlegt auf X. Std." – Zielstunde mit korrektem Fach/Lehrer aktualisieren
    plan_by_stunde = {e["stunde"]: e for e in plan}
    for entry in plan:
        if entry["status"] != "frei":
            continue
        m = re.search(r'verlegt\s+auf\s+.*?(\d+)\.\s*std', entry["hinweis"], re.I)
        if not m:
            continue
        ziel = int(m.group(1))
        target = plan_by_stunde.get(ziel)
        if target and target["status"] == "vertretung" and target["vertreter"] == entry["lehrer"]:
            target["fach"]      = entry["fach"]
            target["fach_kurz"] = entry["fach_kurz"]
            target["lehrer"]    = entry["lehrer"]
            target["vertreter"] = ""
            target["hinweis"]   = f"verlegt von {entry['stunde']}. Std."
    output = {
        "date": target_date, "day": day_name, "class": "06c",
        "plan": plan,
        "vtg_count": len([p for p in plan if p["status"] in ("frei","vertretung")]),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pdf_stand": pdf_stand
    }
    out_path = BASE / "data" / out_file
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    unique_stunden = len(set(p["stunde"] for p in plan))
    print("Tag: " + day_name + " | " + str(unique_stunden) + " Stunden | " + str(output["vtg_count"]) + " Aenderungen")
    for p in plan:
        mark    = " [" + p["status"].upper() + "]" if p["status"] != "normal" else ""
        vtg_str = " -> " + p["vertreter"] if p["vertreter"] else ""
        hinweis = " | " + p["hinweis"] if p["hinweis"] else ""
        print("  Std " + str(p["stunde"]) + " " + p["fach"] + " (" + p["lehrer"] + ") " + p["raum"] + mark + vtg_str + hinweis)

if __name__ == "__main__":
    out = sys.argv[2] if len(sys.argv) > 2 else "today_6c.json"
    vtg = sys.argv[3] if len(sys.argv) > 3 else "latest_6c.json"
    merge(sys.argv[1] if len(sys.argv) > 1 else None, out_file=out, vtg_file=vtg)