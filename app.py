"""Event-related Trade Explorer: the daily event-study page (Alex 2026-11-05). The front page is today's top 5 news
stories as short exhibit cards (Alex 2026-11-06: the stock-led MU exhibit's format), the rest under "Load more";
each card opens its full exhibit (?story=<id>, a link people can share). Also: search over the event-study archive,
and a box to commission a new study by email. Reads only this folder's data/ (export.py writes it each morning).

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
from pathlib import Path
from urllib.parse import quote

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
TOP = 5
NOT_ADVICE = ""  # Alex 2026-11-06: dropped
GOLD, BLUE, DIM = "#d9a441", "#5b8def", "#9aa3b2"
PICKED = ["#e5534b", "#3fb27f", "#c678dd", "#56b6c2", "#f0f0f0", "#e5a0d6", "#98c379", "#ff9e64"]  # ticked cases

st.set_page_config(page_title="Event-related Trade Explorer", layout="wide")
st.markdown("""<style>
.stApp { background:#0e1117; color:#e6e9ef; } .block-container { padding-top:3.6rem; max-width:1100px; }
.chiron { overflow:hidden; white-space:nowrap; border-top:1px solid #2a3140; border-bottom:1px solid #2a3140;
          background:#11161f; padding:.45rem 0; margin:.3rem 0 1.2rem 0; }
.chiron span.run { display:inline-block; padding-left:100%; animation:roll 90s linear infinite; }
.chiron:hover span.run { animation-play-state:paused; }
.chiron b { color:#d9a441; font-weight:600; margin-right:.4rem; } .chiron i { color:#9aa3b2; font-style:normal; margin:0 2.2rem 0 .3rem; }
@keyframes roll { from { transform:translateX(0); } to { transform:translateX(-100%); } }
.mast { font-family:Georgia, serif; font-size:2.1rem; letter-spacing:.02em; margin:0; }
.tk { font-family:Georgia, serif; font-size:3rem; line-height:1.05; margin:0; }
.tk.small { font-size:2.2rem; }
.why { font-size:1.2rem; margin:.3rem 0 .8rem 0; } .meta { color:#9aa3b2; font-size:.85rem; }
.big { font-size:2rem; font-weight:600; } .up { color:#3fb27f; } .down { color:#e5534b; }
.box { background:#161b24; border:1px solid #2a3140; border-radius:8px; padding:.9rem 1.1rem; height:100%; }
.news { color:#9aa3b2; font-size:.95rem; margin:.6rem 0 .2rem 0; }
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
def load(stamp: tuple):  # stamp = the data files' change times, so a new edition shows at once
    t = json.loads((DATA / "today.json").read_text(encoding="utf-8")) if (DATA / "today.json").exists() else None
    a = []
    if (DATA / "archive.json.gz").exists():
        with gzip.open(DATA / "archive.json.gz", "rt", encoding="utf-8") as fh:
            a = json.load(fh)
    return t, a


def pct(x):
    return "–" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x * 100:+.0f}%"


def cls(x):
    return "" if x is None else ("up" if x > 0 else "down")


def tally(vals):
    v = [float(x) for x in vals if x is not None and np.isfinite(x)]
    return len(v), sum(x > 0 for x in v), (float(np.mean(v)) if v else None), (float(np.median(v)) if v else None)


def headline(X: dict, small: bool = False):
    when = (f"today's move is not in our prices yet (through {X['data_through']})" if X.get("pending")
            else X["event_date"])
    yb = (f"; {pct(X['year_before'])} against {X['against']} in the year before" if X["kind"] == "stock"
          else f"; the US stock average {pct(X['year_before'])} in the year before")
    st.markdown(f"<div class='tk{' small' if small else ''}'>{html.escape(X['subject'])}</div>"
                f"<div class='why'>{html.escape(X['plain'] or X['event'])} <span class='meta'>({when}{yb})</span></div>",
                unsafe_allow_html=True)


def boxes(X: dict):
    cs = X["cases"]
    n1, w1, a1, m1 = tally([c["after_21"] for c in cs])
    n2, w2, a2, m2 = tally([c["after_252"] for c in cs])
    did = "beat the market" if X["kind"] == "stock" else "the market was up"
    since = f"since {min(c['date'] for c in cs)[:4]}" if cs else "no past cases yet"
    first = "Stocks that did this before" if X["kind"] == "stock" else "Times this happened before"
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"<div class='box'><span class='meta'>{first}</span><br><span class='big'>{len(cs)}</span><br>"
                f"<span class='meta'>{since}</span></div>", unsafe_allow_html=True)
    for col, name, n, w, a, m in ((c2, "1 month", n1, w1, a1, m1), (c3, "1 year", n2, w2, a2, m2)):
        col.markdown(f"<div class='box'><span class='meta'>{name} later, {did}</span><br><span class='big'>"
                     f"{f'{w} of {n}' if n else '–'}</span><br><span class='meta'>middle case <span class='{cls(m)}'>"
                     f"{pct(m)}</span> (average {pct(a)})</span></div>", unsafe_allow_html=True)


def overlay(X: dict, sel: set | None = None):
    """sel: case numbers ticked in the table; when some are ticked only those past cases are drawn."""
    step, B = X["step"], X["before"]
    x = np.arange(-B, X["after"] + 1, step)
    p0 = X.get("paths_from", 0)
    P = np.array([[np.nan if v is None else v for v in p] for p in X["paths"]], float).reshape(-1, len(x))
    fig = go.Figure()
    for i, p in enumerate(P):
        c = X["cases"][p0 + i]
        lab = f"{c['who']} {c['date']}".strip()
        if sel and p0 + i not in sel:
            continue
        fig.add_scatter(x=x, y=p, mode="lines", hoverinfo="text", text=lab, name=lab, showlegend=bool(sel),
                        line=dict(color=PICKED[len(fig.data) % len(PICKED)] if sel else "rgba(154,163,178,.18)", width=2 if sel else 1))
    if len(P):
        ok = np.isfinite(P).sum(0) >= 5
        with np.errstate(all="ignore"):
            med = np.where(ok, np.nanmedian(P, axis=0), np.nan)
        fig.add_scatter(x=x, y=med, mode="lines", line=dict(color=BLUE, width=3), name="the middle past case")
    s = np.array([np.nan if v is None else v for v in X["path"]], float)
    fig.add_scatter(x=x, y=s, mode="lines", line=dict(color=GOLD, width=4),
                    name=f"{X['subject'] if X['kind'] == 'stock' else 'now'} (to {X['data_through']})")
    fig.add_vline(x=0, line_color=DIM, line_dash="dot")
    ylab = f"against {X['against']}, from the event day" if X["kind"] == "stock" else "the US stock average, from the event day"
    fig.update_layout(height=440, margin=dict(l=0, r=10, t=30, b=10), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font_color="#e6e9ef", legend=dict(orientation="h", y=1.08, x=0),
                      xaxis=dict(title="trading days from the event (0 = the day it happened)", gridcolor="#2a3140"),
                      yaxis=dict(title=ylab, tickformat="+.0%", gridcolor="#2a3140", zerolinecolor=DIM))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    more = f" Only the {len(P)} newest past cases have a line." if X.get("paths_from") else ""
    st.caption(("Showing the past cases ticked in the table below. " if sel else
                "Each grey line is one past case; tick cases in the table below to show only those. ")
               + "The blue line is the middle past case on each day. Left of 0 is the lead-up; right of 0 is "
               "what came after." + more)


def full(s: dict, X: dict, also: list | None = None):
    if st.button("← Back to today"):
        st.query_params.clear()
        st.rerun()
    headline(X)
    boxes(X)
    who = X["subject"] if X["kind"] == "stock" else "Now"
    st.markdown(f"**{who} against the {len(X['cases'])} past cases**")
    chart = st.container()   # drawn after the table, so the ticks in the table choose its lines
    cases = pd.DataFrame(X["cases"])
    sel: set = set()
    if X.get("rankings"):
        st.markdown(f"**Past cases that were also {', '.join(k.split(' (')[0] for k in X['rankings'])}, like {X['subject']}**")
        rows = []
        for k, idx in X["rankings"].items():
            sub = cases.iloc[idx] if idx else cases.iloc[0:0]
            a, b = tally(sub.after_21.tolist()), tally(sub.after_252.tolist())
            rows.append({"ranking": k, "past cases": len(sub),
                         "1 month later: beat the market": f"{a[1]} of {a[0]}" if a[0] else "–", "1 month, middle case": pct(a[3]),
                         "1 year later: beat the market": f"{b[1]} of {b[0]}" if b[0] else "–", "1 year, middle case": pct(b[3])})
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    elif X["kind"] != "stock" and (X.get("lead") or {}).get("picks_21"):
        st.markdown("**Which kind of stock did best after it, against the market** (top fifth of the S&P 500 on each ranking)")
        L = X["lead"]
        by = {r["pick"]: r for r in L.get("picks_252") or []}
        st.dataframe(pd.DataFrame([{"ranking": r["pick"], "1 month later": pct(r.get("avg")),
                                    "ahead after 1 month": f"{r.get('won')} of {r.get('n')}",
                                    "1 year later": pct((by.get(r["pick"]) or {}).get("avg")),
                                    "ahead after 1 year": (f"{by[r['pick']].get('won')} of {by[r['pick']].get('n')}"
                                                           if r["pick"] in by else "–")} for r in L["picks_21"]]),
                     hide_index=True, use_container_width=True)
    if also:
        st.markdown(f"### Similar cases to {html.escape(X['subject'])}")
        rows = []
        for (s2, j2, X2) in also:
            a, b = tally([c["after_21"] for c in X2["cases"]]), tally([c["after_252"] for c in X2["cases"]])
            did = "beat the market" if X2["kind"] == "stock" else "market up"
            rows.append({"version": f"{X2['subject']}: {X2['plain'] or X2['event']}", "past cases": len(X2["cases"]),
                         f"1 month later": f"{a[1]} of {a[0]} {did}, middle case {pct(a[3])}" if a[0] else "–",
                         f"1 year later": f"{b[1]} of {b[0]} {did}, middle case {pct(b[3])}" if b[0] else "–"})
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        pick = st.selectbox("Open a framing", ["–"] + [r["version"] for r in rows], key=f"ver_{s['id']}")
        if pick != "–":
            s2, j2, _ = also[[r["version"] for r in rows].index(pick)]
            st.query_params.update({"story": s2["id"], "v": str(j2)})
            st.rerun()
    if len(cases):
        st.markdown("**Every past case** (tick any to show only those in the chart)")
        cols = (["who"] if X["kind"] == "stock" else []) + ["date", "year_before", "after_21", "after_252"]
        t = cases[cols].sort_values("date", ascending=False)
        for c in ("year_before", "after_21", "after_252"):
            t[c] = t[c].map(pct)
        t = t.rename(columns={"who": "ticker", "year_before": "year before", "after_21": "1 month later",
                              "after_252": "1 year later"})
        ev = st.dataframe(t, hide_index=True, use_container_width=True, key=f"pick_{s['id']}",
                          on_select="rerun", selection_mode="multi-row")
        rows = ev.selection.rows if ev and ev.selection else []
        sel = set(int(t.index[r]) for r in rows)
    with chart:
        overlay(X, sel)
    st.markdown(f"<p class='news'><b>The news:</b> {html.escape(s['headline'])}. {html.escape(s.get('summary', ''))}</p>",
                unsafe_allow_html=True)
    src = " · ".join(f"<a href='{html.escape(x.get('url', ''))}' target='_blank'>{html.escape(x.get('title') or 'source')}</a>"
                     for x in s.get("sources", [])[:3])
    st.markdown(f"<span class='meta'>{src}<br>The rule: <code>{html.escape(X['event'])}</code>. Returns are against "
                f"{X['against']} (each S&amp;P 500 stock counted the same, financials out), bought at the next close. "
                f"Prices through {X['data_through']}. {NOT_ADVICE}</span>", unsafe_allow_html=True)


def card(s: dict, X: dict, i: int, j: int = 0, n_also: int = 0):
    with st.container(border=True):
        headline(X, small=True)
        boxes(X)
        extra = ""
        st.markdown(f"<p class='news'>{html.escape(s['headline'])}<span class='meta'>{extra}</span></p>", unsafe_allow_html=True)
        b1, b2, _ = st.columns([1, 1.3, 5])
        if b1.button("More info →", key=f"open{i}"):
            st.query_params.clear()
            st.query_params.update({"story": s["id"], "v": str(j)})
            st.rerun()
        if n_also and b2.button(f"Similar cases ({n_also})", key=f"sim{i}"):
            st.query_params.update({"story": s["id"], "v": str(j), "view": "similar"})
            st.rerun()


today, archive = load(tuple(f.stat().st_mtime for f in sorted(DATA.glob("*")) if f.is_file()))

st.markdown("<p class='mast'>Event-related Trade Explorer</p>", unsafe_allow_html=True)
if not today:
    st.info("The first daily edition is not out yet.")
    st.stop()
st.markdown(f"<span class='meta'>{today['date']} · prices through {today.get('data_through')}</span>",
            unsafe_allow_html=True)
stories = today["stories"]
groups = [{"lead": (stories[g["lead"][0]], g["lead"][1]), "also": [(stories[i], j) for i, j in g["also"]]}
          for g in today.get("front") or []]


def ex(s, j):
    return (s.get("exhibits") or [None])[j] if j < len(s.get("exhibits") or []) else None


open_id, open_v = st.query_params.get("story"), int(st.query_params.get("v", 0) or 0)
s_open = next((s for s in stories if s["id"] == open_id), None)
if s_open and ex(s_open, open_v):
    g = next((g for g in groups if (g["lead"][0]["id"], g["lead"][1]) == (open_id, open_v)
              or any((s2["id"], j2) == (open_id, open_v) for s2, j2 in g["also"])), None)
    others = [] if g is None else [(s2, j2, ex(s2, j2)) for s2, j2 in [g["lead"]] + g["also"]
                                   if (s2["id"], j2) != (open_id, open_v) and ex(s2, j2)]
    if st.query_params.get("view") == "similar":
        if st.button("← Back to today"):
            st.query_params.clear()
            st.rerun()
        X0 = ex(s_open, open_v)
        st.markdown(f"## Similar cases to {html.escape(X0['subject'])}")
        for k, (s2, j2, X2) in enumerate([(s_open, open_v, ex(s_open, open_v))] + others):
            card(s2, X2, 100 + k, j2, 0)
    else:
        full(s_open, ex(s_open, open_v), others)
    st.stop()

items = []
for g in groups[:TOP]:
    s, j = g["lead"]
    X = ex(s, j)
    n, w, _, _ = tally([c["after_21"] for c in X["cases"]])
    tail = (f"{X['subject']}: {w} of {n} past cases {'beat the market' if X['kind'] == 'stock' else 'saw the market up'}"
            f" a month later") if n else ""
    items.append(f"<b>{html.escape(s['headline'])}</b><i>{html.escape(tail)}</i>")
st.markdown(f"<div class='chiron'><span class='run'>{''.join(items)}</span></div>", unsafe_allow_html=True)

tab_today, tab_search, tab_ask = st.tabs(["Today", "Search the archive", "Commission a study"])

with tab_today:
    for i, g in enumerate(groups[:TOP]):
        card(g["lead"][0], ex(*g["lead"]), i, g["lead"][1], len(g["also"]))
    rest = groups[TOP:]
    if rest:
        if st.session_state.get("more"):
            for i, g in enumerate(rest, start=TOP):
                card(g["lead"][0], ex(*g["lead"]), i, g["lead"][1], len(g["also"]))
        elif st.button(f"Load more ({len(rest)})"):
            st.session_state.more = True
            st.rerun()

with tab_search:
    q = st.text_input("Search past event studies", placeholder="oil crash, chip sell-off, stock up 10x then drops ...")
    if archive:
        df = pd.DataFrame(archive)
        df["text"] = (df.headline.fillna("") + " " + df.summary.fillna("") + " " + df.plain.fillna("") + " "
                      + df.event.fillna("") + " " + df.tickers.apply(lambda t: " ".join(t or [])))
        if q.strip():
            from sklearn.feature_extraction.text import TfidfVectorizer
            vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
            M = vec.fit_transform(df.text)
            df = df.assign(score=(M @ vec.transform([q]).T).toarray().ravel())
            df = df[df.score > 0].sort_values("score", ascending=False)
        st.caption(f"{len(df)} studies" + (" match" if q.strip() else " so far, newest first"))
        for r in df.head(30).itertuples():
            lead = r.lead or {}
            parts = []
            for h, name in (("21", "1 month"), ("252", "1 year")):
                a = lead.get(f"after_{h}") or {}
                if a.get("n"):
                    parts.append(f"{name} later: {'ahead' if r.kind == 'stock' else 'up'} in {a.get('won')} of {a['n']} "
                                 f"(average {pct(a.get('avg'))})")
            with st.expander(f"{r.date} · {r.headline} — {r.plain}"):
                st.markdown(f"<code>{html.escape(r.event)}</code> · {r.past_cases} past cases<br>"
                            f"{'; '.join(parts) or 'too few past cases'}", unsafe_allow_html=True)
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
