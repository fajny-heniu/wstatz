# WSTATZ — widzewskie statystyki

Statystyki meczowe Widzewa Łódź, kolejka po kolejce, sezon bieżący zestawiony
z poprzednim. Strona: `index.html` (samodzielny plik, dane wbudowane w środku —
działa też otwarty lokalnie, bez serwera).

## Źródła danych

- Statystyki meczowe: Flashscore
- Miejsca w tabeli: Wikipedia

## Struktura repo

| Plik | Rola |
|---|---|
| `index.html` | gotowa strona (to ją serwuje GitHub Pages) |
| `data.json` | dane po przeliczeniu — wejście dla `strona.py` |
| `2025-26.csv`, `2026-27.csv` | surowe dane meczowe, jeden wiersz = jeden mecz |
| `zbuduj.py` | CSV → `data.json` (średnie, bilans, walidacja) |
| `strona.py` | `data.json` → `index.html` |
| `pobierz.py` | próba automatycznego pobierania z API-Football (ograniczenia planu darmowego opisane w historii projektu) |

## Aktualizacja

```
python3 zbuduj.py && python3 strona.py
```

Dane historyczne (`2025-26.csv`) są zamknięte i nienaruszane — aktualizacji
podlega tylko sezon bieżący.
