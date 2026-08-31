#!/usr/bin/env python3
import re, requests, json, sys, shutil
from bs4 import BeautifulSoup
from pathlib import Path
from constants import DAYS_DE

UNTIS_URL = "https://leibniz-gymnasium.net/files/stpl/Kla1A_07c.htm"

def extract_schuljahr(html_text: str) -> str | None:
    """Schuljahr aus dem Untis-HTML lesen ('2025/26'). None, wenn nicht gefunden."""
    m = re.search(r'(20\d{2}/\d{2})', html_text)
    return m.group(1) if m else None

def extract_valid_from(html_text: str) -> str | None:
    m = re.search(r'\(ab (\d{1,2}\.\d{1,2}\.\d{2,4})\)', html_text)
    if not m:
        return None
    day, month, year = m.group(1).split(".")
    if len(year) == 2:
        year = "20" + year
    return f"{year}-{int(month):02d}-{int(day):02d}"

def parse_untis():
    r = requests.get(UNTIS_URL, timeout=30)
    r.raise_for_status()
    r.encoding = r.apparent_encoding
    valid_from = extract_valid_from(r.text)
    if valid_from:
        print("Gültig ab: " + valid_from)
    schuljahr = extract_schuljahr(r.text)
    if schuljahr:
        print("Schuljahr laut Untis: " + schuljahr)
    soup = BeautifulSoup(r.content, "html.parser")
    tables = soup.find_all("table")
    if len(tables) < 2:
        print("FEHLER: Untis-HTML hat unerwartete Struktur (zu wenige Tabellen).")
        sys.exit(1)
    main_rows = tables[1].find_all("tr")

    # Tag-Startspalten aus Header
    day_start_cols = {}
    col = 0
    for cell in main_rows[0].find_all(["td","th"]):
        cs = int(cell.get("colspan", 1))
        txt = cell.get_text(strip=True)
        if cs == 12 and txt in DAYS_DE.values():
            day_start_cols[col] = txt
        col += cs
    all_days = [day_start_cols[c] for c in sorted(day_start_cols.keys())]
    print("Tage: " + str(all_days))

    # Stunden-Tabellen-Index
    hour_table_idx = {}
    for i, table in enumerate(tables):
        txt = table.get_text(strip=True)
        if txt.isdigit() and 1 <= int(txt) <= 9:
            hour_table_idx[int(txt)] = i
    sorted_hours = sorted(hour_table_idx.items())

    # Tracke welche Tage in der nächsten Stunde durch rs=4 belegt sind
    day_skip_next = {d: False for d in all_days}

    timetable = {}

    for h_pos, (stunde, h_idx) in enumerate(sorted_hours):
        next_h_idx = sorted_hours[h_pos+1][1] if h_pos+1 < len(sorted_hours) else len(tables)

        # Sub-Tabellen zwischen dieser und nächster Stunden-Tabelle
        # ALLE zählen, auch leere
        slot_tables = []
        for i in range(h_idx+1, next_h_idx):
            flat = [v for rr in tables[i].find_all("tr")
                    for v in [c.get_text(strip=True) for c in rr.find_all(["td","th"])]]
            slot_tables.append(flat)

        # Freie Tage für diese Stunde
        free_days = [d for d in all_days if not day_skip_next[d]]

        # Sub-Tabellen den freien Tagen zuweisen (1:1, inkl. leerer)
        if stunde not in timetable:
            timetable[stunde] = {}
        for i, day in enumerate(free_days):
            if i >= len(slot_tables):
                break
            flat = [v for v in slot_tables[i] if v]  # leere Strings rausfiltern
            lessons = []
            for j in range(0, len(flat)-2, 3):
                fach, lehrer, raum = flat[j], flat[j+1], flat[j+2]
                if fach and not fach.upper().startswith("NK"):
                    lessons.append({"fach": fach, "lehrer": lehrer, "raum": raum})
            if lessons:
                timetable[stunde][day] = lessons
                print("Std " + str(stunde) + " " + day + ": " + str(lessons))

        # Jetzt Haupt-Zeile lesen: rs=4 bei cs=12 → dieser Tag in NÄCHSTER Stunde belegt
        day_skip_next = {d: False for d in all_days}
        stunden_row = None
        for row in main_rows:
            cells_r = row.find_all(["td","th"])
            if cells_r and cells_r[0].get_text(strip=True) == str(stunde):
                stunden_row = row
                break

        if stunden_row:
            cur_col = 0
            first = True
            for cell in stunden_row.find_all(["td","th"]):
                cs = int(cell.get("colspan", 1))
                rs = int(cell.get("rowspan", 1))
                if first:
                    first = False
                    cur_col += cs
                    continue
                if cs == 12:
                    for dcol, day in day_start_cols.items():
                        if dcol <= cur_col < dcol + 13:
                            if rs >= 4:
                                day_skip_next[day] = True
                                if day in timetable[stunde]:
                                    next_stunde = stunde + 1
                                    if next_stunde not in timetable:
                                        timetable[next_stunde] = {}
                                    timetable[next_stunde][day] = timetable[stunde][day]
                                    print("Std " + str(next_stunde) + " " + day + " (Doppelstunde): " + str(timetable[stunde][day]))
                            break
                cur_col += cs

    return timetable, valid_from, schuljahr

if __name__ == "__main__":
    tt, valid_from, schuljahr = parse_untis()
    out = Path(__file__).resolve().parents[1] / "data" / "untis_7c.json"
    out.parent.mkdir(exist_ok=True)
    # Backup: wenn valid_from sich geändert hat, alten Plan sichern
    if out.exists() and valid_from:
        old = json.loads(out.read_text(encoding="utf-8"))
        if old.get("valid_from") != valid_from:
            prev = out.parent / "untis_7c_prev.json"
            shutil.copy2(out, prev)
            print("Backup gespeichert: " + str(prev))
    output = {}
    if valid_from:
        output["valid_from"] = valid_from
    if schuljahr:
        output["schuljahr"] = schuljahr
    output.update(tt)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print("Gespeichert: " + str(out))