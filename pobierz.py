#!/usr/bin/env python3
"""
Widzew Lodz - pobieranie statystyk meczowych z API-Football.

Uzycie:
    python pobierz.py --sezon 2025          # pelny sezon 2025/26 (raz)
    python pobierz.py --update              # tylko nowe mecze biezacego sezonu
    python pobierz.py --sezon 2025 --dry-run   # pokaz mecze, nie pobieraj statystyk

Klucz API czytany ze zmiennej srodowiskowej APIFOOTBALL_KEY
albo z pliku klucz.txt lezacego obok skryptu.
"""

import argparse
import csv
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "https://v3.football.api-sports.io"
SZUKANA_DRUZYNA = "Widzew"
KRAJ = "Poland"

HERE = pathlib.Path(__file__).resolve().parent
CACHE_DIR = HERE / "cache"
CONFIG = HERE / "config.json"

# Kolejnosc kolumn w CSV. Statystyki trzymamy per gospodarz/gosc,
# dokladnie tak jak zwraca je API - kolumna 'venue' mowi, gdzie byl Widzew.
KOLUMNY = [
    "season", "round", "date", "competition", "venue",
    "home_team", "away_team", "score_ht", "score_ft",
    "xg_home", "xg_away",
    "shots_home", "shots_away",
    "sot_home", "sot_away",
    "passes_home", "passes_away",
    "passes_acc_home", "passes_acc_away",
    "pass_pct_home", "pass_pct_away",
    "poss_home", "poss_away",
    "fixture_id",
]

# Etykiety statystyk w odpowiedzi API -> nasze nazwy pol
MAPA_STAT = {
    "expected_goals": "xg",
    "Total Shots": "shots",
    "Shots on Goal": "sot",
    "Total passes": "passes",
    "Passes accurate": "passes_acc",
    "Passes %": "pass_pct",
    "Ball Possession": "poss",
}


# ---------------------------------------------------------------- pomocnicze

def wczytaj_klucz():
    klucz = os.environ.get("APIFOOTBALL_KEY", "").strip()
    if klucz:
        return klucz
    plik = HERE / "klucz.txt"
    if plik.exists():
        klucz = plik.read_text(encoding="utf-8").strip()
        if klucz:
            return klucz
    sys.exit(
        "BLAD: brak klucza API.\n"
        "  Zapisz klucz w pliku klucz.txt obok tego skryptu,\n"
        "  albo ustaw zmienna APIFOOTBALL_KEY."
    )


def liczba(txt):
    """'52%' -> 52.0 ; '1.34' -> 1.34 ; None/'' -> None"""
    if txt is None:
        return None
    if isinstance(txt, (int, float)):
        return float(txt)
    txt = str(txt).strip().replace("%", "").replace(",", ".")
    if not txt or txt in {"-", "null"}:
        return None
    try:
        return float(txt)
    except ValueError:
        return None


def numer_kolejki(runda):
    """'Regular Season - 12' -> 12"""
    m = re.search(r"(\d+)\s*$", runda or "")
    return int(m.group(1)) if m else None


def domyslny_sezon():
    """Sezon 2026/27 to w API-Football sezon 2026."""
    import datetime as dt
    dzis = dt.date.today()
    return dzis.year if dzis.month >= 7 else dzis.year - 1


class Licznik:
    """Pilnuje, ile zapytan zuzyl skrypt - darmowy plan ma ~100/dzien."""

    def __init__(self, maks):
        self.maks = maks
        self.zuzyte = 0

    def sprawdz(self):
        if self.zuzyte >= self.maks:
            raise LimitZapytan(
                f"osiagnieto limit {self.maks} zapytan w tym uruchomieniu"
            )

    def plus(self):
        self.zuzyte += 1


class LimitZapytan(Exception):
    pass


# ---------------------------------------------------------------- warstwa API

def api_get(sciezka, params, klucz, licznik, cache_nazwa=None, force=False):
    """Zapytanie do API z cache na dysku. Cache oszczedza limit przy re-runach."""
    if cache_nazwa and not force:
        plik = CACHE_DIR / f"{cache_nazwa}.json"
        if plik.exists():
            return json.loads(plik.read_text(encoding="utf-8"))

    licznik.sprawdz()
    url = f"{API_BASE}{sciezka}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"x-apisports-key": klucz})

    ostatni_blad = None
    for proba in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as odp:
                dane = json.loads(odp.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            ostatni_blad = f"HTTP {e.code}"
            if e.code == 429:
                time.sleep(5 * (proba + 1))
                continue
            if e.code in (401, 403):
                sys.exit(
                    "BLAD: API odrzucilo klucz (HTTP %d).\n"
                    "  Sprawdz, czy klucz jest poprawny i aktywny." % e.code
                )
            time.sleep(2)
        except (urllib.error.URLError, TimeoutError) as e:
            ostatni_blad = str(e)
            time.sleep(2)
    else:
        sys.exit(f"BLAD: nie udalo sie polaczyc z API ({ostatni_blad}).")

    licznik.plus()

    bledy = dane.get("errors")
    if bledy:
        # API-Football zwraca [] gdy wszystko OK, dict/list gdy jest problem
        tekst = json.dumps(bledy, ensure_ascii=False)
        if "plan" in tekst.lower() or "subscription" in tekst.lower():
            sys.exit(
                f"BLAD z API: {tekst}\n"
                "  Darmowy plan API-Football czesto ogranicza dostepne sezony.\n"
                "  Sprawdz w panelu, ktore sezony masz w swoim planie."
            )
        if "limit" in tekst.lower():
            sys.exit(
                f"BLAD z API: {tekst}\n"
                "  Wyczerpany dzienny limit zapytan. Uruchom ponownie jutro -\n"
                "  cache sprawi, ze skrypt nie pobierze dwa razy tego samego."
            )
        sys.exit(f"BLAD z API: {tekst}")

    if cache_nazwa:
        CACHE_DIR.mkdir(exist_ok=True)
        (CACHE_DIR / f"{cache_nazwa}.json").write_text(
            json.dumps(dane, ensure_ascii=False), encoding="utf-8"
        )
    time.sleep(0.3)
    return dane


def id_druzyny(klucz, licznik):
    """Znajduje id Widzewa raz i zapisuje w config.json."""
    if CONFIG.exists():
        cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
        if cfg.get("team_id"):
            return cfg["team_id"], cfg.get("team_name", SZUKANA_DRUZYNA)

    # API-Football nie pozwala uzyc 'country' razem z 'search',
    # wiec filtrujemy po kraju lokalnie, na zwroconych wynikach.
    dane = api_get("/teams", {"search": SZUKANA_DRUZYNA},
                   klucz, licznik, cache_nazwa="teams_widzew")
    wszyscy = dane.get("response", [])
    kandydaci = [k for k in wszyscy
                 if (k.get("team", {}).get("country") or "").lower() == KRAJ.lower()]
    if not kandydaci:
        kandydaci = wszyscy  # gdyby API nie podalo kraju - pokazemy wszystko
    if not kandydaci:
        sys.exit("BLAD: API nie znalazlo zadnej druzyny 'Widzew'.")

    wybrany = kandydaci[0]["team"]
    if len(kandydaci) > 1:
        print("Znaleziono wiecej niz jedna druzyne:")
        for k in kandydaci:
            t = k["team"]
            print(f"  id={t['id']}  {t['name']}  ({t.get('country')})")
        print(f"-> wybieram {wybrany['name']} (id={wybrany['id']})")
        print("   Jesli to zle, popraw team_id w config.json.")

    CONFIG.write_text(
        json.dumps({"team_id": wybrany["id"], "team_name": wybrany["name"]},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return wybrany["id"], wybrany["name"]


def mecze_ligowe(team_id, sezon, klucz, licznik):
    """
    Wszystkie mecze druzyny w sezonie, przefiltrowane do rozgrywek ligowych.
    Filtr po league.type == 'League' zalatwia sprawe automatycznie -
    niezaleznie od tego, czy Widzew gra w Ekstraklasie czy 1. Lidze,
    i odrzuca puchary bez recznej listy wyjatkow.
    """
    dane = api_get("/fixtures", {"team": team_id, "season": sezon},
                   klucz, licznik, cache_nazwa=f"fixtures_{team_id}_{sezon}",
                   force=True)  # terminarz zawsze swiezy, to jedno zapytanie

    wynik = []
    for f in dane.get("response", []):
        liga = f.get("league", {})
        if (liga.get("type") or "").lower() != "league":
            continue
        wynik.append(f)
    return wynik


def statystyki_meczu(fixture_id, klucz, licznik):
    dane = api_get("/fixtures/statistics", {"fixture": fixture_id},
                   klucz, licznik, cache_nazwa=f"stats_{fixture_id}")
    per_team = {}
    for blok in dane.get("response", []):
        tid = blok.get("team", {}).get("id")
        staty = {}
        for s in blok.get("statistics", []):
            pole = MAPA_STAT.get(s.get("type"))
            if pole:
                staty[pole] = liczba(s.get("value"))
        per_team[tid] = staty
    return per_team


# ---------------------------------------------------------------- budowa wiersza

def zbuduj_wiersz(fixture, staty, team_id, sezon):
    home = fixture["teams"]["home"]
    away = fixture["teams"]["away"]
    gole = fixture.get("goals", {})
    score = fixture.get("score", {})
    ht = score.get("halftime", {}) or {}

    sh = staty.get(home["id"], {})
    sa = staty.get(away["id"], {})

    def pct(s):
        """Jesli API nie poda 'Passes %', licz z celnych/wszystkich."""
        if s.get("pass_pct") is not None:
            return s["pass_pct"]
        c, w = s.get("passes_acc"), s.get("passes")
        return round(c / w * 100, 1) if c and w else None

    w = {
        "season": f"{sezon}/{str(sezon + 1)[2:]}",
        "round": numer_kolejki(fixture["league"].get("round")),
        "date": (fixture["fixture"].get("date") or "")[:10],
        "competition": fixture["league"].get("name"),
        "venue": "H" if home["id"] == team_id else "A",
        "home_team": home["name"],
        "away_team": away["name"],
        "score_ht": f"{ht.get('home')}:{ht.get('away')}"
                    if ht.get("home") is not None else None,
        "score_ft": f"{gole.get('home')}:{gole.get('away')}"
                    if gole.get("home") is not None else None,
        "fixture_id": fixture["fixture"]["id"],
        "pass_pct_home": pct(sh),
        "pass_pct_away": pct(sa),
    }
    for pole in ("xg", "shots", "sot", "passes", "passes_acc", "poss"):
        w[f"{pole}_home"] = sh.get(pole)
        w[f"{pole}_away"] = sa.get(pole)
    return w


def zapisz_csv(sciezka, wiersze):
    """Sortowanie malejace po kolejce - najnowsza na gorze, zgodnie z zalozeniem."""
    wiersze = sorted(wiersze, key=lambda r: (r.get("round") or 0), reverse=True)
    with open(sciezka, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=KOLUMNY, extrasaction="ignore")
        wr.writeheader()
        for r in wiersze:
            wr.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in KOLUMNY})


def wczytaj_csv(sciezka):
    if not sciezka.exists():
        return []
    with open(sciezka, newline="", encoding="utf-8") as f:
        out = []
        for r in csv.DictReader(f):
            r["round"] = int(r["round"]) if r.get("round") else None
            out.append(r)
        return out


# ---------------------------------------------------------------- main

def main():
    p = argparse.ArgumentParser(description="Statystyki meczowe Widzewa z API-Football")
    p.add_argument("--sezon", type=int, help="rok startowy, np. 2025 = sezon 2025/26")
    p.add_argument("--update", action="store_true",
                   help="dociaga tylko brakujace mecze biezacego sezonu")
    p.add_argument("--dry-run", action="store_true",
                   help="pokaz liste meczow, nie pobieraj statystyk")
    p.add_argument("--max-zapytan", type=int, default=90,
                   help="bezpiecznik na darmowy limit (domyslnie 90)")
    args = p.parse_args()

    if not args.sezon and not args.update:
        p.error("podaj --sezon ROK albo --update")

    sezon = args.sezon or domyslny_sezon()
    plik = HERE / f"{sezon}-{str(sezon + 1)[2:]}.csv"

    klucz = wczytaj_klucz()
    licznik = Licznik(args.max_zapytan)

    try:
        team_id, nazwa = id_druzyny(klucz, licznik)
        print(f"Druzyna: {nazwa} (id={team_id})   sezon {sezon}/{str(sezon+1)[2:]}")

        fixtures = mecze_ligowe(team_id, sezon, klucz, licznik)
        if not fixtures:
            print("\nAPI nie zwrocilo zadnych meczow ligowych dla tego sezonu.")
            print("Najczestsza przyczyna: darmowy plan nie obejmuje tego sezonu.")
            return

        rozegrane = [f for f in fixtures
                     if (f["fixture"]["status"]["short"] in ("FT", "AET", "PEN"))]
        print(f"Meczow ligowych w terminarzu: {len(fixtures)}, rozegranych: {len(rozegrane)}")

        istniejace = wczytaj_csv(plik) if args.update else []
        znane = {r["fixture_id"] for r in istniejace}
        do_pobrania = [f for f in rozegrane if str(f["fixture"]["id"]) not in znane]

        if args.update and not do_pobrania:
            print("Brak nowych meczow - plik bez zmian.")
            return

        print(f"Do pobrania statystyk: {len(do_pobrania)} meczow "
              f"(~{len(do_pobrania)} zapytan)")

        if args.dry_run:
            for f in sorted(do_pobrania,
                            key=lambda x: numer_kolejki(x["league"]["round"]) or 0,
                            reverse=True):
                k = numer_kolejki(f["league"]["round"])
                print(f"  kolejka {k:>2}  {f['fixture']['date'][:10]}  "
                      f"{f['teams']['home']['name']} - {f['teams']['away']['name']}  "
                      f"{f['goals']['home']}:{f['goals']['away']}")
            print("\n(--dry-run: statystyki nie byly pobierane)")
            return

        nowe = []
        for i, f in enumerate(do_pobrania, 1):
            fid = f["fixture"]["id"]
            k = numer_kolejki(f["league"]["round"])
            print(f"  [{i}/{len(do_pobrania)}] kolejka {k} ... ", end="", flush=True)
            staty = statystyki_meczu(fid, klucz, licznik)
            nowe.append(zbuduj_wiersz(f, staty, team_id, sezon))
            print("ok")

        zapisz_csv(plik, istniejace + nowe)
        print(f"\nZapisano: {plik.name}  ({len(istniejace) + len(nowe)} meczow)")
        print(f"Zuzyte zapytania w tym uruchomieniu: {licznik.zuzyte}")

        braki = sum(1 for r in nowe if r.get("xg_home") is None)
        if braki:
            print(f"Uwaga: {braki} meczow bez xG - API ich nie podalo. "
                  "W tabeli beda pokazane jako '-'.")

    except LimitZapytan as e:
        print(f"\nPrzerwano: {e}.")
        print("Uruchom skrypt ponownie - cache zachowa to, co juz pobrane.")


if __name__ == "__main__":
    main()
