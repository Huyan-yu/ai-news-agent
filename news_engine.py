# 新闻抓取引擎: 多源聚合 -> 清洗 -> 按日期 JSON 落到 outbox/today/
# 模型后续会 read_file 这些文件再做筛选/摘要。
# 源不可达时容错跳过, 保证至少有内容可写。

import json
import re
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent
OUTBOX = BASE / "outbox"

# 一批对"AI 新闻"友好的源(优先 RSS, 稳定且无需鉴权)
NEWS_SOURCES = [
    # (name, rss_url, kind)
    ("OpenAI Blog", "https://openai.com/blog/rss.xml", "rss"),
    ("Hugging Face Blog", "https://huggingface.co/blog/feed.xml", "rss"),
    ("Anthropic News", "https://www.anthropic.com/news/rss", "rss"),
    ("MIT Tech Review AI", "https://www.technologyreview.com/topic/ai/feed", "rss"),
    ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "rss"),
    ("Ars Technica AI", "https://arstechnica.com/ai/feed/", "rss"),
    ("Google AI Blog", "https://blog.google/technology/ai/rss/", "rss"),
    ("Microsoft Research Blog", "https://www.microsoft.com/en-us/research/feed/", "rss"),
]

AI_KEYWORDS = [
    "ai", "a.i.", "artificial intelligence", "gpt", "llm", "model", "openai",
    "anthropic", "claude", "gemini", "chatgpt", "diffusion", "neural",
    "machine learning", "deep learning", "agent", "transformer",
]


def _clean(s: str) -> str:
    """去掉 CDATA/HTML 标签与常见实体, 折叠空白。"""
    s = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", s, flags=re.DOTALL)
    s = re.sub(r"<[^>]+>", " ", s)
    for a, b in [
        ("&amp;", "&"), ("&#8230;", "..."), ("&lt;", "<"), ("&gt;", ">"),
        ("&quot;", '"'), ("&#8217;", "'"), ("&#8216;", "'"), ("&rsquo;", "'"),
        ("&#8211;", "-"), ("&#8212;", "-"), ("&nbsp;", " "),
    ]:
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


def _fetch_rss(url: str, timeout: int = 12) -> list[dict]:
    """抓 RSS/Atom (兼容 CDATA 与两种 feed), 返回最近若干条。"""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (ai-news-agent)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read(500_000).decode("utf-8", "replace")

    items = []
    for m in re.finditer(r"<(?:item|entry)\b.*?</(?:item|entry)>", raw, re.DOTALL):
        chunk = m.group(0)
        t_m = re.search(r"<title[^>]*>(.*?)</title>", chunk, re.DOTALL)
        link_m = (
            re.search(r'<link[^>]*href="([^"]+)"', chunk)
            or re.search(r"<link>(.*?)</link>", chunk, re.DOTALL)
        )
        pub_m = re.search(
            r"<(?:pubDate|published|updated)>(.*?)</(?:pubDate|published|updated)>",
            chunk, re.DOTALL,
        )
        sm_m = re.search(r"<summary[^>]*>(.*?)</summary>", chunk, re.DOTALL)
        cd_m = re.search(r"<content[^>]*>(.*?)</content>", chunk, re.DOTALL)
        summary_src = sm_m.group(1) if sm_m else (cd_m.group(1) if cd_m else "")
        items.append(
            {
                "title": _clean(t_m.group(1))[:200] if t_m else "",
                "link": _clean(link_m.group(1)) if link_m else "",
                "published": _clean(pub_m.group(1)) if pub_m else "",
                "summary": _clean(summary_src)[:300],
            }
        )
    return items


def _looks_ai(item: dict) -> bool:
    blob = f"{item.get('title','')} {item.get('summary','')}".lower()
    return any(k in blob for k in AI_KEYWORDS)


def collect_news(max_items_per_source: int = 6, min_age_days: int = 3) -> dict:
    """聚合各源近 min_age_days 天的 AI 相关新闻。"""
    cutoff = datetime.now() - timedelta(days=min_age_days)
    all_items: list[dict] = []
    errors: list[str] = []

    for name, url, kind in NEWS_SOURCES:
        try:
            raw = _fetch_rss(url)
            for it in raw[:max_items_per_source]:
                it["source"] = name
                it["fetched_at"] = datetime.now().isoformat(timespec="seconds")
                all_items.append(it)
        except Exception as e:
            errors.append(f"{name}: {type(e).__name__} {str(e)[:80]}")

    # 过滤明显非 AI
    ai_items = [i for i in all_items if _looks_ai(i)]
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "min_age_days": min_age_days,
        "total_raw": len(all_items),
        "ai_items": ai_items,
        "source_errors": errors,
        "sources": [s[0] for s in NEWS_SOURCES],
    }
    return payload


def save_to_outbox(payload: dict) -> Path:
    """把聚合结果按 日期 写到 outbox/today/YYYY-MM-DD.json。"""
    day = datetime.now().strftime("%Y-%m-%d")
    OUTBOX.mkdir(parents=True, exist_ok=True)
    target = OUTBOX / "today" / f"{day}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return target


def run() -> dict:
    """抓取 + 落盘, 返回摘要。"""
    t0 = time.time()
    payload = collect_news()
    p = save_to_outbox(payload)
    return {
        "file": str(p),
        "ai_items": len(payload["ai_items"]),
        "raw_items": payload["total_raw"],
        "errors": payload["source_errors"],
        "elapsed_sec": round(time.time() - t0, 1),
    }


if __name__ == "__main__":
    out = run()
    print(json.dumps(out, ensure_ascii=False, indent=1))
