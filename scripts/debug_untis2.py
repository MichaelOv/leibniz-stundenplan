#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup

url = "https://leibniz-gymnasium.net/files/stpl/Kla1A_06c.htm"
r = requests.get(url, timeout=30)
r.encoding = r.apparent_encoding
soup = BeautifulSoup(r.content, "html.parser")

main_table = None
for table in soup.find_all("table"):
    if "Montag" in table.get_text() and "Dienstag" in table.get_text():
        main_table = table
        break

rows = main_table.find_all("tr")

# Nur Zeilen mit Stundenzahl ausgeben - erste 6 Stunden
for row in rows:
    cells = row.find_all(["td","th"])
    if not cells:
        continue
    first = cells[0].get_text(strip=True)
    if not first.isdigit():
        continue
    print("=== Stunde " + first + " ===")
    for i, cell in enumerate(cells):
        colspan = cell.get("colspan", "1")
        content = cell.get_text(strip=True)[:60]
        print("  Zelle " + str(i) + " colspan=" + str(colspan) + ": " + content)
    if int(first) > 3:
        break
