#!/usr/bin/env python3
from datetime import date

DAYS_DE = {0: "Montag", 1: "Dienstag", 2: "Mittwoch", 3: "Donnerstag", 4: "Freitag"}
NOTIFY_HOUR_CUTOFF = 9

# Beginn und Ende jeder Stunde. Wird gebraucht, um nach der letzten Stunde des
# Tages auf den naechsten Schultag umzuschalten.
# Achtung: dieselbe Tabelle steht als ZEITEN auch in index.html fuer die
# Anzeige. Aendert die Schule die Zeiten, muessen beide angepasst werden.
STUNDEN_ZEITEN = {
    1: ("08:20", "09:05"),
    2: ("09:10", "09:55"),
    3: ("10:15", "11:00"),
    4: ("11:05", "11:50"),
    5: ("12:05", "12:50"),
    6: ("12:55", "13:40"),
    7: ("13:50", "14:35"),
    8: ("14:40", "15:25"),
    9: ("15:25", "16:10"),
}

# Ab diesem Monat gehoert ein Datum zum neuen Schuljahr (August).
SCHOOL_YEAR_START_MONTH = 8


def expected_schuljahr(d: date) -> str:
    """Schuljahr im Untis-Format ('2026/27') fuer ein Datum.

    Ab August gehoert das Datum zum Schuljahr JJJJ/JJ+1, davor zum vorherigen.
    2026-09-02 -> '2026/27', 2026-07-20 -> '2025/26'.
    """
    start = d.year if d.month >= SCHOOL_YEAR_START_MONTH else d.year - 1
    return f"{start}/{(start + 1) % 100:02d}"
