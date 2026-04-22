"""
Review dashboard — internal tool for approving and editing digest items
before publishing. Run with: streamlit run review.py
"""
import json
import os
import streamlit as st
from datetime import datetime

DRAFT_FILE     = "draft_digest.json"
APPROVED_FILE  = "approved_digest.json"

st.set_page_config(page_title="Digest Review", layout="wide")

st.markdown("""
<style>
  .item-card { background: #f8f9fa; border-radius: 10px; padding: 1.2rem 1.4rem; margin-bottom: 1rem; border-left: 4px solid #ddd; }
  .item-card.act  { border-left-color: #1D9E75; }
  .item-card.watch { border-left-color: #378ADD; }
  .item-card.skip { border-left-color: #aaa; }
  .item-card.approved { background: #f0faf5; }
  .rel-act  { color: #1D9E75; font-weight: 600; font-size: 0.8rem; }
  .rel-watch { color: #378ADD; font-weight: 600; font-size: 0.8rem; }
  .rel-skip { color: #888; font-weight: 600; font-size: 0.8rem; }
  h4 { margin: 0 0 0.3rem 0; font-size: 1rem; }
</style>
""", unsafe_allow_html=True)

# ── Load draft ────────────────────────────────────────────────────────────────
if not os.path.exists(DRAFT_FILE):
    st.error(f"No draft found. Run `python3 engine.py` first to generate a draft.")
    st.stop()

with open(DRAFT_FILE) as f:
    digest = json.load(f)

# ── Header ────────────────────────────────────────────────────────────────────
col1, col2 = st.columns([3, 1])
with col1:
    st.title("📋 Digest Review Dashboard")
    st.caption(f"Issue #{digest['issue_number']} · Week of {digest['week_of']} · Generated {digest['generated_at'][:16]}")
with col2:
    approved_count = sum(1 for i in digest["items"] if i.get("approved"))
    total = len(digest["items"])
    st.metric("Approved", f"{approved_count} / {total}")
    if approved_count == total:
        st.success("All items approved!")

st.divider()

# ── Items ─────────────────────────────────────────────────────────────────────
for idx, item in enumerate(digest["items"]):
    rel = item.get("relevance", "Watch").lower().replace(" ", "")
    approved = item.get("approved", False)

    css_class = f"item-card {rel[:4]}" + (" approved" if approved else "")
    rel_class  = f"rel-{rel[:4]}"

    with st.expander(
        f"{'✅' if approved else '⬜'} {idx+1}. {item['title'][:80]}...",
        expanded=not approved
    ):
        col_left, col_right = st.columns([2, 1])

        with col_left:
            # Title
            new_title = st.text_input(
                "Title", value=item["title"], key=f"title_{idx}"
            )

            # Summary
            st.markdown("**Plain-English summary**")
            new_summary = st.text_area(
                "Summary", value=item["summary_plain"],
                height=80, key=f"summary_{idx}"
            )

            # PM Takeaway
            st.markdown("**PM takeaway** ← the most important field")
            new_takeaway = st.text_area(
                "PM Takeaway", value=item["pm_takeaway"],
                height=100, key=f"takeaway_{idx}"
            )

        with col_right:
            st.markdown("**Relevance signal**")
            new_relevance = st.selectbox(
                "Relevance", ["Act now", "Watch", "Skip"],
                index=["Act now", "Watch", "Skip"].index(item.get("relevance", "Watch")),
                key=f"rel_{idx}"
            )

            new_rel_reason = st.text_area(
                "Reason for signal",
                value=item.get("relevance_reason", ""),
                height=80, key=f"rel_reason_{idx}"
            )

            st.markdown("**Source**")
            st.markdown(f"[{item.get('authors', 'Unknown')} · {item.get('date', '')}]({item['link']})")
            st.caption(f"Source: {item.get('source', 'arxiv').upper()}")

            # Approve button
            st.markdown("---")
            if st.button(
                "✅ Approve" if not approved else "↩️ Unapprove",
                key=f"approve_{idx}",
                type="primary" if not approved else "secondary",
                use_container_width=True
            ):
                digest["items"][idx]["approved"] = not approved
                digest["items"][idx]["title"]          = new_title
                digest["items"][idx]["summary_plain"]  = new_summary
                digest["items"][idx]["pm_takeaway"]    = new_takeaway
                digest["items"][idx]["relevance"]      = new_relevance
                digest["items"][idx]["relevance_reason"] = new_rel_reason
                digest["items"][idx]["edited"]         = True
                with open(DRAFT_FILE, "w") as f:
                    json.dump(digest, f, indent=2)
                st.rerun()

st.divider()

# ── Publish button ────────────────────────────────────────────────────────────
all_approved = all(i.get("approved") for i in digest["items"])

col_pub, col_preview = st.columns([1, 1])

with col_pub:
    if st.button(
        "🚀 Publish digest",
        type="primary",
        disabled=not all_approved,
        use_container_width=True
    ):
        digest["status"]       = "approved"
        digest["approved_at"]  = datetime.now().isoformat()
        with open(APPROVED_FILE, "w") as f:
            json.dump(digest, f, indent=2)
        # Log published items to prevent repeats in future issues
        PUBLISHED_LOG = "published_items.json"
        existing = set()
        if os.path.exists(PUBLISHED_LOG):
            with open(PUBLISHED_LOG) as f:
                existing = set(json.load(f).get("fingerprints", []))
        import hashlib
        for item in digest["items"]:
            raw = (item.get("title", "") + item.get("link", "")).lower().strip()
            existing.add(hashlib.md5(raw.encode()).hexdigest())
        with open(PUBLISHED_LOG, "w") as f:
            json.dump({"fingerprints": list(existing)}, f, indent=2)
        st.success(f"✓ Digest approved and saved to `{APPROVED_FILE}`")
        st.info("Next step: run the web app with `streamlit run app.py`")

    if not all_approved:
        remaining = sum(1 for i in digest["items"] if not i.get("approved"))
        st.caption(f"Approve all {remaining} remaining item(s) to publish.")

with col_preview:
    if st.button("👁️ Preview digest", use_container_width=True):
        st.markdown("---")
        st.markdown(f"### Preview: Week of {digest['week_of']}")
        for i, item in enumerate(digest["items"]):
            rel_emoji = {"Act now": "🔴", "Watch": "🟡", "Skip": "⚪"}.get(item.get("relevance"), "🟡")
            st.markdown(f"**{i+1}. {rel_emoji} {item['title']}**")
            st.markdown(f"*{item.get('summary_plain', '')}*")
            st.markdown(f"**PM takeaway →** {item.get('pm_takeaway', '')}")
            st.markdown(f"[Read source →]({item['link']})")
            st.markdown("---")

# ── Save edits without approving ──────────────────────────────────────────────
with st.sidebar:
    st.header("Actions")
    if st.button("💾 Save all edits", use_container_width=True):
        for idx, item in enumerate(digest["items"]):
            digest["items"][idx]["title"]          = st.session_state.get(f"title_{idx}", item["title"])
            digest["items"][idx]["summary_plain"]  = st.session_state.get(f"summary_{idx}", item["summary_plain"])
            digest["items"][idx]["pm_takeaway"]    = st.session_state.get(f"takeaway_{idx}", item["pm_takeaway"])
            digest["items"][idx]["relevance"]      = st.session_state.get(f"rel_{idx}", item["relevance"])
            digest["items"][idx]["relevance_reason"] = st.session_state.get(f"rel_reason_{idx}", item.get("relevance_reason", ""))
        with open(DRAFT_FILE, "w") as f:
            json.dump(digest, f, indent=2)
        st.success("Saved!")

    st.divider()
    st.markdown("**Workflow**")
    st.markdown("1. `python3 engine.py` — generate draft")
    st.markdown("2. `streamlit run review.py` — review & approve")
    st.markdown("3. `streamlit run app.py` — publish to web")