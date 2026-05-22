#!/usr/bin/env python3
"""Generate the Semiconductor Intelligence Report from public RSS feeds."""

from __future__ import annotations

import argparse
import email.utils
import html
import json
import re
import sys
import textwrap
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

KEYWORDS = {
    "2nm": 16, "a16": 15, "18a": 15, "14a": 15, "gaa": 13, "gate-all-around": 14,
    "hbm": 14, "euv": 13, "cowos": 12, "advanced packaging": 12, "capacity": 10,
    "capex": 10, "fab": 9, "ramp": 9, "chiplet": 9, "asic": 8, "boise": 8,
    "foundry": 8, "dram": 7, "nand": 7, "silicon carbide": 7, "pricing": 6,
    "investment": 6, "automotive": 5, "eda": 5, "ip": 4,
}

TOPIC_WEIGHTS = {
    "Fab announcements": 15, "CapEx changes": 14, "EUV roadmap": 16, "HBM demand": 17,
    "NAND / DRAM pricing": 11, "Advanced packaging": 13, "Foundry customer wins": 13,
    "AI accelerator demand": 16, "GPU / CPU roadmaps": 12, "ASIC and custom silicon": 14,
    "Automotive and edge silicon": 8, "EDA / IP design starts": 7, "OSAT / packaging capacity": 12,
}

ALIASES = {
    "Samsung Foundry": ["samsung"], "Intel Foundry": ["intel"],
    "Vanguard International Semiconductor": ["vanguard", "vis"], "Apple Silicon": ["apple"],
    "Google TPU": ["google", "tpu"], "Amazon Trainium": ["amazon", "trainium", "inferentia"],
    "Microsoft Maia": ["microsoft", "maia"], "Meta MTIA": ["meta", "mtia"],
    "Tesla Dojo": ["tesla", "dojo"], "Ampere Computing": ["ampere"],
    "Global Unichip": ["global unichip", "guc"], "Cisco Silicon One": ["cisco", "silicon one"],
    "Arista Networks": ["arista"], "Powertech Technology": ["powertech", "pti"], "Siemens EDA": ["siemens"],
}


def clean(value: str) -> str:
    value = html.unescape(value or "")
    for old, new in {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-", "\u00a0": " "}.items():
        value = value.replace(old, new)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def date(value: str) -> str:
    try:
        return email.utils.parsedate_to_datetime(value).date().isoformat()
    except Exception:
        return datetime.now(timezone.utc).date().isoformat()


def url(query: str) -> str:
    q = urllib.parse.quote_plus(f"{query} when:14d")
    return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


def terms(customer: str) -> list[str]:
    return ALIASES.get(customer, [customer.lower()])


def matches(customer: str, title: str, summary: str) -> bool:
    text = f"{title} {summary}".lower()
    return any(term.lower() in text for term in terms(customer))


def fetch(query: str, timeout: int) -> list[dict]:
    req = urllib.request.Request(url(query), headers={"User-Agent": "semiconductor-intelligence-report/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        root = ET.fromstring(res.read())
    rows = []
    for node in root.findall("./channel/item"):
        source = node.find("source")
        rows.append({
            "title": clean(node.findtext("title", "")),
            "summary": clean(node.findtext("description", ""))[:320],
            "url": node.findtext("link", ""),
            "source": clean(source.text if source is not None else "Google News"),
            "date": date(node.findtext("pubDate", "")),
        })
    return [row for row in rows if row["title"] and row["url"]]


def impact(customer: str, topic: str, title: str, summary: str) -> int:
    text = f"{customer} {topic} {title} {summary}".lower()
    value = 42 + TOPIC_WEIGHTS.get(topic, 10)
    for word, points in KEYWORDS.items():
        if word in text:
            value += points
    return max(1, min(99, value))


def implication(customer: str, topic: str, title: str) -> str:
    text = f"{topic} {title}".lower()
    if "asic" in text or "custom silicon" in text:
        return f"{customer}: custom silicon demand can translate into foundry starts, packaging capacity, and advanced-node etch pull."
    if "ai accelerator" in text:
        return f"{customer}: AI accelerator momentum is a leading indicator for CoWoS/HBM constraints and etch-intensive foundry demand."
    if "hbm" in text:
        return f"{customer}: HBM demand can pull advanced DRAM capacity and packaging intensity forward, lifting conductor etch relevance."
    if any(x in text for x in ["euv", "2nm", "18a", "14a"]):
        return f"{customer}: roadmap progress points to leading-edge process complexity where conductor etch timing matters."
    if "capex" in text or "investment" in text:
        return f"{customer}: CapEx language is a direct read-through to WFE budgets, timing, and tool allocation."
    if any(x in text for x in ["pricing", "dram", "nand"]):
        return f"{customer}: memory price and utilization momentum help estimate when deferred etch demand may return."
    if "packaging" in text:
        return f"{customer}: advanced packaging expansion can reshape adjacent process demand and customer priority."
    if "eda" in text or "ip" in text:
        return f"{customer}: EDA/IP activity is an upstream signal for design starts that can become future foundry and etch demand."
    if "automotive" in text:
        return f"{customer}: automotive and power-semiconductor demand can influence specialty fab loading and mature-node etch utilization."
    return f"{customer}: fab and capacity signals should be checked for ramp timing, layer complexity, and tool pull-ins."


def build_report(watchlist: dict, timeout: int, max_signals: int) -> dict:
    seen = set()
    signals = []
    for item in watchlist["queries"]:
        try:
            rows = fetch(item["query"], timeout)
        except Exception as exc:
            print(f"warning: {item['query']}: {exc}", file=sys.stderr)
            continue
        for row in rows[:3]:
            if row["url"] in seen or not matches(item["customer"], row["title"], row["summary"]):
                continue
            seen.add(row["url"])
            row.update({"customer": item["customer"], "topic": item["topic"]})
            row["impact_score"] = impact(item["customer"], item["topic"], row["title"], row["summary"])
            signals.append(row)
    signals = sorted(signals, key=lambda row: row["impact_score"], reverse=True)[:max_signals]
    if not signals:
        raise RuntimeError("No RSS records were collected.")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "customers": watchlist["customers"],
        "customer_groups": watchlist.get("customer_groups", {}),
        "topics": watchlist["topics"],
        "brief": [{"headline": row["title"], "implication": implication(row["customer"], row["topic"], row["title"])} for row in signals[:5]],
        "signals": signals,
    }


def write_markdown(report: dict, path: Path) -> None:
    lines = ["# Semiconductor Intelligence Report", "", f"Generated: {report['generated_at']}", "", f"Tracked entities: {len(report['customers'])}", "", "## What matters to conductor etch this week", ""]
    for item in report["brief"]:
        lines.append(f"- **{item['headline']}** - {item['implication']}")
    lines += ["", "## Ranked signals", ""]
    for row in report["signals"]:
        lines += [f"### {row['impact_score']} - {row['customer']} - {row['topic']}", "", f"[{row['title']}]({row['url']})", "", textwrap.fill(row["summary"], width=96), "", f"Source: {row['source']} | Date: {row['date']}", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--watchlist", default="data/watchlist.json")
    parser.add_argument("--json-out", default="data/latest-report.json")
    parser.add_argument("--markdown-out", default="reports/latest.md")
    parser.add_argument("--timeout", type=int, default=18)
    parser.add_argument("--max-signals", type=int, default=40)
    args = parser.parse_args()
    watchlist = json.loads(Path(args.watchlist).read_text(encoding="utf-8"))
    report = build_report(watchlist, args.timeout, args.max_signals)
    json_path = Path(args.json_out)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    write_markdown(report, Path(args.markdown_out))
    print(f"wrote {json_path} and {args.markdown_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
