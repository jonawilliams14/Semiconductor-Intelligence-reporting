# Semiconductor Intelligence Agent

Daily monitor for customer and market signals that matter to conductor etch product management.

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

## Dashboard

The dashboard is served by `index.html` and reads `data/latest-report.json`.

Expected GitHub Pages URL after Pages is enabled:

```text
https://jonawilliams14.github.io/Semiconductor-Intelligence-reporting/
```

## Refresh the report

```powershell
python scripts/generate_report.py
```

The script reads `data/watchlist.json`, searches public Google News RSS feeds, ranks signals through a conductor-etch lens, and writes:

- `data/latest-report.json` for the dashboard
- `reports/latest.md` for a readable brief

## GitHub Pages setup

1. Open repository **Settings -> Pages**.
2. Under **Build and deployment**, choose **Deploy from a branch**.
3. Choose branch `main` and folder `/root`.
4. Save.

The workflow in `.github/workflows/daily-semiconductor-intel.yml` runs every weekday at 13:15 UTC, roughly 6:15 AM Pacific during daylight saving time. Use **Actions -> Daily Semiconductor Intelligence -> Run workflow** to refresh it on demand.

The dashboard answers the operating question directly: **What matters to conductor etch this week?**
