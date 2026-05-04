# parse_untis.py
# -*- coding: utf-8 -*-
#!/usr/bin/env python3
import requests, json
from bs4 import BeautifulSoup
from pathlib import Path

UNTIS_URL = "https://leibniz-gymnasium.net/files/stpl/Kla1A_06c.htm"
DAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"]

def parse_untis():
    r = requests.get(UNTIS_URL, timeout=30)
    r.encoding = r.apparent_encoding
    soup = BeautifulSoup(r.content, "html.parser")
    tables = soup.find_all("table")
    main_rows = tables[1].find_all("tr")

    # Tag-Startspalten aus Header
    day_start_cols = {}
    col = 0
    for cell in main_rows[0].find_all(["td","th"]):
        cs = int(cell.get("colspan", 1))
        txt = cell.get_text(strip=True)
        if cs == 12 and txt in DAYS:
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
            block_idx = 0
            for cell in stunden_row.find_all(["td","th"]):
                cs = int(cell.get("colspan", 1))
                rs = int(cell.get("rowspan", 1))
                if cs == 12:
                    if rs >= 4 and block_idx < len(free_days):
                        day_skip_next[free_days[block_idx]] = True
                    block_idx += 1

    return timetable

if __name__ == "__main__":
    tt = parse_untis()
    out = Path(__file__).resolve().parents[1] / "data" / "untis_6c.json"
    out.parent.mkdir(exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(tt, f, indent=2, ensure_ascii=False)
    print("Gespeichert: " + str(out))