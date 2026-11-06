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
.mast { font-family:"Helvetica Neue", Helvetica, Arial, sans-serif; font-weight:700; font-size:2.8rem; letter-spacing:-.01em; line-height:1.1; margin:0 0 .2rem 0; }
.tk { font-family:"Helvetica Neue", Helvetica, Arial, sans-serif; font-weight:700; font-size:2.8rem; letter-spacing:-.01em; line-height:1.05; margin:0; }
.tk.small { font-size:2.1rem; }
.why { font-size:1.2rem; margin:.3rem 0 .8rem 0; } .meta { color:#9aa3b2; font-size:.85rem; }
.big { font-size:2rem; font-weight:600; } .up { color:#3fb27f; } .down { color:#e5534b; }
.box { background:#161b24; border:1px solid #2a3140; border-radius:8px; padding:.9rem 1.1rem; height:100%; }
.take { font-size:1.05rem; margin:.9rem 0 .6rem 0; padding:.6rem .9rem; border-left:3px solid #d9a441; background:#161b24; border-radius:0 6px 6px 0; }
.take b { color:#d9a441; font-size:.8rem; letter-spacing:.06em; text-transform:uppercase; display:block; margin-bottom:.15rem; }
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


def measure(X: dict) -> str:
    """What a market exhibit's results are measured on, lower-cased for a sentence ("chip stocks", "the US stock average")."""
    m_ = X.get("measure") or "The US stock average"
    return "the" + m_[3:] if m_.startswith("The ") else m_ if m_.split(" ", 1)[0] in ("Brent", "Bitcoin", "Gold") else m_[:1].lower() + m_[1:]


def trig(X: dict) -> str:
    """The event trigger in words, lower-cased to follow a colon ("a stock that tripled ...")."""
    t = (X.get("plain") or X["event"]).strip().rstrip(".")
    w = t.split(" ", 1)[0]
    return t if len(w) > 1 and w.isupper() else t[:1].lower() + t[1:]   # keep tickers and acronyms (VIX, S&P)


def day(d: str) -> str:
    t = pd.Timestamp(d)
    return f"{t:%b} {t.day}, {t.year}"


def headline(X: dict, small: bool = False):
    when = (f"Today's move is not in our prices yet (they run through {day(X['data_through'])})" if X.get("pending")
            else f"Happened {day(X['event_date'])}")
    y = X.get("year_before")
    if y is None:
        yb = ""
    elif X["kind"] == "stock":
        yb = (f" · in the 12 months before, {X['subject']} {'beat' if y >= 0 else 'trailed'} the average S&amp;P 500 "
              f"stock by {abs(y) * 100:.0f}%")
    else:
        m_ = measure(X)
        yb = f" · in the 12 months before, {m_} {'rose' if y >= 0 else 'fell'} {abs(y) * 100:.0f}%"
    st.markdown(f"<div class='tk{' small' if small else ''}'>{html.escape(X['subject'])}</div>"
                f"<div class='why'>{html.escape(X['plain'] or X['event'])}</div>"
                f"<div class='meta' style='margin:-.5rem 0 .8rem 0'>{when}{yb}</div>", unsafe_allow_html=True)


def takeaway(X: dict) -> str:
    """One plain sentence from the counts (Alex 2026-11-06: readers asked for a takeaway). Rules, no model:
    a hold "leans" one way when 60%+ of cases went that way and the median agrees; the stronger lean (share further
    from half, then the bigger median) is the one called out."""
    cs = X["cases"]
    stock = X["kind"] == "stock"
    up_word, down_word = (("beat the market", "lagged the market") if stock else (f"rose", f"fell"))
    who = "Past cases like this" if stock else f"After past cases like this, {measure(X)}"
    leans = []
    for h, name in ((21, "a month"), (252, "a year")):
        n, w, _, m = tally([c[f"after_{h}"] for c in cs])
        if n < 5 or m is None:
            continue
        share = w / n
        lean = "up" if share >= 0.6 and m > 0 else "down" if share <= 0.4 and m < 0 else None
        leans.append((h, name, n, w, m, share, lean))
    if not leans:
        return "Too few past cases to say which way they went."
    called = [x for x in leans if x[5] is not None and x[6]]
    if not called:
        return f"{who} went both ways: no clear lean after a month or a year."
    best = max(called, key=lambda x: (abs(x[5] - 0.5), abs(x[4])))
    word = up_word if best[6] == "up" else down_word
    both = len(called) == 2 and called[0][6] == called[1][6]
    when = (f"over both a month and a year, most clearly over {best[1]}" if both else f"over {best[1]}")
    other = [x for x in leans if x is not best and not (both and x in called)]
    tail = f"; over {other[0][1]} it was mixed" if other else ""
    verb = word if stock else f"mostly {word}"
    lead_ = f"{who} {'have mostly ' + word if stock else verb} {when}"
    few = " Only a few past cases, so read it lightly." if min(x[2] for x in leans) < 10 else ""
    return (f"{lead_}: {best[3]} of {best[2]} {'beat the market' if stock else 'were up'}, median {pct(best[4])}"
            f"{tail}.{few}")


def take_box(X: dict):
    st.markdown(f"<div class='take'><b>Takeaway</b>{html.escape(takeaway(X))}</div>", unsafe_allow_html=True)


def boxes(X: dict):
    cs = X["cases"]
    n1, w1, a1, m1 = tally([c["after_21"] for c in cs])
    n2, w2, a2, m2 = tally([c["after_252"] for c in cs])
    did = "beat the market" if X["kind"] == "stock" else f"{measure(X)} {'were' if measure(X).endswith('s') else 'was'} up"
    since = f"since {min(c['date'] for c in cs)[:4]}" if cs else "no past cases yet"
    first = "Stocks that did this before" if X["kind"] == "stock" else "Times this happened before"
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"<div class='box'><span class='meta'>{first}</span><br><span class='big'>{len(cs)}</span><br>"
                f"<span class='meta'>{since}</span></div>", unsafe_allow_html=True)
    for col, name, n, w, a, m in ((c2, "1 month", n1, w1, a1, m1), (c3, "1 year", n2, w2, a2, m2)):
        col.markdown(f"<div class='box'><span class='meta'>{name} later, {did}</span><br><span class='big'>"
                     f"{f'{w} of {n}' if n else '–'}</span><br><span class='meta'>median <span class='{cls(m)}'>"
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
    band = st.toggle("Show the range of 80% of past cases", value=True, key=f"band_{X['event']}_{X['subject']}",
                     help="Shaded: on each day, the middle 80% of past cases (10th to 90th percentile).")
    if len(P):
        ok = np.isfinite(P).sum(0) >= 5
        with np.errstate(all="ignore"):
            med = np.where(ok, np.nanmedian(P, axis=0), np.nan)
            lo = np.where(ok, np.nanpercentile(P, 10, axis=0), np.nan)
            hi = np.where(ok, np.nanpercentile(P, 90, axis=0), np.nan)
        if band:
            fig.add_scatter(x=x, y=hi, mode="lines", line=dict(width=0), hoverinfo="skip", showlegend=False)
            fig.add_scatter(x=x, y=lo, mode="lines", line=dict(width=0), fill="tonexty",
                            fillcolor="rgba(91,141,239,.30)", name="80% of past cases", hoverinfo="skip")
        fig.add_scatter(x=x, y=med, mode="lines", line=dict(color=BLUE, width=3), name="median past case")
    s = np.array([np.nan if v is None else v for v in X["path"]], float)
    fig.add_scatter(x=x, y=s, mode="lines", line=dict(color=GOLD, width=4),
                    name=f"{X['subject'] if X['kind'] == 'stock' else 'now'} (to {X['data_through']})")
    fig.add_vline(x=0, line_color=DIM, line_dash="dot")
    ylab = f"against {X['against']}, from the event day" if X["kind"] == "stock" else f"{measure(X)}, from the event day"
    fig.update_layout(height=440, margin=dict(l=0, r=10, t=30, b=10), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font_color="#e6e9ef", legend=dict(orientation="h", y=1.08, x=0),
                      xaxis=dict(title="trading days from the event (0 = the day it happened)", gridcolor="#2a3140"),
                      yaxis=dict(title=ylab, tickformat="+.0%", gridcolor="#2a3140", zerolinecolor=DIM))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    more = f" Only the {len(P)} newest past cases have a line." if X.get("paths_from") else ""
    st.caption(("Showing the past cases ticked in the table below. " if sel else
                "Each grey line is one past case; tick cases in the table below to show only those. ")
               + "The blue line is the median past case on each day. Left of 0 is the lead-up; right of 0 is "
               "what came after." + more)


def bars(rows: list, did: str):
    """rows: (ranking, (value, won, n) at 1 month, (value, won, n) at 1 year); grouped horizontal bars."""
    rows = [r for r in rows if (r[1][2] or 0) or (r[2][2] or 0)]
    if not rows:
        st.caption("Too few past cases to compare.")
        return
    rows.sort(key=lambda r: r[1][0] if r[1][0] is not None else -9)
    names = [r[0] for r in rows]
    fig = go.Figure()
    for k, (name, col) in enumerate((("1 month", GOLD), ("1 year", BLUE)), start=1):
        fig.add_bar(y=names, x=[r[k][0] for r in rows], orientation="h", name=name, marker_color=col,
                    customdata=[[r[k][1], r[k][2]] for r in rows],
                    hovertemplate="%{y}: %{x:+.0%}, " + did + " in %{customdata[0]} of %{customdata[1]}<extra>" + name + "</extra>")
    fig.update_layout(barmode="group", height=60 + 38 * len(names), margin=dict(l=0, r=10, t=10, b=10),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#e6e9ef",
                      xaxis=dict(tickformat="+.0%", gridcolor="#2a3140", zerolinecolor=DIM),
                      legend=dict(orientation="h", y=1.12, x=0))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def full(s: dict, X: dict, also: list | None = None):
    if st.button("← Back to today"):
        st.query_params.clear()
        st.rerun()
    headline(X)
    boxes(X)
    take_box(X)
    who = X["subject"] if X["kind"] == "stock" else "Now"
    st.markdown(f"**{who} against the {len(X['cases'])} past cases**")
    chart = st.container()   # drawn after the table, so the ticks in the table choose its lines
    cases = pd.DataFrame(X["cases"])
    sel: set = set()
    if X.get("rankings"):
        st.markdown(f"**Past cases that were also {', '.join(k.split(' (')[0] for k in X['rankings'])}, like "
                    f"{html.escape(X['subject'])}** (median against the market)")
        rows = []
        for k, idx in X["rankings"].items():
            sub = cases.iloc[idx] if idx else cases.iloc[0:0]
            a, b = tally(sub.after_21.tolist()), tally(sub.after_252.tolist())
            rows.append((k, (a[3], a[1], a[0]), (b[3], b[1], b[0])))
        bars(rows, "beat the market")
    elif X["kind"] != "stock" and (X.get("lead") or {}).get("picks_21"):
        st.markdown("**Which kind of stock did best after it** (top fifth of the S&P 500 on each ranking, average "
                    "against the market)")
        Ld = X["lead"]
        by = {r["pick"]: r for r in Ld.get("picks_252") or []}
        bars([(r["pick"], (r.get("avg"), r.get("won"), r.get("n")),
               ((by.get(r["pick"]) or {}).get("avg"), (by.get(r["pick"]) or {}).get("won"), (by.get(r["pick"]) or {}).get("n")))
              for r in Ld["picks_21"]], "ahead of the market")
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
    if also and st.button(f"Similar cases ({len(also)}) →"):
        st.query_params.update({"view": "similar"})
        st.rerun()
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
        take_box(X)
        extra = ""
        st.markdown(f"<p class='news'>{html.escape(s['headline'])}<span class='meta'>{extra}</span></p>", unsafe_allow_html=True)
        b1, b2, _ = st.columns([1, 1.3, 5])
        if b1.button("More info →", key=f"open{i}"):
            st.query_params.clear()
            st.query_params.update({"story": s["id"], "v": str(j), **({"day": CUR_DAY} if CUR_DAY else {})})
            st.rerun()
        if n_also and b2.button(f"Similar cases ({n_also})", key=f"sim{i}"):
            st.query_params.update({"story": s["id"], "v": str(j), "view": "similar"})
            st.rerun()


MAX_SEARCHES = 40   # per visitor session, so one visitor cannot run up the bill


def word_search(q: str, texts: tuple, top: int | None = None) -> list:
    from sklearn.feature_extraction.text import TfidfVectorizer
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
    M = vec.fit_transform(texts)
    sc = (M @ vec.transform([q]).T).toarray().ravel()
    idx = [int(i) for i in np.argsort(-sc) if sc[i] > 0]
    return idx[:top] if top else idx


@st.cache_data(ttl=3600, show_spinner=False)
def haiku_search(q: str, texts: tuple, key: str) -> list:
    """Claude Haiku reads the query and the archive (one line per study) and returns the matching rows, best first.
    A large archive is cut to the 300 best word matches plus the 100 newest first. Cached for an hour per query."""
    import anthropic
    ids = list(range(len(texts)))
    if len(ids) > 400:
        ids = sorted(set(word_search(q, texts, 300)) | set(range(100)))
    lines = "\n".join(f"{i}: {texts[i][:300]}" for i in ids)
    r = anthropic.Anthropic(api_key=key).messages.create(
        model="claude-haiku-5-5", max_tokens=2000, output_config={"effort": "low", "format": {"type": "json_schema", "schema": {
            "type": "object", "properties": {"ids": {"type": "array", "items": {"type": "integer"}}},
            "required": ["ids"], "additionalProperties": False}}},
        messages=[{"role": "user", "content": (
            "You search an archive of market event studies. Each line is one study: its number, then the news "
            "headline, summary, the event in words, the event rule and tickers. Return the numbers of the studies "
            "that match what the user is looking for, best match first, at most 30. Match on meaning (a 'chip "
            "crash' matches semiconductor sell-offs), not just words. Return an empty list if nothing fits.\n\n"
            f"Search: {q}\n\nStudies:\n{lines}")}])
    out = json.loads(next(b.text for b in r.content if b.type == "text"))["ids"]
    ok = set(ids)
    return [i for i in dict.fromkeys(out) if i in ok]


today, archive = load(tuple(f.stat().st_mtime for f in sorted(DATA.glob("*")) if f.is_file()))

st.markdown("<div class='mast'>Event-related Trade Explorer</div>", unsafe_allow_html=True)
if not today:
    st.info("The first daily edition is not out yet.")
    st.stop()


@st.cache_data(ttl=3600, show_spinner=False)
def load_day(day_: str, stamp: float):
    with gzip.open(DATA / "days" / f"{day_}.json.gz", "rt", encoding="utf-8") as fh:
        return json.load(fh)


ed = today   # the edition on show: today's, or an older one opened from search (?day=)
_dq = st.query_params.get("day")
if _dq and _dq != today["date"] and (DATA / "days" / f"{_dq}.json.gz").exists():
    ed = load_day(_dq, (DATA / "days" / f"{_dq}.json.gz").stat().st_mtime)
CUR_DAY = None if ed is today else ed["date"]
st.markdown(f"<span class='meta'>{ed['date']} · prices through {ed.get('data_through')}"
            + (" · an earlier edition" if CUR_DAY else "") + "</span>", unsafe_allow_html=True)
stories = ed["stories"]
groups = [{"lead": (stories[g["lead"][0]], g["lead"][1]), "also": [(stories[i], j) for i, j in g["also"]]}
          for g in ed.get("front") or []]


RECENT = bool(st.session_state.get("recent", False))   # the switch itself sits at the bottom of the page


def recent_switch():
    st.toggle("Include cases from the last year", key="recent",
              help="Off: only past cases at least a year old, so their year after does not overlap today's.")


def trim(X: dict | None) -> dict | None:
    """Alex 2026-11-06: by default only past cases at least a year old (their 1-year result is in), so recent cases
    that overlap each other and today's move do not crowd the counts, the chart or the table."""
    if X is None or RECENT:
        return X
    keep = [i for i, c in enumerate(X["cases"]) if c.get("after_252") is not None]
    new = {old: k for k, old in enumerate(keep)}
    p0 = X.get("paths_from", 0)
    pk = [(new[p0 + i], p) for i, p in enumerate(X["paths"]) if p0 + i in new]
    return {**X, "cases": [X["cases"][i] for i in keep], "paths": [p for _, p in pk],
            "paths_from": pk[0][0] if pk else 0,
            "rankings": {k: [new[i] for i in v if i in new] for k, v in (X.get("rankings") or {}).items()}}


def ex(s, j):
    return trim((s.get("exhibits") or [None])[j]) if j < len(s.get("exhibits") or []) else None


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
        st.markdown(f"## Similar cases to {html.escape(X0['subject'])}: {html.escape(trig(X0))}")
        for k, (s2, j2, X2) in enumerate([(s_open, open_v, ex(s_open, open_v))] + others):
            card(s2, X2, 100 + k, j2, 0)
    else:
        full(s_open, ex(s_open, open_v), others)
    recent_switch()
    st.stop()

items = []
for g in groups[:TOP]:
    s, j = g["lead"]
    X = ex(s, j)
    n, w, _, _ = tally([c["after_21"] for c in X["cases"]])
    tail = (f"{X['subject']}: {w} of {n} past cases {'beat the market' if X['kind'] == 'stock' else 'saw the market up'}"
            f" a month later") if n else ""
    items.append(f"<b>{html.escape(s['headline'])}</b><i>{html.escape(tail)}</i>")
# Alex 2026-11-06: chiron off for now; uncomment to bring it back
# st.markdown(f"<div class='chiron'><span class='run'>{''.join(items)}</span></div>", unsafe_allow_html=True)

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
    recent_switch()

with tab_search:
    q = st.text_input("Search past event studies", placeholder="oil crash, chip sell-off, stock up 10x then drops ...")
    if archive:
        df = pd.DataFrame(archive)
        df = df.drop_duplicates(["story_id", "event"]).reset_index(drop=True)   # a story kept for days: newest copy
        df["text"] = (df.headline.fillna("") + " " + df.summary.fillna("") + " " + df.plain.fillna("") + " "
                      + df.event.fillna("") + " " + df.tickers.apply(lambda t: " ".join(t or [])))
        if q.strip():
            key = secret("anthropic_api_key")
            n_q = st.session_state.get("n_search", 0)
            order = None
            if key and n_q < MAX_SEARCHES:
                st.session_state.n_search = n_q + 1
                try:
                    with st.spinner("Searching ..."):
                        order = haiku_search(q.strip(), tuple(df.text), key)
                except Exception as exc:  # noqa: BLE001  (any API trouble: fall back to word matching)
                    st.caption(f"Smart search is down ({type(exc).__name__}); matching words instead.")
            if order is None:
                order = word_search(q, tuple(df.text))
            df = df.iloc[order]
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
                if st.button("Open →", key=f"srch{r.Index}"):
                    f_ = DATA / "days" / f"{r.date}.json.gz"
                    E_ = today if r.date == today["date"] else (load_day(r.date, f_.stat().st_mtime) if f_.exists() else None)
                    s_ = next((x for x in (E_ or {}).get("stories", []) if x["id"] == r.story_id), None)
                    j_ = next((k for k, x in enumerate((s_ or {}).get("studies", [])) if x.get("event") == r.event), None)
                    if s_ is None or j_ is None or not ((s_.get("exhibits") or [None] * (j_ + 1))[j_]):
                        st.caption("This study's full page is not available.")
                    else:
                        st.query_params.clear()
                        st.query_params.update({"story": r.story_id, "v": str(j_),
                                                **({"day": r.date} if r.date != today["date"] else {})})
                        st.rerun()
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
