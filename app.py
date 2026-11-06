"""Event-related Trade Explorer: the daily event-study page (Alex 2026-11-05): today's news-based event studies in a scrolling ticker and cards,
search over the event-study archive, and a box to commission a new study by email. Hosted like Blackbird
(sharadar/search_site): reads only this folder's data/ (export.py writes it locally each morning).

Run: C:\\Python310\\python.exe -m streamlit run sharadar\\event_site\\app.py
Secrets (.streamlit/secrets.toml on the host; all optional locally): password, request_email.
History only, not investment advice.
"""
from __future__ import annotations

import gzip
import hmac
import html
import json
import os
import re
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
HOLDS = {"21": "1 month", "252": "1 year"}
NOT_ADVICE = "History, not investment advice. Past results do not tell you what happens next."

st.set_page_config(page_title="Event-related Trade Explorer", layout="wide")
st.markdown("""<style>
:root { --bg:#0e1117; --panel:#161b24; --line:#2a3140; --ink:#e6e9ef; --dim:#9aa3b2; --up:#3fb27f; --down:#e5534b;
        --accent:#d9a441; }
.stApp { background: var(--bg); color: var(--ink); }
.block-container { padding-top: 1.2rem; max-width: 1100px; }
.chiron { overflow: hidden; white-space: nowrap; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line);
          background: #11161f; padding: .45rem 0; margin: .3rem 0 1.2rem 0; }
.chiron span.run { display: inline-block; padding-left: 100%; animation: roll 90s linear infinite; }
.chiron:hover span.run { animation-play-state: paused; }
.chiron b { color: var(--accent); font-weight: 600; margin-right: .4rem; }
.chiron i { color: var(--dim); font-style: normal; margin: 0 2.2rem 0 .3rem; }
@keyframes roll { from { transform: translateX(0); } to { transform: translateX(-100%); } }
.card { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 1rem 1.2rem; margin-bottom: 1rem; }
.card h3 { margin: 0 0 .3rem 0; font-size: 1.25rem; }
.meta { color: var(--dim); font-size: .85rem; }
.ev { border-left: 3px solid var(--accent); padding-left: .8rem; margin-top: .9rem; }
.num { font-size: 1.5rem; font-weight: 600; }
.up { color: var(--up); } .down { color: var(--down); }
.mast { font-family: Georgia, serif; font-size: 2.1rem; letter-spacing: .02em; margin: 0; }
</style>""", unsafe_allow_html=True)


def secret(k: str):
    try:
        return st.secrets.get(k) or os.environ.get(k.upper())
    except Exception:  # noqa: BLE001  (no secrets file locally)
        return os.environ.get(k.upper())


pw = secret("password")
if pw and not st.session_state.get("ok"):
    x = st.text_input("Password", type="password")
    if x and hmac.compare_digest(x, pw):
        st.session_state.ok = True
        st.rerun()
    elif x:
        st.error("Wrong password")
    st.stop()


@st.cache_data(ttl=600)
def load():
    t = json.loads((DATA / "today.json").read_text(encoding="utf-8")) if (DATA / "today.json").exists() else None
    a = []
    if (DATA / "archive.json.gz").exists():
        with gzip.open(DATA / "archive.json.gz", "rt", encoding="utf-8") as fh:
            a = json.load(fh)
    return t, a


def pct(x, sign=True) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "–"
    return f"{x * 100:+.1f}%" if sign else f"{x * 100:.1f}%"


def cls(x) -> str:
    return "" if x is None else ("up" if x > 0 else "down" if x < 0 else "")


def after_line(lead: dict, kind: str) -> str:
    """'1 month later: +2.1% on average, higher in 9 of 14' for the market (or the stocks, for a stock event)."""
    who = "the stocks beat the market by" if kind == "stock" else "the market moved"
    parts = []
    for h, name in HOLDS.items():
        a = lead.get(f"after_{h}") or {}
        if a.get("n"):
            parts.append(f"{name} later {who} <span class='{cls(a.get('avg'))}'>{pct(a.get('avg'))}</span> on "
                         f"average ({'ahead' if kind == 'stock' else 'up'} in {a.get('won')} of {a['n']})")
    return "; ".join(parts) or "too few past cases to show"


def picks_chart(lead: dict, key: str):
    fig = go.Figure()
    colors = {"21": "#d9a441", "252": "#5b8def"}
    names = None
    for h, name in HOLDS.items():
        rows = lead.get(f"picks_{h}") or []
        if not rows:
            continue
        if names is None:
            names = [r["pick"] for r in sorted(rows, key=lambda r: r.get("avg") or 0)]
        by = {r["pick"]: r for r in rows}
        fig.add_bar(y=names, x=[(by.get(n) or {}).get("avg") for n in names], orientation="h", name=name,
                    marker_color=colors[h],
                    customdata=[[(by.get(n) or {}).get("won"), (by.get(n) or {}).get("n")] for n in names],
                    hovertemplate="%{y}: %{x:+.1%} vs the market, ahead in %{customdata[0]} of %{customdata[1]}<extra>"
                                  + name + "</extra>")
    if names is None:
        st.caption("No pick comparison yet: too few past cases.")
        return
    fig.update_layout(barmode="group", height=40 + 34 * len(names), margin=dict(l=0, r=10, t=10, b=10),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#e6e9ef",
                      xaxis=dict(tickformat="+.0%", gridcolor="#2a3140", zerolinecolor="#9aa3b2"),
                      legend=dict(orientation="h", y=1.08, x=0))
    st.plotly_chart(fig, use_container_width=True, key=key, config={"displayModeBar": False})


def study_block(stu: dict, key: str):
    st.markdown(f"<div class='ev'><b>{html.escape(stu.get('plain') or stu['event'])}</b><br>"
                f"<span class='meta'><code>{html.escape(stu['event'])}</code> · {stu.get('past_cases', 0)} past cases"
                + (" · fired this week" if stu.get("fired_recently") else "") + "</span><br>"
                f"{after_line(stu.get('lead') or {}, stu['kind'])}</div>", unsafe_allow_html=True)
    if stu.get("error"):
        st.caption(f"Could not study this event: {stu['error']}")
        return
    st.markdown("<span class='meta'>Which kind of stock did best after it, against the market (top fifth of the "
                "S&amp;P 500 on each ranking)</span>", unsafe_allow_html=True)
    picks_chart(stu.get("lead") or {}, key)
    h = stu.get("history") or {}
    with st.expander("Past cases"):
        if stu["kind"] == "stock":
            st.write("Firings by year: " + ", ".join(f"{y}: {n}" for y, n in (h.get("by_year") or {}).items()))
        else:
            cs = [c for c in h.get("cases", []) if not c.get("pending")]
            if cs:
                df = pd.DataFrame([{"date": c["date"], "market 1 month later": c.get("mkt_21"),
                                    "market 1 year later": c.get("mkt_252")} for c in cs][::-1])
                st.dataframe(df.style.format({c: "{:+.1%}" for c in df.columns if c != "date"}, na_rep="pending"),
                             hide_index=True, use_container_width=True)
    if stu.get("today"):
        with st.expander(f"Stocks that did this in the last week ({len(stu['today'])})"):
            st.dataframe(pd.DataFrame([{"ticker": t["ticker"], "date": t["date"], "rankings it sits in":
                                        ", ".join(p.split(" (")[0] for p in t["picks"])} for t in stu["today"]]),
                         hide_index=True, use_container_width=True)


today, archive = load()

st.markdown("<p class='mast'>Event-related Trade Explorer</p>", unsafe_allow_html=True)
if not today:
    st.info("The first daily edition is not out yet.")
    st.stop()
st.markdown(f"<span class='meta'>{today['date']} · prices through {today.get('data_through')} · "
            f"{NOT_ADVICE}</span>", unsafe_allow_html=True)

items = []
for s in today["stories"]:
    stu = next((x for x in s.get("studies", []) if not x.get("error")), None)
    tail = ""
    if stu:
        a = (stu.get("lead") or {}).get("after_21") or {}
        if a.get("n"):
            tail = (f"after {a['n']} similar cases, {'those stocks' if stu['kind'] == 'stock' else 'the market'} "
                    f"averaged {pct(a.get('avg'))} a month later")
    items.append(f"<b>{html.escape(s['headline'])}</b><i>{html.escape(tail)}</i>")
st.markdown(f"<div class='chiron'><span class='run'>{''.join(items)}</span></div>", unsafe_allow_html=True)

tab_today, tab_search, tab_ask = st.tabs(["Today", "Search the archive", "Commission a study"])

with tab_today:
    for i, s in enumerate(today["stories"]):
        src = " · ".join(f"<a href='{html.escape(x.get('url', ''))}' target='_blank'>{html.escape(x.get('title') or 'source')}</a>"
                         for x in s.get("sources", [])[:3])
        st.markdown(f"<div class='card'><h3>{html.escape(s['headline'])}</h3>"
                    f"<span class='meta'>{s.get('date', '')}"
                    + (f" · {', '.join(map(html.escape, s.get('tickers', [])))}" if s.get("tickers") else "")
                    + (f" · {src}" if src else "") + f"</span><p>{html.escape(s.get('summary', ''))}</p></div>",
                    unsafe_allow_html=True)
        for j, stu in enumerate(s.get("studies", [])):
            study_block(stu, key=f"t{i}_{j}")
        st.divider()

with tab_search:
    q = st.text_input("Search past event studies", placeholder="oil crash, chip sell-off, stock up 10x then drops ...")
    if archive:
        df = pd.DataFrame(archive)
        df["text"] = (df.headline.fillna("") + " " + df.summary.fillna("") + " " + df.plain.fillna("") + " "
                      + df.event.fillna("") + " " + df.tickers.apply(lambda t: " ".join(t or [])))
        if q.strip():
            from sklearn.feature_extraction.text import TfidfVectorizer
            vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
            X = vec.fit_transform(df.text)
            s_ = (X @ vec.transform([q]).T).toarray().ravel()
            df = df.assign(score=s_)
            df = df[df.score > 0].sort_values("score", ascending=False)
        st.caption(f"{len(df)} studies" + (" match" if q.strip() else " so far, newest first"))
        for k, r in enumerate(df.head(30).itertuples()):
            with st.expander(f"{r.date} · {r.headline} — {r.plain}"):
                st.markdown(f"<code>{html.escape(r.event)}</code> · {r.past_cases} past cases<br>"
                            f"{after_line(r.lead or {}, r.kind)}", unsafe_allow_html=True)
                picks_chart(r.lead or {}, key=f"s{k}")
    else:
        st.caption("The archive fills up as daily editions come out.")

with tab_ask:
    st.markdown("Describe a move or a story you want studied: what happened, and to what (the market, a sector, one "
                "kind of stock). We test it on the history and send you the result.")
    ask = st.text_area("Your study", placeholder="What happens to small caps after the 10-year yield jumps half a point in a month?")
    to = secret("request_email")
    if to:
        st.link_button("Send the request by email", f"mailto:{to}?subject={quote('Event study request')}&body={quote(ask)}",
                       disabled=not ask.strip())
    else:
        st.button("Requests are coming soon", disabled=True)
    st.caption(NOT_ADVICE)
