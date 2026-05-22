#!/usr/bin/env python3
"""Generate the Semiconductor Intelligence Report from public RSS search feeds."""

from __future__ import annotations

import argparse
import email.utils
import html
import json
import re
import sys
import textwrap
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ETCH_KEYWORDS = {
    "2nm": 16,
    "a16": 15,
    "18a": 15,
    "14a": 15,
    "gate-all-around": 14,
    "gaa": 13,
    "hbm": 14,
    "euv": 13,
    "advanced packaging": 12,
    "capacity": 10,
    "capex": 10,
    "fab": 9,
    "ramp": 9,
    "boise": 8,
    "foundry": 8,
    "dram": 7,
    "nand": 7,
    "pricing": 6,
    "investment": 6,
    "asic": 8,
    "ai accelerator": 10,
    "chiplet": 9,
    "cowos": 12,
    "emib": 10,
    "foveros": 10,
    "silicon carbide": 7,
    "automotive": 5,
    "eda": 5,
    "ip": 4,
}

TOPIC_WEIGHTS = {
    "Fab announcements": 15,
    "CapEx changes": 14,
    "EUV roadmap": 16,
    "HBM demand": 17,
    "NAND / DRAM pricing": 11,
    "Advanced packaging": 13,
    "Foundry customer wins": 13,
    "AI accelerator demand": 16,
    "GPU / CPU roadmaps": 12,
    "ASIC and custom silicon": 14,
    "Automotive and edge silicon": 8,
    "EDA / IP design starts": 7,
    "OSAT / packaging capacity": 12,
}

DEFAULT_MAX_PER_QUERY = 3
ARTICLE_TIMEOUT = 5
MIN_SUMMARY_CHARS = 90
MAX_SUMMARY_CHARS = 520

CUSTOMER_ALIASES = {
    "Samsung Foundry": ["samsung"],
    "Intel Foundry": ["intel"],
    "Vanguard International Semiconductor": ["vanguard", "vis"],
    "Apple Silicon": ["apple"],
    "Google TPU": ["google", "tpu"],
    "Amazon Trainium": ["amazon", "trainium", "inferentia"],
    "Microsoft Maia": ["microsoft", "maia"],
    "Meta MTIA": ["meta", "mtia"],
    "Tesla Dojo": ["tesla", "dojo"],
    "Ampere Computing": ["ampere"],
    "Global Unichip": ["global unichip", "guc"],
    "Cisco Silicon One": ["cisco", "silicon one"],
    "Arista Networks": ["arista"],
    "Powertech Technology": ["powertech", "pti"],
    "Siemens EDA": ["siemens"],
}


@dataclass
class Item:
    customer: str
    topic: str
    title: str
    summary: str
    url: str
    source: str
    published: str
    score: int


def clean_text(value: str) -> str:
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u00a0": " ",
    }
    text = html.unescape(value or "")
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def trim_summary(value: str) -> str:
    text = clean_text(value)
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    if len(text) <= MAX_SUMMARY_CHARS:
        return text
    clipped = text[:MAX_SUMMARY_CHARS].rsplit(" ", 1)[0].rstrip(",;:")
    return f"{clipped}."


def title_without_source(title: str, source: str) -> str:
    clean_title = clean_text(title)
    clean_source = clean_text(source)
    if clean_source and clean_title.lower().endswith(f" - {clean_source}".lower()):
        return clean_title[: -(len(clean_source) + 3)].strip()
    return clean_title


def useful_summary(value: str, title: str, source: str) -> bool:
    text = clean_text(value).lower()
    headline = clean_text(title).lower()
    headline_core = title_without_source(title, source).lower()
    source_name = clean_text(source).lower()
    if len(text) < MIN_SUMMARY_CHARS:
        return False
    if text == headline or text == headline_core:
        return False
    if text == f"{headline} {source_name}".strip() or text == f"{headline_core} {source_name}".strip():
        return False
    if headline_core and text.startswith(headline_core) and source_name and text.endswith(source_name):
        return False
    if "comprehensive up-to-date news coverage" in text and "google news" in text:
        return False
    if "enable javascript" in text or "are you a robot" in text:
        return False
    return True


def headline_based_summary(customer: str, topic: str, title: str, source: str) -> str:
    core = title_without_source(title, source)
    implication = conductor_etch_implication(customer, topic, title)
    return trim_summary(f"{source} reports that {core}. {implication}")


def extract_meta_description(page: str) -> str:
    patterns = [
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:description["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, page, flags=re.IGNORECASE)
        if match:
            return clean_text(match.group(1))
    return ""


def extract_first_paragraph(page: str) -> str:
    paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", page, flags=re.IGNORECASE | re.DOTALL)
    for paragraph in paragraphs:
        text = clean_text(paragraph)
        if len(text) >= MIN_SUMMARY_CHARS:
            return text
    return ""


def fetch_article_summary(url: str, customer: str, topic: str, title: str, source: str, fallback: str) -> str:
    candidates = [fallback]
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 semiconductor-intelligence-report/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=ARTICLE_TIMEOUT) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            page = response.read(900_000).decode(charset, errors="replace")
        candidates.insert(0, extract_first_paragraph(page))
        candidates.insert(0, extract_meta_description(page))
    except (urllib.error.URLError, TimeoutError, UnicodeDecodeError, ValueError) as exc:
        print(f"warning: article summary fallback for {url}: {exc}", file=sys.stderr)

    for candidate in candidates:
        if useful_summary(candidate, title, source):
            return trim_summary(candidate)
    return headline_based_summary(customer, topic, title, source)


def parse_date(value: str) -> str:
    if not value:
        return datetime.now(timezone.utc).date().isoformat()
    try:
        return email.utils.parsedate_to_datetime(value).date().isoformat()
    except (TypeError, ValueError):
        return datetime.now(timezone.utc).date().isoformat()


def google_news_rss_url(query: str) -> str:
    encoded = urllib.parse.quote_plus(f"{query} when:14d")
    return f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"


def fetch_feed(query: str, timeout: int) -> list[dict[str, str]]:
    request = urllib.request.Request(
        google_news_rss_url(query),
        headers={"User-Agent": "semiconductor-intelligence-agent/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read()

    root = ET.fromstring(payload)
    records = []
    for item in root.findall("./channel/item"):
        title = clean_text(item.findtext("title", ""))
        summary = clean_text(item.findtext("description", ""))
        url = item.findtext("link", "")
        source_node = item.find("source")
        source = clean_text(source_node.text if source_node is not None else "Google News")
        published = parse_date(item.findtext("pubDate", ""))
        if title and url:
            records.append(
                {
                    "title": title,
                    "summary": summary,
                    "url": url,
                    "source": source,
                    "published": published,
                }
            )
    return records


def customer_terms(customer: str) -> list[str]:
    if customer in CUSTOMER_ALIASES:
        return CUSTOMER_ALIASES[customer]
    return [customer.lower()]


def matches_customer(customer: str, title: str, summary: str) -> bool:
    haystack = f"{title} {summary}".lower()
    return any(term.lower() in haystack for term in customer_terms(customer))


def impact_score(customer: str, topic: str, title: str, summary: str) -> int:
    haystack = f"{customer} {topic} {title} {summary}".lower()
    score = 42 + TOPIC_WEIGHTS.get(topic, 10)
    for keyword, value in ETCH_KEYWORDS.items():
        if keyword in haystack:
            score += value
    return max(1, min(score, 99))


def conductor_etch_implication(customer: str, topic: str, title: str) -> str:
    lowered = f"{topic} {title}".lower()
    if "asic" in lowered or "custom silicon" in lowered:
        return f"{customer}: custom silicon demand can translate into foundry starts, packaging capacity, and advanced-node etch pull."
    if "ai accelerator" in lowered:
        return f"{customer}: AI accelerator momentum is a leading indicator for CoWoS/HBM constraints and etch-intensive foundry demand."
    if "hbm" in lowered:
        return f"{customer}: HBM demand can pull advanced DRAM capacity and packaging intensity forward, lifting conductor etch relevance."
    if "euv" in lowered or "2nm" in lowered or "18a" in lowered or "14a" in lowered:
        return f"{customer}: roadmap progress points to leading-edge process complexity where conductor etch timing matters."
    if "capex" in lowered or "investment" in lowered:
        return f"{customer}: CapEx language is a direct read-through to WFE budgets, timing, and tool allocation."
    if "pricing" in lowered or "dram" in lowered or "nand" in lowered:
        return f"{customer}: memory price and utilization momentum help estimate when deferred etch demand may return."
    if "packaging" in lowered:
        return f"{customer}: advanced packaging expansion can reshape adjacent process demand and customer priority."
    if "eda" in lowered or "ip" in lowered:
        return f"{customer}: EDA/IP activity is an upstream signal for design starts that can become future foundry and etch demand."
    if "automotive" in lowered:
        return f"{customer}: automotive and power-semiconductor demand can influence specialty fab loading and mature-node etch utilization."
    return f"{customer}: fab and capacity signals should be checked for ramp timing, layer complexity, and tool pull-ins."


def build_report(watchlist: dict, timeout: int, max_signals: int) -> dict:
    generated_at = datetime.now(timezone.utc).isoformat()
    seen_urls: set[str] = set()
    items: list[Item] = []

    for query in watchlist["queries"]:
        try:
            records = fetch_feed(query["query"], timeout)
        except Exception as exc:
            print(f"warning: failed query {query['query']!r}: {exc}", file=sys.stderr)
            continue

        for record in records[:DEFAULT_MAX_PER_QUERY]:
            if record["url"] in seen_urls:
                continue
            if not matches_customer(query["customer"], record["title"], record["summary"]):
                continue
            seen_urls.add(record["url"])
            score = impact_score(query["customer"], query["topic"], record["title"], record["summary"])
            items.append(
                Item(
                    customer=query["customer"],
                    topic=query["topic"],
                    title=record["title"],
                    summary=record["summary"][:320],
                    url=record["url"],
                    source=record["source"],
                    published=record["published"],
                    score=score,
                )
            )

    ranked = sorted(items, key=lambda item: item.score, reverse=True)[:max_signals]
    if not ranked:
        raise RuntimeError("No RSS records were collected. Check network access or query configuration.")

    for item in ranked:
        item.summary = fetch_article_summary(
            item.url,
            item.customer,
            item.topic,
            item.title,
            item.source,
            item.summary,
        )

    brief = [
        {
            "headline": item.title,
            "implication": conductor_etch_implication(item.customer, item.topic, item.title),
        }
        for item in ranked[:5]
    ]

    return {
        "generated_at": generated_at,
        "customers": watchlist["customers"],
        "customer_groups": watchlist.get("customer_groups", {}),
        "topics": watchlist["topics"],
        "brief": brief,
        "signals": [
            {
                "customer": item.customer,
                "topic": item.topic,
                "title": item.title,
                "summary": item.summary or conductor_etch_implication(item.customer, item.topic, item.title),
                "impact_score": item.score,
                "date": item.published,
                "source": item.source,
                "url": item.url,
            }
            for item in ranked
        ],
    }


def write_markdown(report: dict, path: Path) -> None:
    lines = [
        "# Semiconductor Intelligence Report",
        "",
        f"Generated: {report['generated_at']}",
        "",
        f"Tracked entities: {len(report['customers'])}",
        "",
        "## What matters to conductor etch this week",
        "",
    ]
    for item in report["brief"]:
        lines.append(f"- **{item['headline']}** - {item['implication']}")
    lines.extend(["", "## Ranked signals", ""])
    for signal in report["signals"]:
        lines.extend(
            [
                f"### {signal['impact_score']} - {signal['customer']} - {signal['topic']}",
                "",
                f"[{signal['title']}]({signal['url']})",
                "",
                textwrap.fill(signal["summary"], width=96),
                "",
                f"Source: {signal['source']} | Date: {signal['date']}",
                "",
            ]
        )
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
