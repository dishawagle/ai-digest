import os
import json
import hashlib
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.5-flash")

ARXIV_CATEGORIES  = ["cs.AI", "cs.LG", "cs.CL"]
MAX_ARXIV_GENERAL = 15
FINAL_ITEMS       = 5
OUTPUT_FILE       = "draft_digest.json"
PUBLISHED_LOG     = "published_items.json"  # tracks all previously published items

# ── Verified RSS feeds (limit = max items to take from each) ─────────────────
LAB_FEEDS = [
    {"name": "OpenAI",             "url": "https://openai.com/news/rss.xml",                    "limit": 10},
    {"name": "Google DeepMind",    "url": "https://deepmind.google/blog/rss.xml",               "limit": 10},
    {"name": "Hugging Face",       "url": "https://huggingface.co/blog/feed.xml",               "limit": 10},
    {"name": "Google Research",    "url": "https://research.google/blog/rss/",                  "limit": 10},
    {"name": "Microsoft Research", "url": "https://www.microsoft.com/en-us/research/blog/feed/","limit": 10},
    {"name": "AWS AI",             "url": "https://aws.amazon.com/blogs/machine-learning/feed/","limit": 10},
]

# ArXiv searches for labs without RSS (Anthropic, Meta, Mistral)
LAB_ARXIV = [
    {"name": "Anthropic",  "query": "ti:claude+OR+(au:anthropic+AND+cat:cs.AI)",          "limit": 5},
    {"name": "Meta AI",    "query": "au:meta+AND+(cat:cs.AI+OR+cat:cs.LG+OR+cat:cs.CL)", "limit": 5},
    {"name": "Mistral",    "query": "ti:mistral+AND+(cat:cs.AI+OR+cat:cs.LG)",            "limit": 5},
    {"name": "Perplexity", "query": "ti:perplexity+AND+(cat:cs.AI+OR+cat:cs.IR)",         "limit": 3},
]


# ── Published items log ───────────────────────────────────────────────────────
def load_published_log() -> set:
    """Load set of item fingerprints that have already been published."""
    if not os.path.exists(PUBLISHED_LOG):
        return set()
    with open(PUBLISHED_LOG) as f:
        data = json.load(f)
    return set(data.get("fingerprints", []))


def save_published_log(existing: set, new_items: list[dict]):
    """Append newly published item fingerprints to the log."""
    for item in new_items:
        existing.add(fingerprint(item))
    with open(PUBLISHED_LOG, "w") as f:
        json.dump({"fingerprints": list(existing)}, f, indent=2)


def fingerprint(item: dict) -> str:
    """Create a stable identifier for an item based on its title + link."""
    raw = (item.get("title", "") + item.get("link", "")).lower().strip()
    return hashlib.md5(raw.encode()).hexdigest()


# ── Fetch helpers ─────────────────────────────────────────────────────────────
def parse_rss(url: str, source: str, limit: int = 10) -> list[dict]:
    """Parse RSS or Atom feed, return up to `limit` items."""
    items = []
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; AI-Digest-Bot/1.0)"}
        resp = requests.get(url, timeout=12, headers=headers)
        if resp.status_code != 200:
            print(f"    ! {source}: HTTP {resp.status_code}")
            return []
        root = ET.fromstring(resp.content)
        ns   = {"atom": "http://www.w3.org/2005/Atom"}

        # Atom format
        entries = root.findall(".//atom:entry", ns)
        if entries:
            for e in entries[:limit]:
                title   = e.findtext("atom:title",   namespaces=ns) or ""
                summary = (e.findtext("atom:summary", namespaces=ns) or
                           e.findtext("atom:content", namespaces=ns) or "")
                link_el = e.find("atom:link", ns)
                link    = link_el.get("href", "") if link_el is not None else ""
                date    = (e.findtext("atom:published", namespaces=ns) or
                           e.findtext("atom:updated",   namespaces=ns) or "")
                if title and link:
                    items.append({"title": title.strip(), "summary": summary.strip()[:600],
                                  "link": link.strip(), "authors": source,
                                  "date": date[:10], "source": source})
        else:
            # RSS format
            for i in list(root.findall(".//item"))[:limit]:
                title   = i.findtext("title")       or ""
                summary = i.findtext("description") or ""
                link    = i.findtext("link")        or ""
                date    = i.findtext("pubDate")     or ""
                if title and link:
                    items.append({"title": title.strip(), "summary": summary.strip()[:600],
                                  "link": link.strip(), "authors": source,
                                  "date": date[:10], "source": source})
    except Exception as e:
        print(f"    ! {source}: {e}")
    return items


def fetch_arxiv(query: str, source: str, max_results: int = 5) -> list[dict]:
    """Fetch papers from ArXiv by search query."""
    url = (f"http://export.arxiv.org/api/query?search_query={query}"
           f"&sortBy=submittedDate&sortOrder=descending&max_results={max_results}")
    papers = []
    try:
        resp = requests.get(url, timeout=12)
        root = ET.fromstring(resp.content)
        ns   = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("atom:entry", ns):
            title   = entry.find("atom:title",   ns).text.strip().replace("\n", " ")
            summary = entry.find("atom:summary", ns).text.strip().replace("\n", " ")
            link    = entry.find("atom:id",      ns).text.strip()
            authors = [a.find("atom:name", ns).text for a in entry.findall("atom:author", ns)]
            pub     = entry.find("atom:published", ns).text[:10]
            papers.append({"title": title, "source": source,
                           "summary": summary[:600] + "..." if len(summary) > 600 else summary,
                           "link": link,
                           "authors": ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else ""),
                           "date": pub})
    except Exception as e:
        print(f"    ! {source} ArXiv: {e}")
    return papers


def fetch_news() -> list[dict]:
    """Fetch AI news via NewsAPI (optional — free tier at newsapi.org)."""
    api_key = os.getenv("NEWS_API_KEY", "")
    if not api_key:
        return []
    since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    url = (f"https://newsapi.org/v2/everything?q=artificial+intelligence+OR+large+language+model"
           f"&from={since}&sortBy=relevancy&pageSize=10&language=en&apiKey={api_key}")
    try:
        data = requests.get(url, timeout=10).json()
        return [{"title": a["title"], "summary": a.get("description", ""),
                 "link": a["url"], "authors": a.get("source", {}).get("name", ""),
                 "date": a.get("publishedAt", "")[:10], "source": "News"}
                for a in data.get("articles", []) if a.get("title") and a.get("description")]
    except Exception as e:
        print(f"    ! NewsAPI: {e}")
        return []


def deduplicate_within_run(items: list[dict]) -> list[dict]:
    """Remove duplicates within the current fetch based on title."""
    seen, unique = set(), []
    for item in items:
        key = item["title"].lower().strip()[:80]
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def remove_previously_published(items: list[dict], published: set) -> list[dict]:
    """Filter out items already published in a previous issue."""
    return [i for i in items if fingerprint(i) not in published]


# ── LLM calls ─────────────────────────────────────────────────────────────────
def select_top_items(items: list[dict], n: int = FINAL_ITEMS) -> list[dict]:
    print(f"\nSelecting top {n} items from {len(items)} candidates...")
    titles_block = "\n".join([f"{i+1}. [{item['source']}] {item['title']}"
                               for i, item in enumerate(items)])
    prompt = (
        f"You are a senior AI product manager curating a weekly digest for other PMs. "
        f"From {len(items)} items, select the {n} most relevant for product managers — "
        f"with real implications for product decisions, roadmaps, or competitive positioning.\n\n"
        f"RULES:\n"
        f"1. Include at least 2 items from major AI labs (OpenAI, Anthropic, Google, Meta, Mistral) if available.\n"
        f"2. Cover different topics — not 5 items on the same theme.\n"
        f"3. Prefer new model releases, capability announcements, and research findings.\n"
        f"4. Avoid press releases, partnership announcements, and business news unless genuinely product-relevant.\n\n"
        f"Return ONLY a JSON array of item numbers: [1, 4, 7, 12, 15]. No other text.\n\n{titles_block}"
    )
    response = model.generate_content(prompt)
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    indices  = json.loads(raw.strip())
    selected = [items[i - 1] for i in indices if 1 <= i <= len(items)]
    print(f"  -> Sources: {[items[i-1]['source'] for i in indices if 1 <= i <= len(items)]}")
    return selected[:n]


def generate_takeaway(item: dict) -> dict:
    print(f"  Generating: {item['title'][:65]}...")
    prompt = (
        f"Write for a weekly AI digest read exclusively by product managers at tech companies. "
        f"Be practical, specific, jargon-free.\n\n"
        f"Source: {item['source']}\nTitle: {item['title']}\nSummary: {item['summary']}\n\n"
        f"Return ONLY valid JSON, no markdown:\n"
        '{{\n'
        '  "summary": "2 sentences. Sentence 1: what this IS — name the model/framework/system explicitly and what it does. Sentence 2: what result or announcement it produced.",\n'
        '  "pm_takeaway": "2-3 sentences. Why a PM should care, what to do or watch for, optional concrete example.",\n'
        '  "relevance": "Act now" or "Watch" or "Skip",\n'
        '  "relevance_reason": "1 sentence — specific about timeline or trigger"\n'
        '}}'
    )
    response = model.generate_content(prompt)
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    g = json.loads(raw.strip())
    return {**item, "summary_plain": g["summary"], "pm_takeaway": g["pm_takeaway"],
            "relevance": g["relevance"], "relevance_reason": g["relevance_reason"],
            "approved": False, "edited": False}


# ── Main pipeline ─────────────────────────────────────────────────────────────
def build_draft_digest():
    print("=" * 60)
    print("AI Research Digest - Draft Builder")
    print("=" * 60)

    # Load previously published fingerprints
    published = load_published_log()
    print(f"Previously published items: {len(published)}")

    # Fetch from all sources
    print("\nFetching from RSS feeds...")
    rss_items = []
    for feed in LAB_FEEDS:
        items = parse_rss(feed["url"], feed["name"], feed["limit"])
        print(f"  -> {feed['name']}: {len(items)} items")
        rss_items.extend(items)

    print("\nFetching lab papers from ArXiv...")
    arxiv_lab = []
    for lab in LAB_ARXIV:
        papers = fetch_arxiv(lab["query"], lab["name"], lab["limit"])
        print(f"  -> {lab['name']}: {len(papers)} papers")
        arxiv_lab.extend(papers)

    print("\nFetching general ArXiv papers...")
    query_general = "+OR+".join([f"cat:{c}" for c in ARXIV_CATEGORIES])
    arxiv_general = fetch_arxiv(query_general, "ArXiv", MAX_ARXIV_GENERAL)
    print(f"  -> ArXiv general: {len(arxiv_general)} papers")

    news = fetch_news()
    if news:
        print(f"  -> News: {len(news)} articles")
    else:
        print("  -> NewsAPI: not configured (optional)")
        print("     To add news: get a free key at newsapi.org, then add NEWS_API_KEY=... to .env")

    all_items = rss_items + arxiv_lab + arxiv_general + news
    print(f"\nTotal raw items fetched: {len(all_items)}")

    # Deduplicate within this run
    all_items = deduplicate_within_run(all_items)
    print(f"After deduplication within run: {len(all_items)}")

    # Remove items already published in previous issues
    all_items = remove_previously_published(all_items, published)
    print(f"After removing previously published: {len(all_items)}")

    if not all_items:
        print("ERROR: No new items found. All candidates were already published.")
        return

    # Select and generate
    selected = select_top_items(all_items, n=FINAL_ITEMS)

    print(f"\nGenerating PM takeaways...")
    digest_items = []
    for item in selected:
        try:
            digest_items.append(generate_takeaway(item))
        except Exception as e:
            print(f"  Failed: {e}")

    # Ensure at least one Skip
    if not any(i["relevance"] == "Skip" for i in digest_items) and digest_items:
        digest_items[-1]["relevance"] = "Skip"
        digest_items[-1]["relevance_reason"] = "Included for completeness — lower priority this week."

    # Determine issue number
    issue_num = 1
    if os.path.exists("approved_digest.json"):
        with open("approved_digest.json") as f:
            prev = json.load(f)
        issue_num = prev.get("issue_number", 0) + 1

    draft = {
        "issue_number": issue_num,
        "week_of":      datetime.now().strftime("%B %d, %Y"),
        "generated_at": datetime.now().isoformat(),
        "status":       "draft",
        "items":        digest_items,
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(draft, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"Draft saved to {OUTPUT_FILE} (Issue #{issue_num})")
    print(f"  Sources: {[i['source'] for i in digest_items]}")
    for r in ["Act now", "Watch", "Skip"]:
        count = sum(1 for i in digest_items if i["relevance"] == r)
        print(f"    {r}: {count}")
    print(f"\nNote: Run 'streamlit run review.py' to review and approve.")
    print(f"      After approval, published items are logged to avoid repeats.")
    print("=" * 60)


if __name__ == "__main__":
    build_draft_digest()