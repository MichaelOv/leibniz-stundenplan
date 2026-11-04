#!/usr/bin/env python3
from datetime import date, timedelta

DAYS_DE = {0: "Montag", 1: "Dienstag", 2: "Mittwoch", 3: "Donnerstag", 4: "Freitag"}
NOTIFY_HOUR_CUTOFF = 9

# Ab dieser Stunde werden auch die spaeteren Schultage der Woche abgerufen.
# Beobachtung aus den PDF-Staenden: morgens (06:07, 07:28, 08:17) aktualisiert
# die Schule nur den laufenden Tag, die kommenden Tage erscheinen nachmittags
# (13:33, 15:09, 16:52). Der Cron laeuft morgens alle 5 Minuten; diese Tage
# dort mitzuziehen waere Last ohne Gegenwert.
WEEK_FETCH_FROM_HOUR = 9

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


# Ende des ersten Schulhalbjahrs, Tag der Zeugnisausgabe laut Schulkalender.
# Gesetzlich ist das Halbjahr zum 31.01. geteilt, die Zeugnisse kommen aber
# erst Tage spaeter, und bis dahin zaehlt der Unterricht zum ersten Halbjahr.
# Fehlt ein Schuljahr hier, wird auf den 31.01. zurueckgefallen.
HALBJAHR_ENDE = {
    "2026/27": "2027-02-12",
}


def schuljahr_start(sj: str) -> date:
    """Erster Tag des Schuljahrs '2026/27' -> 2026-08-01."""
    return date(int(sj.split("/")[0]), SCHOOL_YEAR_START_MONTH, 1)


def schuljahr_ende(sj: str) -> date:
    """Letzter Tag des Schuljahrs '2026/27' -> 2027-07-31."""
    return date(int(sj.split("/")[0]) + 1, SCHOOL_YEAR_START_MONTH, 1) - timedelta(days=1)


def halbjahr_grenze(sj: str) -> date:
    """Letzter Tag des ersten Halbjahrs."""
    eintrag = HALBJAHR_ENDE.get(sj)
    if eintrag:
        return date.fromisoformat(eintrag)
    return date(int(sj.split("/")[0]) + 1, 1, 31)


def zeitraum_fuer(sj: str, teil: str) -> tuple[date, date]:
    """Zeitraum eines Schuljahrs oder eines seiner Halbjahre.

    teil: 'jahr', 'hj1' oder 'hj2'.
    """
    if teil == "hj1":
        return schuljahr_start(sj), halbjahr_grenze(sj)
    if teil == "hj2":
        return halbjahr_grenze(sj) + timedelta(days=1), schuljahr_ende(sj)
    return schuljahr_start(sj), schuljahr_ende(sj)
