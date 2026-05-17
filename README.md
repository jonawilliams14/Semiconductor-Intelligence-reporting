# Semiconductor Intelligence Agent

GitHub-ready daily monitor for customer and market signals that matter to conductor etch product management.

## Watchlist

Customers:

- TSMC
- Micron Technology
- Samsung Electronics
- SK hynix
- Intel

Tracked themes:

- Fab announcements
- CapEx changes
- EUV roadmap
- HBM demand
- NAND / DRAM pricing
- Advanced packaging

## Run locally

```powershell
python -m http.server 8787
```

Then open `http://localhost:8787`.

## Refresh the report

```powershell
python scripts/generate_report.py
```

The script reads `data/watchlist.json`, searches public Google News RSS feeds, ranks signals through a conductor-etch lens, and writes:

- `data/latest-report.json` for the dashboard
- `reports/latest.md` for a readable weekly brief

## GitHub setup

1. Push this folder to a GitHub repository.
2. Enable GitHub Pages from the repository settings, serving from the main branch root.
3. The workflow in `.github/workflows/daily-semiconductor-intel.yml` runs every weekday at 13:15 UTC, roughly 6:15 AM Pacific during daylight saving time.
4. Use **Actions -> Daily Semiconductor Intelligence -> Run workflow** to refresh it on demand.

The dashboard answers the operating question directly: **What matters to conductor etch this week?**
