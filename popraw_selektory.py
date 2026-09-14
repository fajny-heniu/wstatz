#!/usr/bin/env python3
"""Dopisuje aktualne selektory Flashscore do SELEKTORY w aktualizuj.py.

Flashscore usunal znaczniki wcl-statistics-category i wcl-statistics-value.
Dzis etykieta i wartosci siedza w divach o klasach z doklejonym losowym
sufiksem (wcl-label_sO4bA, wcl-value_Ywp3J), wiec dopasowujemy po FRAGMENCIE
nazwy klasy - sufiks zmieni sie przy kolejnym wdrozeniu, prefiks nie.

Stare selektory zostaja jako zapas (gdyby Flashscore sie cofnal albo gdzies
jeszcze zyla stara wersja strony). Nowe ida na poczatek listy.

    ./.venv/bin/python popraw_selektory.py           # pokaz, co zmieni
    ./.venv/bin/python popraw_selektory.py --zapisz  # zapisz (robi .bak)
"""
import argparse
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
PLIK = HERE / "aktualizuj.py"

ZMIANY = [
    (
        """    "etykieta": [
        '[data-testid="wcl-statistics-category"]',""",
        """    "etykieta": [
        # uklad z wrzesnia 2026: klasy z losowym sufiksem, dopasowanie po prefiksie
        '[class*="wcl-label_"]',
        '[data-testid="wcl-scores-simple-text-01"]',
        '[data-testid="wcl-statistics-category"]',""",
    ),
    (
        """    "wartosc": [
        '[data-testid="wcl-statistics-value"]',""",
        """    "wartosc": [
        # dokladnie dwie na wiersz: gospodarz pierwszy, gosc ostatni
        '[class*="wcl-value_"]',
        '[data-testid="wcl-statistics-value"]',""",
    ),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zapisz", action="store_true")
    ap.add_argument("--plik", default=str(PLIK))
    args = ap.parse_args()

    sciezka = pathlib.Path(args.plik)
    if not sciezka.exists():
        sys.exit(f"Nie znaleziono {sciezka}")
    tekst = sciezka.read_text(encoding="utf-8")

    if '[class*="wcl-value_"]' in tekst:
        print("  Selektory sa juz poprawione - nic do zrobienia.")
        return

    for stare, nowe in ZMIANY:
        ile = tekst.count(stare)
        if ile != 1:
            sys.exit(f"STOP: fragment wystapil {ile} razy, spodziewano sie 1:\n{stare}")
        tekst = tekst.replace(stare, nowe)
        print(f"  + {nowe.strip().splitlines()[1].strip()}")

    if not args.zapisz:
        print("\n  To byl podglad. Aby zapisac: ./.venv/bin/python popraw_selektory.py --zapisz")
        return

    kopia = sciezka.with_suffix(".py.bak")
    kopia.write_bytes(sciezka.read_bytes())
    sciezka.write_text(tekst, encoding="utf-8")
    print(f"\n  zapisano {sciezka.name} (kopia: {kopia.name})")
    print("  Teraz sprawdz: ./.venv/bin/python backfill.py --test")


if __name__ == "__main__":
    main()
