#!/usr/bin/env python3
"""
Scala pliki CSV z sezonow w jeden data.json, ktory zasili strone.

Uzycie:
    python zbuduj.py                 # bierze wszystkie pliki ROK-RR.csv z katalogu
    python zbuduj.py 2025-26.csv 2026-27.csv

Efekt: data.json z lista meczow per sezon (od najnowszej kolejki),
srednimi sezonowymi i wartosciami przelozonymi na perspektywe Widzewa.
"""

import csv
import glob
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
DRUZYNA = "Widzew"

# Statystyki, dla ktorych liczymy srednie sezonowe
METRYKI = ["xg", "shots", "sot", "bc", "pass_pct", "poss"]


def num(x):
    if x is None or x == "":
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def perspektywa_widzewa(r):
    """
    Dokłada pola widzew_* / rywal_* wyliczone z venue.
    CSV zostaje w ukladzie gospodarz/gosc (1:1 z API), a tu robimy
    warstwe interpretacyjna - dzieki temu surowe dane sa nietykalne.
    """
    dom = r.get("venue") == "H"
    a, b = ("home", "away") if dom else ("away", "home")

    out = {"venue": r.get("venue")}
    for m in METRYKI:
        out[f"widzew_{m}"] = num(r.get(f"{m}_{a}"))
        out[f"rywal_{m}"] = num(r.get(f"{m}_{b}"))

    out["rywal_nazwa"] = r.get("away_team") if dom else r.get("home_team")

    ft = r.get("score_ft") or ""
    if ":" in ft:
        h, g = ft.split(":")
        gole_w, gole_r = (int(h), int(g)) if dom else (int(g), int(h))
        out["widzew_gole"] = gole_w
        out["rywal_gole"] = gole_r
        out["rezultat"] = "W" if gole_w > gole_r else ("P" if gole_w < gole_r else "R")
    else:
        out["widzew_gole"] = out["rywal_gole"] = out["rezultat"] = None
    return out


def narastajaco(mecze):
    """
    Dokłada do kazdego meczu bilans i punkty PO tej kolejce.
    Liczy w kolejnosci rosnacej, choc lista jest posortowana malejaco.

    Zwraca liste ostrzezen: jesli w numerach kolejek jest luka albo dane
    nie zaczynaja sie od kolejki 1, bilans narastajacy jest bezwartosciowy
    i pola zostaja puste, zamiast pokazywac zaniżone liczby.
    """
    ostrz = []
    kolejki = sorted(m["kolejka"] for m in mecze if m["kolejka"])
    if not kolejki:
        return ["brak numerow kolejek - nie licze bilansu"]

    oczekiwane = list(range(1, len(kolejki) + 1))
    ciagle = kolejki == oczekiwane
    if not ciagle:
        brakujace = sorted(set(range(1, max(kolejki) + 1)) - set(kolejki))
        ostrz.append(
            "kolejki nie tworza ciaglej serii od 1 (brakuje: "
            + ", ".join(map(str, brakujace))
            + ") - bilans i punkty zostaja puste"
        )
        for m in mecze:
            m["bilans_do"] = m["punkty_do"] = None
        return ostrz

    w = r = p = 0
    for m in sorted(mecze, key=lambda x: x["kolejka"]):
        if m.get("rezultat") == "W":
            w += 1
        elif m.get("rezultat") == "R":
            r += 1
        elif m.get("rezultat") == "P":
            p += 1
        m["bilans_do"] = f"{w}-{r}-{p}"
        m["punkty_do"] = w * 3 + r
    return ostrz


def waliduj_pozycje(mecze):
    """
    Test krzyzowy dwoch niezaleznych zrodel: pozycja (tabela zewnetrzna)
    kontra wynik meczu (Flashscore). Po wygranej pozycja nie moze spasc,
    po przegranej nie moze wzrosnac.

    Uwaga: przy rownej liczbie punktow teoretycznie mozliwy jest wyjatek
    przez roznice bramek, wiec to ostrzezenie, nie blad. Ale trafienie
    w taki przypadek jest rzadkie - najpierw sprawdz literowke.
    """
    ostrz = []
    poprz = None
    for m in sorted((x for x in mecze if x.get("kolejka")), key=lambda x: x["kolejka"]):
        p = m.get("pozycja")
        if p is None:
            poprz = None  # luka w pozycjach zeruje porownanie
            continue
        if poprz is not None:
            if m.get("rezultat") == "W" and p > poprz:
                ostrz.append(f"k{m['kolejka']}: wygrana, a pozycja spadla {poprz}->{p}")
            if m.get("rezultat") == "P" and p < poprz:
                ostrz.append(f"k{m['kolejka']}: przegrana, a pozycja wzrosla {poprz}->{p}")
        poprz = p
    return ostrz


def srednie(mecze):
    """Srednia liczona tylko z meczow, w ktorych metryka istnieje."""
    out = {}
    for m in METRYKI:
        for kto in ("widzew", "rywal"):
            klucz = f"{kto}_{m}"
            wart = [x[klucz] for x in mecze if x.get(klucz) is not None]
            out[klucz] = round(sum(wart) / len(wart), 2) if wart else None
            out[f"{klucz}_n"] = len(wart)  # ile meczow zasilalo te srednia
    gole = [x for x in mecze if x.get("widzew_gole") is not None]
    if gole:
        out["widzew_gole"] = round(sum(x["widzew_gole"] for x in gole) / len(gole), 2)
        out["rywal_gole"] = round(sum(x["rywal_gole"] for x in gole) / len(gole), 2)
        out["bilans"] = {
            "W": sum(1 for x in gole if x["rezultat"] == "W"),
            "R": sum(1 for x in gole if x["rezultat"] == "R"),
            "P": sum(1 for x in gole if x["rezultat"] == "P"),
        }
    return out


def waliduj(r, sezon):
    """Sanity-checki. Nie poprawiaja danych - tylko krzycza."""
    ostrz = []
    k = r.get("round")
    for strona in ("home", "away"):
        s, sot = num(r.get(f"shots_{strona}")), num(r.get(f"sot_{strona}"))
        if s is not None and sot is not None and sot > s:
            ostrz.append(f"{sezon} k.{k}: strzaly na bramke > strzaly lacznie ({strona})")
        p = num(r.get(f"pass_pct_{strona}"))
        if p is not None and not (0 <= p <= 100):
            ostrz.append(f"{sezon} k.{k}: % podan poza zakresem ({strona}): {p}")
        x = num(r.get(f"xg_{strona}"))
        if x is not None and not (0 <= x <= 8):
            ostrz.append(f"{sezon} k.{k}: podejrzane xG ({strona}): {x}")
    poss = (num(r.get("poss_home")) or 0) + (num(r.get("poss_away")) or 0)
    if poss and not (95 <= poss <= 105):
        ostrz.append(f"{sezon} k.{k}: posiadanie nie sumuje sie do 100 ({poss})")
    return ostrz


def main():
    pliki = sys.argv[1:] or sorted(glob.glob(str(HERE / "[0-9][0-9][0-9][0-9]-[0-9][0-9].csv")))
    if not pliki:
        sys.exit("BLAD: nie znalazlem zadnego pliku CSV. Uruchom najpierw pobierz.py")

    sezony = {}
    wszystkie_ostrz = []

    for sciezka in pliki:
        with open(sciezka, newline="", encoding="utf-8") as f:
            wiersze = list(csv.DictReader(f))
        if not wiersze:
            continue

        nazwa = wiersze[0].get("season") or pathlib.Path(sciezka).stem
        mecze = []
        for r in wiersze:
            wszystkie_ostrz += waliduj(r, nazwa)
            m = {
                "kolejka": int(r["round"]) if r.get("round") else None,
                "data": r.get("date"),
                "rozgrywki": r.get("competition"),
                "gospodarz": r.get("home_team"),
                "gosc": r.get("away_team"),
                "wynik": r.get("score_ft") or None,
                "wynik_ht": r.get("score_ht") or None,
            }
            for strona in ("home", "away"):
                for met in METRYKI:
                    m[f"{met}_{strona}"] = num(r.get(f"{met}_{strona}"))
            m.update(perspektywa_widzewa(r))
            # pozycja w tabeli - dane zewnetrzne, nie da sie policzyc
            # z meczow samego Widzewa; puste pole to brak, nie zero
            poz = r.get("position")
            m["pozycja"] = int(poz) if poz not in (None, "") else None
            mecze.append(m)

        mecze.sort(key=lambda x: x["kolejka"] or 0, reverse=True)
        wszystkie_ostrz += [f"{nazwa}: {o}" for o in narastajaco(mecze)]
        wszystkie_ostrz += [f"{nazwa}: {o}" for o in waliduj_pozycje(mecze)]
        sezony[nazwa] = {
            "mecze": mecze,
            "liczba_meczow": len(mecze),
            "srednie": srednie(mecze),
            "forma_5": srednie(mecze[:5]),  # 5 ostatnich kolejek
        }
        print(f"{nazwa}: {len(mecze)} meczow")

    out = {
        "druzyna": DRUZYNA,
        "metryki": METRYKI,
        "sezony": sezony,
    }
    (HERE / "data.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\nZapisano data.json")

    if wszystkie_ostrz:
        print(f"\nOstrzezenia walidacji ({len(wszystkie_ostrz)}):")
        for o in wszystkie_ostrz[:20]:
            print("  -", o)
        if len(wszystkie_ostrz) > 20:
            print(f"  ... i {len(wszystkie_ostrz) - 20} wiecej")


if __name__ == "__main__":
    main()
