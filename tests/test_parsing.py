"""Tests für die reine Parser- und Merge-Logik (kein Netzwerk, keine Dateien).

Deckt die heuristischen Funktionen ab, die bei geändertem PDF /HTML-Layout
still falsche Ergebnisse liefern könnten.
"""
import pytest

from fetch_and_build import class_matches, is_next_class
from parse_untis import extract_valid_from
from build_today import parse_stunden, clean, clean_lehrer, fach_name, resolve_vtg_fach

FACH_MAP = {"BI": "Biologie", "GE": "Geschichte", "M": "Mathe", ".IR": "Islamische Rel."}


class TestParseStunden:
    @pytest.mark.parametrize("raw, stunden, lehrer", [
        ("7 - 8 ROM", [7, 8], "ROM"),
        ("1 - 2 MAT", [1, 2], "MAT"),
        ("3", [3], ""),
        ("5", [5], ""),
    ])
    def test_parse(self, raw, stunden, lehrer):
        assert parse_stunden(raw) == (stunden, lehrer)


class TestClassMatches:
    @pytest.mark.parametrize("kandidat, ziel", [
        ("06c", "06c"),      # exakt
        ("06bc", "06c"),     # Gruppe enthält Buchstaben der Zielklasse
    ])
    def test_matches(self, kandidat, ziel):
        assert class_matches(kandidat, ziel) is True

    @pytest.mark.parametrize("kandidat, ziel", [
        ("06a", "06c"),      # anderer Buchstabe
        ("07c", "06c"),      # anderer Jahrgang
    ])
    def test_no_match(self, kandidat, ziel):
        assert class_matches(kandidat, ziel) is False


class TestIsNextClass:
    @pytest.mark.parametrize("wert", ["06c", "6c", "EF", "Q1", "Q2", "(06d)", "07ab"])
    def test_is_class(self, wert):
        assert is_next_class(wert) is True

    @pytest.mark.parametrize("wert", ["GE", "BI", "MU", "SP", "MOR", "A1.17"])
    def test_is_not_class(self, wert):
        # Fachkürzel und Räume dürfen NICHT als Klasse erkannt werden
        assert is_next_class(wert) is False


class TestExtractValidFrom:
    @pytest.mark.parametrize("html, erwartet", [
        ("Stundenplan (ab 5.5.25) gültig", "2025-05-05"),
        ("Plan (ab 12.1.2026)", "2026-01-12"),
        ("kein Datum hier", None),
    ])
    def test_extract(self, html, erwartet):
        assert extract_valid_from(html) == erwartet


class TestClean:
    @pytest.mark.parametrize("roh, erwartet", [
        ("---", ""),
        (None, ""),
        ("  Mathe  ", "Mathe"),
        ("D", "D"),
    ])
    def test_clean(self, roh, erwartet):
        assert clean(roh) == erwartet

    @pytest.mark.parametrize("roh, erwartet", [
        ("MOR GRU", "MOR"),   # zusammengeführte Lehrer /Vertreter-Spalte
        ("---", ""),
        ("", ""),
        ("HIL", "HIL"),
    ])
    def test_clean_lehrer(self, roh, erwartet):
        assert clean_lehrer(roh) == erwartet


class TestResolveVtgFach:
    def test_strukturiertes_fach_gewinnt(self):
        assert resolve_vtg_fach("BI", "irgendwas", FACH_MAP) == "BI"

    def test_fuehrender_punkt_im_strukturierten_fach(self):
        assert resolve_vtg_fach(".IR", "", FACH_MAP) == "IR"

    def test_kuerzel_aus_hinweis(self):
        # der Montag-Fall: "BI statt Do. 9.7. 5. Std."
        assert resolve_vtg_fach("", "BI statt Do. 9.7. 5. Std.", FACH_MAP) == "BI"
        assert resolve_vtg_fach("", "GE statt 3. Std.", FACH_MAP) == "GE"

    def test_unbekanntes_kuerzel_wird_ignoriert(self):
        assert resolve_vtg_fach("", "XYZ statt Do.", FACH_MAP) == ""

    def test_freitext_ohne_kuerzel(self):
        assert resolve_vtg_fach("", "Aufgaben werden gestellt", FACH_MAP) == ""
        assert resolve_vtg_fach("", "", FACH_MAP) == ""

    def test_namens_initiale_wird_nicht_als_fach_gelesen(self):
        # 'M' ist Mathe im Mapping, darf hier aber NICHT als Fachwechsel gelten
        assert resolve_vtg_fach("", "M. Müller vertritt", FACH_MAP) == ""
        assert resolve_vtg_fach("", "D Schmidt krank", FACH_MAP) == ""

    def test_kuerzel_ohne_schluesselwort_ignoriert(self):
        # nur 'statt'/'verlegt' lösen einen Fachwechsel aus
        assert resolve_vtg_fach("", "GE Raumänderung", FACH_MAP) == ""


class TestFachName:
    def test_bekanntes_kuerzel(self):
        assert fach_name("D", {"D": "Deutsch"}) == "Deutsch"

    def test_fuehrender_punkt_wird_entfernt(self):
        assert fach_name(".M", {"M": "Mathe"}) == "Mathe"

    def test_unbekanntes_kuerzel_bleibt(self):
        assert fach_name("XX", {}) == "XX"
