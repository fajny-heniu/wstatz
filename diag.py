#!/usr/bin/env python3
"""Rozpoznanie struktury tabeli statystyk na Flashscore.

Nic nie zapisuje, nic nie zmienia - tylko wypisuje, jak wyglada strona.
    ./.venv/bin/python diag.py                 # domyslny mecz (Widzew - Piast)
    ./.venv/bin/python diag.py --mid XXXXXXXX  # inny mecz
    ./.venv/bin/python diag.py --widok         # z widoczna przegladarka
"""
import argparse
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import aktualizuj as A  # noqa: E402

JS_SZUKAJ = r"""() => {
  const wynik = {kandydaci: [], testidy: {}, probki: []};

  // 1. Wszystkie data-testid na stronie, z licznikiem
  document.querySelectorAll('[data-testid]').forEach(e => {
    const t = e.getAttribute('data-testid');
    wynik.testidy[t] = (wynik.testidy[t] || 0) + 1;
  });

  // 2. Element zawierajacy dokladnie etykiete metryki - i jego przodkowie
  const szukane = ['Oczekiwane gole', 'Strzały na bramkę', 'Posiadanie piłki'];
  for (const fraza of szukane) {
    const el = [...document.querySelectorAll('*')].find(e =>
      e.children.length === 0 && (e.textContent || '').trim().startsWith(fraza));
    if (!el) { wynik.kandydaci.push({fraza, znaleziony: false}); continue; }
    const lancuch = [];
    let p = el;
    for (let i = 0; i < 5 && p; i++) {
      lancuch.push({
        tag: p.tagName,
        cls: (p.className && p.className.toString()).slice(0, 90),
        testid: p.getAttribute('data-testid') || '',
        dzieci: p.children.length,
        tekst: (p.innerText || '').replace(/\n/g, ' | ').slice(0, 80),
      });
      p = p.parentElement;
    }
    wynik.kandydaci.push({fraza, znaleziony: true, lancuch});
  }

  // 3. Surowy HTML jednego wiersza statystyki (do podejrzenia atrybutow)
  const et = [...document.querySelectorAll('*')].find(e =>
    e.children.length === 0 && (e.textContent || '').trim().startsWith('Oczekiwane gole'));
  if (et) {
    let w = et;
    for (let i = 0; i < 3 && w.parentElement; i++) w = w.parentElement;
    wynik.probki.push(w.outerHTML.slice(0, 1200));
  }
  return wynik;
}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mid", default="n3LN7zK6")
    ap.add_argument("--widok", action="store_true")
    args = ap.parse_args()

    url = f"https://www.flashscore.pl/mecz/{args.mid}/#/podsumowanie-meczu/statystyki-meczu/0"
    pw, br, page = A.otworz_przegladarke(args.widok)
    try:
        A.wejdz_na(page, url)
        page.wait_for_timeout(3500)
        for _ in range(6):          # przewin, zeby doladowac cala tabele
            page.mouse.wheel(0, 1400)
            page.wait_for_timeout(400)
        print("\n  adres po przekierowaniu:", page.url, "\n")
        w = page.evaluate(JS_SZUKAJ)
    finally:
        br.close()
        pw.stop()

    print("  --- data-testid wystepujace na stronie (te z 'stat' lub liczne) ---")
    for t, n in sorted(w["testidy"].items(), key=lambda x: -x[1]):
        if "stat" in t.lower() or n >= 5:
            print(f"    {n:>4}x  {t}")

    print("\n  --- droga od etykiety metryki w gore drzewa ---")
    for k in w["kandydaci"]:
        if not k["znaleziony"]:
            print(f"    {k['fraza']}: NIE ZNALEZIONO")
            continue
        print(f"    {k['fraza']}:")
        for i, p in enumerate(k["lancuch"]):
            print(f"      {i}: <{p['tag'].lower()}> testid={p['testid']!r} dzieci={p['dzieci']}")
            print(f"         class={p['cls']!r}")
            print(f"         tekst={p['tekst']!r}")

    print("\n  --- surowy HTML wiersza ---")
    for p in w["probki"]:
        print("   ", p.replace("><", ">\n    <")[:1200])
    print()


if __name__ == "__main__":
    main()
