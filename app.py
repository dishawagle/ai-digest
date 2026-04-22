"""
AI Research Digest — Public web reader
Run with: streamlit run app.py
"""
import json
import os
import glob
import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
llm = genai.GenerativeModel("gemini-2.5-flash")

APPROVED_FILE = "approved_digest.json"
ARCHIVE_DIR   = "archive"

st.set_page_config(page_title="AI Research Digest", page_icon="📡", layout="centered")

st.markdown("""
<style>
  .digest-hero { text-align: center; padding: 2rem 0 1rem; }
  .digest-hero h1 { font-size: 2rem; font-weight: 700; margin-bottom: 0.3rem; }
  .digest-hero .week { font-size: 0.9rem; color: #888; margin-bottom: 0.5rem; }
  .digest-hero .tagline { font-size: 1rem; color: #555; font-style: italic; }
  .digest-item { border: 1px solid #e8e0d5; border-radius: 10px; padding: 1.4rem 1.6rem; margin-bottom: 0.5rem; background: white; }
  .item-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; margin-bottom: 0.6rem; }
  .item-num { font-size: 0.75rem; font-weight: 600; color: #aaa; flex-shrink: 0; padding-top: 3px; }
  .item-title { font-size: 1.05rem; font-weight: 600; color: #1a1612; line-height: 1.3; flex: 1; }
  .rel-badge { display: inline-block; border-radius: 4px; padding: 3px 10px; font-size: 0.72rem; font-weight: 600; flex-shrink: 0; }
  .rel-act   { background: #e1f5ee; color: #0f6e56; }
  .rel-watch { background: #e6f1fb; color: #185fa5; }
  .rel-skip  { background: #f2f0ec; color: #888; }
  .item-summary { font-size: 0.9rem; color: #555; line-height: 1.65; margin-bottom: 0.8rem; }
  .item-takeaway { background: #faf7f2; border-left: 3px solid #c4713a; border-radius: 0 8px 8px 0; padding: 0.8rem 1rem; margin-bottom: 0.8rem; }
  .takeaway-label { font-size: 0.7rem; font-weight: 600; color: #c4713a; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 4px; }
  .takeaway-text { font-size: 0.9rem; color: #3a3a3a; line-height: 1.6; }
  .item-footer { display: flex; align-items: center; justify-content: space-between; font-size: 0.78rem; color: #aaa; }
  .skip-reason { font-size: 0.8rem; color: #aaa; font-style: italic; margin-top: 0.4rem; }
  .qa-bubble-user { background: #f0f4ff; border-radius: 10px 10px 2px 10px; padding: 0.7rem 1rem; margin: 0.4rem 0; font-size: 0.88rem; color: #1a1612; }
  .qa-bubble-ai { background: #faf7f2; border-radius: 10px 10px 10px 2px; padding: 0.7rem 1rem; margin: 0.4rem 0; font-size: 0.88rem; color: #3a3a3a; line-height: 1.65; border-left: 3px solid #c4713a; }
  .subscribe-box { background: #1a1612; color: white; border-radius: 12px; padding: 2rem; text-align: center; margin: 2rem 0; }
  .subscribe-box h3 { color: white; margin-bottom: 0.5rem; }
  .subscribe-box p { color: rgba(255,255,255,0.6); font-size: 0.9rem; margin-bottom: 1rem; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────
def load_digest(filepath):
    if not os.path.exists(filepath):
        return None
    with open(filepath) as f:
        return json.load(f)

def load_archive():
    if not os.path.exists(ARCHIVE_DIR):
        return []
    files = sorted(glob.glob(f"{ARCHIVE_DIR}/issue_*.json"), reverse=True)
    return [d for f in files if (d := load_digest(f))]

def ask_about_item(item: dict, question: str, history: list) -> str:
    """Ask the LLM a follow-up question about a specific paper/article."""
    context = (
        f"Title: {item['title']}\n"
        f"Summary: {item.get('summary', '')}\n"
        f"PM Takeaway: {item.get('pm_takeaway', '')}\n"
    )
    history_text = ""
    if history:
        history_text = "\n\nPrevious Q&A in this conversation:\n"
        for turn in history:
            history_text += f"Q: {turn['q']}\nA: {turn['a']}\n\n"

    prompt = (
        f"You are an AI assistant helping a product manager understand a research paper or news article. "
        f"Answer clearly and practically — always connect back to product management implications where relevant. "
        f"Be concise (3-5 sentences max) unless the question requires more depth.\n\n"
        f"Article context:\n{context}"
        f"{history_text}\n"
        f"New question: {question}"
    )
    response = llm.generate_content(prompt)
    return response.text.strip()


# ── Load data ─────────────────────────────────────────────────────────────────
digest  = load_digest(APPROVED_FILE)
archive = load_archive()

# Initialise Q&A history in session state — one list per item
if "qa_history" not in st.session_state:
    st.session_state.qa_history = {}


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📡 AI Research Digest")
    st.markdown("*Role-aware intelligence for product managers.*")
    st.divider()
    if archive:
        st.markdown("**Past issues**")
        for past in archive:
            if st.button(f"Issue #{past['issue_number']} · {past['week_of']}", use_container_width=True):
                digest = past
    st.divider()
    st.markdown("**About**")
    st.markdown("5 PM-specific AI takeaways, every Monday morning. Built by [Disha Wagle](https://dishawagle.github.io) as part of a product case study.")


# ── No digest yet ─────────────────────────────────────────────────────────────
if not digest:
    st.markdown('<div class="digest-hero"><h1>📡 AI Research Digest</h1><p class="tagline">Role-aware intelligence for product managers.</p></div>', unsafe_allow_html=True)
    st.info("No published digest yet. Run `python3 engine.py` to generate a draft, then `streamlit run review.py` to approve it.")
    st.stop()


# ── Hero ──────────────────────────────────────────────────────────────────────
rel_counts = {}
for item in digest["items"]:
    r = item.get("relevance", "Watch")
    rel_counts[r] = rel_counts.get(r, 0) + 1

st.markdown(f"""
<div class="digest-hero">
  <h1>📡 AI Research Digest</h1>
  <p class="week">Issue #{digest['issue_number']} · Week of {digest['week_of']}</p>
  <p class="tagline">5 things product managers need to know this week.<br>
  <small style="color:#aaa;">{rel_counts.get('Act now',0)} act now · {rel_counts.get('Watch',0)} watch · {rel_counts.get('Skip',0)} skip</small></p>
</div>
""", unsafe_allow_html=True)

st.divider()


# ── Digest items ──────────────────────────────────────────────────────────────
for idx, item in enumerate(digest["items"]):
    rel       = item.get("relevance", "Watch")
    rel_lower = rel.lower().replace(" ", "")
    rel_class = {"actnow": "rel-act", "watch": "rel-watch", "skip": "rel-skip"}.get(rel_lower, "rel-watch")
    rel_emoji = {"Act now": "🔴", "Watch": "🟡", "Skip": "⚪"}.get(rel, "🟡")
    reason    = item.get("relevance_reason", "")
    skip_html = f'<p class="skip-reason">Why included: {reason}</p>' if rel == "Skip" and reason else ""

    # Render the item card
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
        <span>{item.get("authors", "")} · {item.get("date", "")}</span>
        <a href="{item["link"]}" target="_blank" style="color:#c4713a;text-decoration:none;">Read source →</a>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Q&A section ──────────────────────────────────────────────────────────
    with st.expander(f"💬 Ask a question about this paper"):

        # Initialise history for this item
        if idx not in st.session_state.qa_history:
            st.session_state.qa_history[idx] = []

        history = st.session_state.qa_history[idx]

        # Render conversation history
        if history:
            for turn in history:
                st.markdown(f'<div class="qa-bubble-user">🙋 {turn["q"]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="qa-bubble-ai">🤖 {turn["a"]}</div>', unsafe_allow_html=True)

        # Suggested starter questions
        if not history:
            st.caption("Not sure where to start? Try one of these:")
            suggestions = [
                "What exactly is this and how does it work?",
                "How could this affect my product roadmap?",
                "Who are the main players building this?",
            ]
            cols = st.columns(3)
            for i, suggestion in enumerate(suggestions):
                with cols[i]:
                    if st.button(suggestion, key=f"suggest_{idx}_{i}", use_container_width=True):
                        with st.spinner("Thinking..."):
                            answer = ask_about_item(item, suggestion, history)
                        st.session_state.qa_history[idx].append({"q": suggestion, "a": answer})
                        st.rerun()

        # Free-text question input
        question = st.text_input(
            "Your question",
            placeholder="e.g. How does this compare to what OpenAI is doing?",
            key=f"q_input_{idx}",
            label_visibility="collapsed"
        )
        col_ask, col_clear = st.columns([3, 1])
        with col_ask:
            if st.button("Ask →", key=f"ask_{idx}", type="primary", use_container_width=True):
                if question.strip():
                    with st.spinner("Thinking..."):
                        answer = ask_about_item(item, question.strip(), history)
                    st.session_state.qa_history[idx].append({"q": question.strip(), "a": answer})
                    st.rerun()
                else:
                    st.warning("Type a question first.")
        with col_clear:
            if history and st.button("Clear", key=f"clear_{idx}", use_container_width=True):
                st.session_state.qa_history[idx] = []
                st.rerun()

    st.markdown("<div style='margin-bottom:1rem;'></div>", unsafe_allow_html=True)


# ── Pulse survey ──────────────────────────────────────────────────────────────
st.divider()
st.markdown("### Did this week's digest influence your work?")
st.caption("Your answer measures whether this product is actually useful — not just opened.")
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("✅ Yes, influenced a decision", use_container_width=True):
        st.success("That's exactly what this is built for.")
with col2:
    if st.button("🔄 Not yet, but it might", use_container_width=True):
        st.info("We'll keep tracking.")
with col3:
    if st.button("❌ No, not this week", use_container_width=True):
        st.warning("Noted — helps us improve relevance.")


# ── Subscribe ─────────────────────────────────────────────────────────────────
st.divider()
st.markdown('<div class="subscribe-box"><h3>Get this in your inbox every Monday</h3><p>5 PM-specific takeaways. Under 5 minutes. Nothing you can safely ignore.</p></div>', unsafe_allow_html=True)

email = st.text_input("Your email", placeholder="you@company.com")
if st.button("Subscribe →", type="primary"):
    if "@" in email:
        subscribers_file = "subscribers.json"
        subscribers = []
        if os.path.exists(subscribers_file):
            with open(subscribers_file) as f:
                subscribers = json.load(f)
        if email not in subscribers:
            subscribers.append(email)
            with open(subscribers_file, "w") as f:
                json.dump(subscribers, f)
            st.success(f"✓ Subscribed! You'll receive Issue #{digest['issue_number'] + 1} next Monday.")
        else:
            st.info("You're already subscribed.")
    else:
        st.error("Please enter a valid email address.")

st.caption("Know a PM who'd find this useful? Forward this link to them.")


# ── Archive on first load ─────────────────────────────────────────────────────
if digest.get("status") == "approved":
    archive_path = f"{ARCHIVE_DIR}/issue_{digest['issue_number']:03d}.json"
    if not os.path.exists(archive_path):
        os.makedirs(ARCHIVE_DIR, exist_ok=True)
        with open(archive_path, "w") as f:
            json.dump(digest, f, indent=2)