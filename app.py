"""
AI Research Digest — Self-contained public web app
Fetches and generates live — no local JSON needed.
Run with: streamlit run app.py
"""
import json
import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import streamlit as st
import google.generativeai as genai

# ── Config ────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="AI Research Digest", page_icon="📡", layout="centered")

GEMINI_KEY = os.getenv("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY", "")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    llm = genai.GenerativeModel("gemini-2.5-flash")
else:
    llm = None

LAB_FEEDS = [
    {"name": "OpenAI",             "url": "https://openai.com/news/rss.xml",                    "limit": 8},
    {"name": "Google DeepMind",    "url": "https://deepmind.google/blog/rss.xml",               "limit": 8},
    {"name": "Hugging Face",       "url": "https://huggingface.co/blog/feed.xml",               "limit": 8},
    {"name": "Google Research",    "url": "https://research.google/blog/rss/",                  "limit": 8},
    {"name": "Microsoft Research", "url": "https://www.microsoft.com/en-us/research/blog/feed/","limit": 8},
]

LAB_ARXIV = [
    {"name": "Anthropic",  "query": "ti:claude+OR+(au:anthropic+AND+cat:cs.AI)",          "limit": 4},
    {"name": "Meta AI",    "query": "au:meta+AND+(cat:cs.AI+OR+cat:cs.LG+OR+cat:cs.CL)", "limit": 4},
    {"name": "Mistral",    "query": "ti:mistral+AND+(cat:cs.AI+OR+cat:cs.LG)",            "limit": 3},
]

st.markdown("""
<style>
  .digest-hero { text-align:center; padding:2rem 0 1rem; }
  .digest-hero h1 { font-size:2rem; font-weight:700; margin-bottom:0.3rem; }
  .digest-hero .week { font-size:0.9rem; color:#888; margin-bottom:0.5rem; }
  .digest-hero .tagline { font-size:1rem; color:#555; font-style:italic; }
  .digest-item { border:1px solid #e8e0d5; border-radius:10px; padding:1.4rem 1.6rem; margin-bottom:0.5rem; background:white; }
  .item-header { display:flex; align-items:flex-start; justify-content:space-between; gap:1rem; margin-bottom:0.6rem; }
  .item-num { font-size:0.75rem; font-weight:600; color:#aaa; flex-shrink:0; padding-top:3px; }
  .item-title { font-size:1.05rem; font-weight:600; color:#1a1612; line-height:1.3; flex:1; }
  .rel-badge { display:inline-block; border-radius:4px; padding:3px 10px; font-size:0.72rem; font-weight:600; flex-shrink:0; }
  .rel-act   { background:#e1f5ee; color:#0f6e56; }
  .rel-watch { background:#e6f1fb; color:#185fa5; }
  .rel-skip  { background:#f2f0ec; color:#888; }
  .item-summary { font-size:0.9rem; color:#555; line-height:1.65; margin-bottom:0.8rem; }
  .item-takeaway { background:#faf7f2; border-left:3px solid #c4713a; border-radius:0 8px 8px 0; padding:0.8rem 1rem; margin-bottom:0.8rem; }
  .takeaway-label { font-size:0.7rem; font-weight:600; color:#c4713a; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:4px; }
  .takeaway-text { font-size:0.9rem; color:#3a3a3a; line-height:1.6; }
  .item-footer { display:flex; align-items:center; justify-content:space-between; font-size:0.78rem; color:#aaa; }
  .qa-bubble-user { background:#f0f4ff; border-radius:10px 10px 2px 10px; padding:0.7rem 1rem; margin:0.4rem 0; font-size:0.88rem; color:#1a1612; }
  .qa-bubble-ai { background:#faf7f2; border-left:3px solid #c4713a; border-radius:10px 10px 10px 2px; padding:0.7rem 1rem; margin:0.4rem 0; font-size:0.88rem; color:#3a3a3a; line-height:1.65; }
  .subscribe-box { background:#1a1612; color:white; border-radius:12px; padding:2rem; text-align:center; margin:2rem 0; }
  .subscribe-box h3 { color:white; margin-bottom:0.5rem; }
  .subscribe-box p { color:rgba(255,255,255,0.6); font-size:0.9rem; margin-bottom:1rem; }
</style>
""", unsafe_allow_html=True)


# ── Data fetching ─────────────────────────────────────────────────────────────
def parse_rss(url, source, limit=8):
    items = []
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; AI-Digest-Bot/1.0)"}
        resp = requests.get(url, timeout=10, headers=headers)
        if resp.status_code != 200:
            return []
        root = ET.fromstring(resp.content)
        ns   = {"atom": "http://www.w3.org/2005/Atom"}
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
                    items.append({"title": title.strip(), "summary": summary.strip()[:500],
                                  "link": link.strip(), "authors": source,
                                  "date": date[:10], "source": source})
        else:
            for i in list(root.findall(".//item"))[:limit]:
                title   = i.findtext("title")       or ""
                summary = i.findtext("description") or ""
                link    = i.findtext("link")        or ""
                date    = i.findtext("pubDate")     or ""
                if title and link:
                    items.append({"title": title.strip(), "summary": summary.strip()[:500],
                                  "link": link.strip(), "authors": source,
                                  "date": date[:10], "source": source})
    except Exception:
        pass
    return items


def fetch_arxiv(query, source, max_results=4):
    papers = []
    try:
        url = (f"http://export.arxiv.org/api/query?search_query={query}"
               f"&sortBy=submittedDate&sortOrder=descending&max_results={max_results}")
        resp = requests.get(url, timeout=10)
        root = ET.fromstring(resp.content)
        ns   = {"atom": "http://www.w3.org/2005/Atom"}
        for e in root.findall("atom:entry", ns):
            title   = e.find("atom:title",   ns).text.strip().replace("\n", " ")
            summary = e.find("atom:summary", ns).text.strip().replace("\n", " ")
            link    = e.find("atom:id",      ns).text.strip()
            authors = [a.find("atom:name", ns).text for a in e.findall("atom:author", ns)]
            pub     = e.find("atom:published", ns).text[:10]
            papers.append({"title": title, "source": source,
                           "summary": summary[:500], "link": link,
                           "authors": ", ".join(authors[:2]) + (" et al." if len(authors) > 2 else ""),
                           "date": pub})
    except Exception:
        pass
    return papers


def deduplicate(items):
    seen, unique = set(), []
    for item in items:
        key = item["title"].lower().strip()[:80]
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


@st.cache_data(ttl=60*60*24*7, show_spinner=False)  # cache for 7 days
def generate_weekly_digest():
    """Fetch sources, select top 5, generate PM takeaways. Cached for 7 days."""
    if not llm:
        return None

    # Fetch all sources
    all_items = []
    for feed in LAB_FEEDS:
        all_items.extend(parse_rss(feed["url"], feed["name"], feed["limit"]))
    for lab in LAB_ARXIV:
        all_items.extend(fetch_arxiv(lab["query"], lab["name"], lab["limit"]))
    # General ArXiv
    general_q = "cat:cs.AI+OR+cat:cs.LG+OR+cat:cs.CL"
    all_items.extend(fetch_arxiv(general_q, "ArXiv", 12))

    all_items = deduplicate(all_items)
    if not all_items:
        return None

    # Select top 5
    titles_block = "\n".join([f"{i+1}. [{item['source']}] {item['title']}"
                               for i, item in enumerate(all_items)])
    select_prompt = (
        f"You are a senior AI product manager curating a weekly digest for other PMs. "
        f"From {len(all_items)} items select 5 most relevant for product managers — "
        f"real implications for product decisions, roadmaps, or competitive positioning.\n"
        f"Include at least 2 from major AI labs. Cover different topics.\n"
        f"Prefer new model releases and research findings over business/partnership news.\n"
        f"Return ONLY a JSON array: [1, 4, 7, 12, 15]. No other text.\n\n{titles_block}"
    )
    try:
        raw = llm.generate_content(select_prompt).text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        indices  = json.loads(raw.strip())
        selected = [all_items[i-1] for i in indices if 1 <= i <= len(all_items)][:5]
    except Exception:
        selected = all_items[:5]

    # Generate takeaways
    digest_items = []
    for item in selected:
        try:
            prompt = (
                f"Write for a weekly AI digest for product managers. "
                f"Practical, specific, jargon-free.\n\n"
                f"Source: {item['source']}\nTitle: {item['title']}\nSummary: {item['summary']}\n\n"
                f"Return ONLY valid JSON:\n"
                '{{\n'
                '  "summary": "2 sentences. Sentence 1: what this IS — name it explicitly. Sentence 2: what it produced/announced.",\n'
                '  "pm_takeaway": "2-3 sentences connecting to real product decisions or roadmap implications.",\n'
                '  "relevance": "Act now" or "Watch" or "Skip",\n'
                '  "relevance_reason": "1 sentence — specific about timeline or trigger"\n'
                '}}'
            )
            raw = llm.generate_content(prompt).text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            g = json.loads(raw.strip())
            digest_items.append({**item, "summary_plain": g["summary"],
                                  "pm_takeaway": g["pm_takeaway"],
                                  "relevance": g["relevance"],
                                  "relevance_reason": g["relevance_reason"]})
        except Exception:
            continue

    # Ensure at least one Skip
    if digest_items and not any(i["relevance"] == "Skip" for i in digest_items):
        digest_items[-1]["relevance"] = "Skip"
        digest_items[-1]["relevance_reason"] = "Included for completeness — lower priority this week."

    return {
        "week_of":      datetime.now().strftime("%B %d, %Y"),
        "generated_at": datetime.now().isoformat(),
        "items":        digest_items,
    }


def ask_about_item(item, question, history):
    if not llm:
        return "LLM not configured."
    context = f"Title: {item['title']}\nSummary: {item.get('summary','')}\nPM Takeaway: {item.get('pm_takeaway','')}"
    history_text = ""
    if history:
        history_text = "\n\nPrevious Q&A:\n" + "\n".join([f"Q: {t['q']}\nA: {t['a']}" for t in history])
    prompt = (
        f"You are helping a product manager understand a research paper or article. "
        f"Answer clearly and practically, connecting to PM implications. "
        f"Be concise (3-5 sentences).\n\n{context}{history_text}\n\nQuestion: {question}"
    )
    return llm.generate_content(prompt).text.strip()


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📡 AI Research Digest")
    st.markdown("*Role-aware intelligence for product managers.*")
    st.divider()
    st.markdown("**About**")
    st.markdown(
        "5 PM-specific AI takeaways, every week. "
        "Built by [Disha Wagle](https://dishawagle.github.io) "
        "as part of a [product case study](https://dishawagle.github.io/digest.html)."
    )
    st.divider()
    if st.button("🔄 Refresh digest", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.caption("Digest refreshes automatically every 7 days.")


# ── Load digest ───────────────────────────────────────────────────────────────
if "qa_history" not in st.session_state:
    st.session_state.qa_history = {}

if not GEMINI_KEY:
    st.error("No GEMINI_API_KEY configured. Add it to Streamlit secrets.")
    st.stop()

with st.spinner("Fetching this week's AI developments..."):
    digest = generate_weekly_digest()

if not digest or not digest.get("items"):
    st.error("Could not generate digest. Check your API key and try refreshing.")
    st.stop()


# ── Hero ──────────────────────────────────────────────────────────────────────
rel_counts = {}
for item in digest["items"]:
    r = item.get("relevance", "Watch")
    rel_counts[r] = rel_counts.get(r, 0) + 1

st.markdown(f"""
<div class="digest-hero">
  <h1>📡 AI Research Digest</h1>
  <p class="week">Week of {digest['week_of']}</p>
  <p class="tagline">5 things product managers need to know this week.<br>
  <small style="color:#aaa;">{rel_counts.get('Act now',0)} act now · {rel_counts.get('Watch',0)} watch · {rel_counts.get('Skip',0)} skip</small></p>
</div>
""", unsafe_allow_html=True)

st.divider()


# ── Items ─────────────────────────────────────────────────────────────────────
for idx, item in enumerate(digest["items"]):
    rel       = item.get("relevance", "Watch")
    rel_lower = rel.lower().replace(" ", "")
    rel_class = {"actnow": "rel-act", "watch": "rel-watch", "skip": "rel-skip"}.get(rel_lower, "rel-watch")
    rel_emoji = {"Act now": "🔴", "Watch": "🟡", "Skip": "⚪"}.get(rel, "🟡")
    reason    = item.get("relevance_reason", "")
    skip_html = f'<p style="font-size:0.8rem;color:#aaa;font-style:italic;margin-top:0.4rem;">Why included: {reason}</p>' if rel == "Skip" and reason else ""

    st.markdown(f"""
    <div class="digest-item">
      <div class="item-header">
        <span class="item-num">0{idx+1}</span>
        <span class="item-title">{item["title"]}</span>
        <span class="rel-badge {rel_class}">{rel_emoji} {rel}</span>
      </div>
      <p class="item-summary">{item.get("summary_plain", item.get("summary", ""))}</p>
      <div class="item-takeaway">
        <div class="takeaway-label">PM takeaway</div>
        <div class="takeaway-text">{item["pm_takeaway"]}</div>
      </div>
      {skip_html}
      <div class="item-footer">
        <span>{item.get("authors", "")} · {item.get("date", "")} · {item.get("source", "")}</span>
        <a href="{item["link"]}" target="_blank" style="color:#c4713a;text-decoration:none;">Read source →</a>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Q&A per item
    with st.expander(f"💬 Ask a question about this"):
        if idx not in st.session_state.qa_history:
            st.session_state.qa_history[idx] = []
        history = st.session_state.qa_history[idx]

        if history:
            for turn in history:
                st.markdown(f'<div class="qa-bubble-user">🙋 {turn["q"]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="qa-bubble-ai">🤖 {turn["a"]}</div>', unsafe_allow_html=True)

        if not history:
            st.caption("Suggested questions:")
            suggestions = ["What exactly is this and how does it work?",
                           "How could this affect my product roadmap?",
                           "Who are the main players building this?"]
            cols = st.columns(3)
            for i, s in enumerate(suggestions):
                with cols[i]:
                    if st.button(s, key=f"s_{idx}_{i}", use_container_width=True):
                        with st.spinner("Thinking..."):
                            ans = ask_about_item(item, s, history)
                        st.session_state.qa_history[idx].append({"q": s, "a": ans})
                        st.rerun()

        q = st.text_input("Your question", placeholder="e.g. How does this compare to GPT-5?",
                          key=f"qi_{idx}", label_visibility="collapsed")
        c1, c2 = st.columns([3, 1])
        with c1:
            if st.button("Ask →", key=f"ask_{idx}", type="primary", use_container_width=True):
                if q.strip():
                    with st.spinner("Thinking..."):
                        ans = ask_about_item(item, q.strip(), history)
                    st.session_state.qa_history[idx].append({"q": q.strip(), "a": ans})
                    st.rerun()
        with c2:
            if history and st.button("Clear", key=f"clr_{idx}", use_container_width=True):
                st.session_state.qa_history[idx] = []
                st.rerun()

    st.markdown("<div style='margin-bottom:0.75rem;'></div>", unsafe_allow_html=True)


# ── Pulse survey ──────────────────────────────────────────────────────────────
st.divider()
st.markdown("### Did this week's digest influence your work?")
st.caption("Helps measure whether this product is actually useful — not just read.")
c1, c2, c3 = st.columns(3)
with c1:
    if st.button("✅ Yes, influenced a decision", use_container_width=True):
        st.success("That's exactly what this is built for.")
with c2:
    if st.button("🔄 Not yet, but it might", use_container_width=True):
        st.info("Good to know — we'll keep tracking.")
with c3:
    if st.button("❌ No, not this week", use_container_width=True):
        st.warning("Noted — helps improve relevance.")


# ── Subscribe ─────────────────────────────────────────────────────────────────
st.divider()
st.markdown('<div class="subscribe-box"><h3>Get this in your inbox every Monday</h3><p>5 PM-specific takeaways. Under 5 minutes. Nothing you can safely ignore.</p></div>', unsafe_allow_html=True)
email = st.text_input("Your email", placeholder="you@company.com")
if st.button("Subscribe →", type="primary"):
    if "@" in email:
        st.success("✓ You're on the list — see you Monday.")
    else:
        st.error("Please enter a valid email address.")
st.caption("Know a PM who'd find this useful? Forward this link.")