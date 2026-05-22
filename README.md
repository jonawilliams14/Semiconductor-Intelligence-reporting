# Semiconductor Intelligence Report

Daily monitor for foundry, memory, IDM, fabless, cloud AI silicon, EDA/IP, and advanced-packaging signals that matter to conductor etch product management.

## Watchlist

The report tracks 50+ entities across:

- Foundries: TSMC, Samsung Foundry, Intel Foundry, GlobalFoundries, UMC, SMIC, Tower, PSMC, VIS, Hua Hong, Rapidus
- Memory and IDMs: Micron, Samsung Electronics, SK hynix, Kioxia, Western Digital, TI, STMicroelectronics, Infineon, NXP, Renesas
- Fabless and system chip integrators: NVIDIA, AMD, Qualcomm, Broadcom, Marvell, MediaTek, Apple Silicon, Google TPU, Amazon Trainium, Microsoft Maia, Meta MTIA, Tesla Dojo, Cerebras, Groq, Tenstorrent, SambaNova, Ampere, Arm, SiFive, Alchip, GUC, Socionext, Cisco Silicon One, Arista, Credo
- Design ecosystem: Synopsys, Cadence, Siemens EDA
- Advanced packaging and OSAT: ASE, Amkor, JCET, Powertech

Tracked themes include fab announcements, CapEx, EUV, HBM, memory pricing, advanced packaging, foundry wins, AI accelerators, GPU/CPU roadmaps, custom ASICs, automotive/edge silicon, EDA/IP design starts, and OSAT capacity.

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

The workflow in `.github/workflows/daily-semiconductor-intel.yml` runs every weekday at 13:15 UTC. Use **Actions -> Daily Semiconductor Intelligence -> Run workflow** to refresh it on demand.
