#!/usr/bin/env python3
from datetime import date

DAYS_DE = {0: "Montag", 1: "Dienstag", 2: "Mittwoch", 3: "Donnerstag", 4: "Freitag"}
NOTIFY_HOUR_CUTOFF = 9

# Ab diesem Monat gehoert ein Datum zum neuen Schuljahr (August).
SCHOOL_YEAR_START_MONTH = 8


def expected_schuljahr(d: date) -> str:
    """Schuljahr im Untis-Format ('2026/27') fuer ein Datum.

    Ab August gehoert das Datum zum Schuljahr JJJJ/JJ+1, davor zum vorherigen.
    2026-09-02 -> '2026/27', 2026-07-20 -> '2025/26'.
    """
    start = d.year if d.month >= SCHOOL_YEAR_START_MONTH else d.year - 1
    return f"{start}/{(start + 1) % 100:02d}"
