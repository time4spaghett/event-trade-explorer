"""Polecat Event Trajectory Explorer (renamed 2026-11-09; was Event-related Trade Explorer): the daily event-study page (Alex 2026-11-05). The front page is today's top 5 news
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
import re
from pathlib import Path
from urllib.parse import quote

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
TOP = 5
THEMES = {   # Alex 2026-11-09: the easter egg (click the first story's status light); one is picked at random
    "vhs": """<style>
.stApp { background:#0e1117 url("data:image/svg+xml;base64,PHN2ZyBvcGFjaXR5PSIwLjAzNSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB2aWV3Qm94PSIwIDAgMTAwMCA2NDAiIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzllYzlmZiIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+CiAgPHBhdGggc3Ryb2tlLXdpZHRoPSIyLjQiIGQ9Ik01MDAgMTEwIEwgOTA1IDMzNSBMIDg5MCAzNjIgTCA3NjAgMzE4IEwgNjkwIDM3MiBMIDYwMCAzMzAgTCA1MDAgMzkyIEwgNDAwIDMzMCBMIDMxMCAzNzIgTCAyNDAgMzE4IEwgMTEwIDM2MiBMIDk1IDMzNSBaIi8+CiAgPHBhdGggc3Ryb2tlLXdpZHRoPSIxLjQiIGQ9Ik01MDAgMTQwIEMgNTQwIDE1MCA1NjAgMTkwIDU2NiAyNTAgTCA1NjYgMzMwIE01MDAgMTQwIEMgNDYwIDE1MCA0NDAgMTkwIDQzNCAyNTAgTCA0MzQgMzMwIi8+CiAgPHBhdGggc3Ryb2tlLXdpZHRoPSIxLjQiIGQ9Ik00NjggMTk2IEwgNDg2IDE4NiBMIDQ4NiAyMzYgTCA0NjggMjQ0IFogTTUzMiAxOTYgTCA1MTQgMTg2IEwgNTE0IDIzNiBMIDUzMiAyNDQgWiIvPgo8L3N2Zz4K") no-repeat fixed;
  background-size:min(78vw, 980px) auto; background-position:78% 30%; }
.logo { position:relative; font-size:3.3rem; letter-spacing:.2em; padding:0 .1em .05em 0; transform:skewX(-9deg);
  background:linear-gradient(180deg,#ffffff 0%,#e3e9f2 36%,#8c96a5 49%,#2a2f37 51%,#6f7a89 64%,#dfe5ee 82%,#ffffff 100%);
  -webkit-background-clip:text; background-clip:text; color:transparent; filter:drop-shadow(0 0 10px rgba(255,120,60,.25)); }
.logo::after { content:""; position:absolute; left:0; right:0; bottom:0; height:46%;
  background:repeating-linear-gradient(180deg, transparent 0 4px, #0e1117 4px 6.5px); }
.logo-bar { height:3px; width:min(560px, 92%); border-radius:2px;
  background:linear-gradient(90deg,#ffb347 0%,#ff5e3a 40%,#d6246e 75%,rgba(214,36,110,0) 100%); }
</style>""",
    "phosphor": """<style>
@import url('https://fonts.googleapis.com/css2?family=VT323&display=swap');
.stApp { background:#050a05; }
.stApp::before { content:""; position:fixed; inset:0; pointer-events:none; z-index:999;
  background:repeating-linear-gradient(180deg, rgba(0,0,0,0) 0 2px, rgba(0,0,0,.22) 2px 3px); }
.logo { font-family:'VT323', monospace; font-size:4.4rem; letter-spacing:.12em; color:#5dff8a;
  text-shadow:0 0 6px rgba(93,255,138,.9), 0 0 18px rgba(93,255,138,.45); }
.logo::after { content:"_"; animation:blink 1s steps(1) infinite; }
@keyframes blink { 50% { opacity:0; } }
.logo-bar { background:#5dff8a; box-shadow:0 0 8px #5dff8a; width:min(420px, 80%); height:2px; }
.logo-sub { font-family:'VT323', monospace; font-size:1.25rem; letter-spacing:.3em; color:#3fbf63; }
.tk, .mast { font-family:'VT323', monospace !important; color:#7dffa0; letter-spacing:.04em; }
</style>""",
    "neon": """<style>
.stApp { background:radial-gradient(ellipse at 70% 0%, #2a0d3d 0%, #0e1117 55%); }
.logo { font-size:3.4rem; letter-spacing:.24em; color:transparent; -webkit-text-stroke:1.5px #ff4fd8;
  text-shadow:0 0 8px rgba(255,79,216,.85), 0 0 22px rgba(255,79,216,.45), 0 0 40px rgba(80,220,255,.25); }
.logo-bar { width:min(520px, 90%); height:2px; background:linear-gradient(90deg,#50dcff,#ff4fd8);
  box-shadow:0 0 10px #50dcff; }
.logo-sub { color:#50dcff; text-shadow:0 0 6px rgba(80,220,255,.7); }
</style>""",
    "redline": """<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
.stApp { background:#121010 url("data:image/svg+xml;base64,PHN2ZyBvcGFjaXR5PSIwLjAzNSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB2aWV3Qm94PSIwIDAgMTAwMCA2NDAiIGZpbGw9Im5vbmUiIHN0cm9rZT0iI2ZmNmEzZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+CiAgPHBhdGggc3Ryb2tlLXdpZHRoPSIyLjQiIGQ9Ik01MDAgMTEwIEwgOTA1IDMzNSBMIDg5MCAzNjIgTCA3NjAgMzE4IEwgNjkwIDM3MiBMIDYwMCAzMzAgTCA1MDAgMzkyIEwgNDAwIDMzMCBMIDMxMCAzNzIgTCAyNDAgMzE4IEwgMTEwIDM2MiBMIDk1IDMzNSBaIi8+CiAgPHBhdGggc3Ryb2tlLXdpZHRoPSIxLjQiIGQ9Ik01MDAgMTQwIEMgNTQwIDE1MCA1NjAgMTkwIDU2NiAyNTAgTCA1NjYgMzMwIE01MDAgMTQwIEMgNDYwIDE1MCA0NDAgMTkwIDQzNCAyNTAgTCA0MzQgMzMwIi8+CiAgPHBhdGggc3Ryb2tlLXdpZHRoPSIxLjQiIGQ9Ik00NjggMTk2IEwgNDg2IDE4NiBMIDQ4NiAyMzYgTCA0NjggMjQ0IFogTTUzMiAxOTYgTCA1MTQgMTg2IEwgNTE0IDIzNiBMIDUzMiAyNDQgWiIvPgo8L3N2Zz4K") no-repeat fixed;
  background-size:min(80vw, 1000px) auto; background-position:80% 28%; }
.logo { color:#ffe9dc; letter-spacing:.3em; border:1.5px solid #ff6a3d; padding:.35rem .6rem .35rem .8rem;
  box-shadow:0 0 14px rgba(255,106,61,.25); }
.logo-bar { display:none; }
.logo-sub { font-family:'Share Tech Mono', monospace; font-size:.95rem; color:#ff8a5c; margin-top:.4rem; }
</style>""",
}   # Alex 2026-11-09: the easter egg (click the first story's status light)
EDIT = "--edit" in __import__("sys").argv or os.environ.get("EVENT_SITE_EDIT") == "1"   # Alex's local rank editor (launch config event-site-edit); never on the live site
NOT_ADVICE = ""  # Alex 2026-11-06: dropped
GOLD, BLUE, DIM = "#d9a441", "#5b8def", "#9aa3b2"
PICKED = ["#e5534b", "#3fb27f", "#c678dd", "#56b6c2", "#f0f0f0", "#e5a0d6", "#98c379", "#ff9e64"]  # ticked cases
RECENT_COLS = ["#56b6c2", "#c678dd", "#e06c75", "#98c379", "#61afef", "#e5a0d6", "#f0f0f0", "#7ee0c8"]  # last year (no yellow)

st.set_page_config(page_title="Polecat Event Trajectory Explorer", layout="wide")
FUN = st.query_params.get("fun") if st.query_params.get("fun") in THEMES else None


def clear_qp():
    """Clear the page's query params but keep the easter-egg look on."""
    st.query_params.clear()
    if FUN:
        st.query_params["fun"] = FUN

st.markdown("""<style>
.stApp { background:#0e1117; color:#e6e9ef; } .block-container { padding-top:3.6rem; max-width:1100px; }
.chiron { overflow:hidden; white-space:nowrap; border-top:1px solid #2a3140; border-bottom:1px solid #2a3140;
          background:#11161f; padding:.45rem 0; margin:.3rem 0 1.2rem 0; }
.chiron span.run { display:inline-block; padding-left:100%; animation:roll 90s linear infinite; }
.chiron:hover span.run { animation-play-state:paused; }
.chiron b { color:#d9a441; font-weight:600; margin-right:.4rem; } .chiron i { color:#9aa3b2; font-style:normal; margin:0 2.2rem 0 .3rem; }
@keyframes roll { from { transform:translateX(0); } to { transform:translateX(-100%); } }
@import url('https://fonts.googleapis.com/css2?family=Michroma&display=swap');
.logo { display:inline-block; font-family:'Michroma', 'Eurostile', sans-serif; font-size:2.9rem; letter-spacing:.16em;
  line-height:1; color:#eef1f5; margin:.2rem 0 .45rem 0; }
.logo-bar { height:2px; width:2.6rem; margin:0 0 .5rem .1rem; background:#d9a441; }
.logo-sub { font:700 .8rem/1 "Helvetica Neue", Helvetica, Arial, sans-serif; letter-spacing:.32em; color:#9aa3b2;
  margin:0 0 .6rem .1rem; }
.mast { font-family:"Helvetica Neue", Helvetica, Arial, sans-serif; font-weight:700; font-size:2.8rem; letter-spacing:-.01em; line-height:1.1; margin:0 0 .2rem 0; }
.tk { font-family:"Helvetica Neue", Helvetica, Arial, sans-serif; font-weight:700; font-size:2.8rem; letter-spacing:-.01em; line-height:1.05; margin:0; }
.tk.small { font-size:2.1rem; }
.why { font-size:1.2rem; margin:.3rem 0 .8rem 0; } .meta { color:#9aa3b2; font-size:.85rem; }
.big { font-size:2rem; font-weight:600; } .up { color:#3fb27f; } .down { color:#e5534b; }
.box, div[data-testid="stTextInput"] div[data-baseweb="input"] { background:#161b24; border:1px solid #2a3140; border-radius:8px; }
.box { padding:.9rem 1.1rem; height:100%; }
div[data-testid="stTextInput"] div[data-baseweb="base-input"], div[data-testid="stTextInput"] input { background:transparent; }
.onair { display:inline-flex; align-items:center; gap:.5rem; padding:.28rem .85rem .28rem .6rem; border:1.5px solid #e6e9ef;
  border-radius:8px; font:700 .78rem/1 "Helvetica Neue", Helvetica, Arial, sans-serif; letter-spacing:.14em;
  background:linear-gradient(180deg,#2a303b 0%,#151a22 100%);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.18), inset 0 -2px 4px rgba(0,0,0,.6), 0 2px 6px rgba(0,0,0,.5); vertical-align:middle; }
.onair .led { width:.72rem; height:.72rem; border-radius:50%; box-shadow:inset 0 -1px 2px rgba(0,0,0,.5); }
.onair.on { color:#7dffb0; text-shadow:0 0 6px rgba(63,220,127,.9); }
.onair.on .led { background:radial-gradient(circle at 35% 30%,#d8ffe8 0%,#3fdc7f 45%,#0d7a3c 100%);
  box-shadow:0 0 8px 2px rgba(63,220,127,.8), 0 0 18px 4px rgba(63,220,127,.35); animation:glow 1.8s ease-in-out infinite; }
.onair.pend { color:#ffcf70; text-shadow:0 0 6px rgba(240,170,40,.8); }
.onair.pend .led { background:radial-gradient(circle at 35% 30%,#fff1c9 0%,#f0aa28 45%,#8a5a07 100%);
  box-shadow:0 0 8px 2px rgba(240,170,40,.7), 0 0 16px 4px rgba(240,170,40,.3); }
.onair.off { color:#8b929e; }
.onair.off .led { background:radial-gradient(circle at 35% 30%,#9aa1ab 0%,#5a606a 55%,#2e333a 100%); }
@keyframes glow { 0%,100% { box-shadow:0 0 6px 1px rgba(63,220,127,.7), 0 0 14px 3px rgba(63,220,127,.25); }
                  50% { box-shadow:0 0 10px 3px rgba(63,220,127,.95), 0 0 24px 6px rgba(63,220,127,.45); } }
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


RELABEL = {"The US market": "US equities", "the US market": "US equities", "Chip stocks": "Semiconductors",
           "Oil": "WTI crude", "Energy stocks": "Energy sector", "Bank stocks": "Financials",
           "Long Treasury bonds": "Long-dated Treasuries", "Junk-bond spreads": "High-yield spreads",
           "The dollar": "The dollar (broad index)"}   # Alex 2026-11-09: labels in editions built before the rename


RANK = {"cheap": "Value (B/P)", "profitable": "Profitability (OP/A)", "past winners": "Momentum (12-1)",
        "beaten down": "Far below 12m high", "calm": "Low volatility", "small": "Small cap",
        "R&D-heavy for their price": "R&D / price", "big payers": "Shareholder yield", "high beta": "High beta"}


def rk(k: str) -> str:
    """A ranking's display label (Alex 2026-11-11 copy edit); the data keeps scan.py's names."""
    return RANK.get(k.split(" (")[0], k)


def relabel(X: dict | None) -> dict | None:
    if X:
        for k in ("subject", "measure", "against"):
            if X.get(k) in RELABEL:
                X[k] = RELABEL[X[k]]
    return X


def measure(X: dict) -> str:
    """What a market exhibit's results are measured on, lower-cased for a sentence ("chip stocks", "the US stock average")."""
    m_ = X.get("measure") or "The US stock average"
    w = m_.split(" ", 1)[0]
    return ("the" + m_[3:] if m_.startswith("The ") else m_ if w in ("Brent", "Bitcoin", "Gold") or (len(w) > 1 and w.isupper())
            else m_[:1].lower() + m_[1:])   # keep US, WTI


def trig(X: dict) -> str:
    """The event trigger in words, lower-cased to follow a colon ("a stock that tripled ...")."""
    t = (X.get("plain") or X["event"]).strip().rstrip(".")
    w = t.split(" ", 1)[0]
    return t if len(w) > 1 and w.isupper() else t[:1].lower() + t[1:]   # keep tickers and acronyms (VIX, S&P)


def day(d: str) -> str:
    t = pd.Timestamp(d)
    return f"{t:%b} {t.day}, {t.year}"


def lib_status(X: dict) -> tuple[bool, str]:
    """Library page: (happening now?, the day it last happened). Market pages are 'pending' when they did not fire
    in the last week; their last past case is then the last time it happened."""
    if X["kind"] == "stock":
        return bool(X.get("recent")), X["event_date"]
    active = not X.get("pending")
    last = X["event_date"] if active else max((c["date"] for c in X["cases"]), default=X["event_date"])
    return active, last


def egg_wrap(badge: str, egg: bool) -> str:
    """The first story's status light doubles as a secret switch for the fun look (Alex 2026-11-09)."""
    if not egg:
        return badge
    import random
    nxt = "0" if FUN else random.choice(list(THEMES))   # off when on; a random look when off
    return f"<a href='?fun={nxt}' target='_self' style='text-decoration:none'>{badge}</a>"


def badge_html(active) -> str:
    """True: ACTIVE (green). False: INACTIVE (grey). "pending": in the news today, not in our prices yet (amber;
    Alex 2026-11-09). It turns green the next morning once the close is in, if the move met the rule."""
    if active == "pending":
        return "<span class='onair pend'><span class='led'></span>PENDING</span>"
    return (f"<span class='onair {'on' if active else 'off'}'><span class='led'></span>"
            f"{'ACTIVE' if active else 'INACTIVE'}</span>")


def headline(X: dict, small: bool = False, egg: bool = False):
    if X.get("library"):
        active, last = lib_status(X)
        r_ = X.get("recent") or []
        badge = badge_html(active)
        line = f"Last triggered {day(last)}" + (
            f" · past week: {', '.join(r_[:10])}{' and others' if len(r_) > 10 else ''}" if active and r_ else "")
        st.markdown(f"<div class='tk{' small' if small else ''}'>{html.escape((X['plain'] or X['event']).rstrip('.'))}</div>"
                    f"<div style='margin:.55rem 0 .9rem 0'>{badge}<span class='meta' style='margin-left:.8rem'>{line}</span></div>",
                    unsafe_allow_html=True)
        return
    when = (f"In today's news; prices through {day(X['data_through'])}" if X.get("pending")
            else f"Last triggered {day(X['event_date'])}" if X.get("library") else f"Triggered {day(X['event_date'])}")
    y = X.get("year_before")
    if X.get("library") and X["kind"] == "stock":
        r_ = X.get("recent") or []
        yb = (f" · past week: {', '.join(r_[:10])}{' and others' if len(r_) > 10 else ''}" if r_ else "")
    elif y is None:
        yb = ""
    elif X["kind"] == "stock":
        yb = f" · prior 12 months: {pct(y)} relative to S&amp;P 500"
    else:
        m_ = measure(X)
        yb = f" · prior 12 months: {pct(y)}"
    st.markdown(f"<div class='tk{' small' if small else ''}'>{html.escape(X['subject'])}</div>"
                f"<div class='why'>{html.escape(X['plain'] or X['event'])}</div>"
                f"<div style='margin:-.2rem 0 .9rem 0'>{egg_wrap(badge_html('pending' if X.get('pending') else True), egg)}"
                f"<span class='meta' style='margin-left:.8rem'>{when}{yb}</span></div>", unsafe_allow_html=True)


def takeaway(X: dict) -> str:
    """One plain sentence from the counts (Alex 2026-11-06: readers asked for a takeaway). Rules, no model:
    a hold "leans" one way when 60%+ of cases went that way and the median agrees; the stronger lean (share further
    from half, then the bigger median) is the one called out."""
    cs = X["cases"]
    stock = X["kind"] == "stock"
    M_ = measure(X)
    M_ = M_[:1].upper() + M_[1:]
    up_word, down_word = ("Outperformed", "Underperformed") if stock else (f"{M_} higher", f"{M_} lower")
    leans = []
    for h, name in ((21, "1 month"), (252, "1 year")):
        n, w, _, m = tally([c[f"after_{h}"] for c in cs])
        if n < 5 or m is None:
            continue
        share = w / n
        lean = "up" if share >= 0.6 and m > 0 else "down" if share <= 0.4 and m < 0 else None
        leans.append((h, name, n, w, m, share, lean))
    if not leans:
        return "Too few past cases."
    called = [x for x in leans if x[5] is not None and x[6]]
    if not called:
        return "No clear lean at 1 month or 1 year."
    best = max(called, key=lambda x: (abs(x[5] - 0.5), abs(x[4])))
    word = up_word if best[6] == "up" else down_word
    both = len(called) == 2 and called[0][6] == called[1][6]
    when = (f"at 1 month and 1 year, strongest at {best[1]}" if both else f"at {best[1]}")
    other = [x for x in leans if x is not best and not (both and x in called)]
    tail = f"; {other[0][1]} mixed" if other else ""
    few = " Small sample." if min(x[2] for x in leans) < 10 else ""
    return (f"{word} {when}: {'hit rate ' if stock else 'up in '}{best[3]} of {best[2]}, median {pct(best[4])}"
            f"{tail}.{few}")


def take_box(X: dict):
    st.markdown(f"<div class='take'><b>Takeaway</b>{html.escape(takeaway(X))}</div>", unsafe_allow_html=True)


def boxes(X: dict):
    cs = X["cases"]
    n1, w1, a1, m1 = tally([c["after_21"] for c in cs])
    n2, w2, a2, m2 = tally([c["after_252"] for c in cs])
    did = "outperformed" if X["kind"] == "stock" else f"{measure(X)} up"
    since = f"since {min(c['date'] for c in cs)[:4]}" if cs else "none yet"
    first = "Past cases"
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"<div class='box'><span class='meta'>{first}</span><br><span class='big'>{len(cs)}</span><br>"
                f"<span class='meta'>{since}</span></div>", unsafe_allow_html=True)
    for col, name, n, w, a, m in ((c2, "1 month", n1, w1, a1, m1), (c3, "1 year", n2, w2, a2, m2)):
        col.markdown(f"<div class='box'><span class='meta'>{name}, {did}</span><br><span class='big'>"
                     f"{f'{w} of {n}' if n else '–'}</span><br><span class='meta'>median <span class='{cls(m)}'>"
                     f"{pct(m)}</span> · mean {pct(a)}</span></div>", unsafe_allow_html=True)


def overlay(X: dict, sel: set | None = None, box: str | None = None, rsel: set | None = None):
    """sel: case numbers ticked in the table; when some are ticked only those past cases are drawn.
    box: widget key for the ticker box (stock filter pages); it sits on the toggles' row (Alex 2026-11-11)."""
    step, B = X["step"], X["before"]
    x = np.arange(-B, X["after"] + 1, step)
    p0 = X.get("paths_from", 0)
    P = np.array([[np.nan if v is None else v for v in p] for p in X["paths"]], float).reshape(-1, len(x))
    fig = go.Figure()
    for i, p in enumerate(P):
        c = X["cases"][p0 + i]
        lab = f"{c['who']} {c['date']}".strip()
        if (sel or rsel) and p0 + i not in (sel or set()):
            continue
        fig.add_scatter(x=x, y=p, mode="lines", hoverinfo="text", text=lab, name=lab, showlegend=bool(sel),
                        line=dict(color=PICKED[len(fig.data) % len(PICKED)] if (sel or rsel) else "rgba(154,163,178,.18)",
                                  width=2 if (sel or rsel) else 1))
    if box:   # Alex 2026-11-11: toggles stacked on the left, ticker box beside them, right third left for warnings
        c1, c3, cw = st.columns(3)
        c2 = c1
    else:
        c1, c2, c3, cw = st.container(), st.container(), None, st
    extra, bad = [], []
    if box:   # readers' stocks, each one's last year up to today (0 = today); several, comma-separated
        ov = load_overlay()
        typed = c3.text_input("Tickers (comma-separated)", key=box, placeholder="Tickers (comma-separated)",
                              label_visibility="collapsed")
        for tk in dict.fromkeys(t.strip().upper() for t in re.split(r"[,\s]+", typed) if t.strip()):
            if ov and tk in ov["series"]:
                extra.append((tk, ov["offsets"], ov["series"][tk]))
            else:
                bad.append(tk)
    band = c1.toggle("Show the range of 80% of past cases", value=True, key=f"band_{X['event']}_{X['subject']}")
    if len(P):
        ok = np.isfinite(P).sum(0) >= 5
        with np.errstate(all="ignore"):
            med = np.where(ok, np.nanmedian(P, axis=0), np.nan)
            lo = np.where(ok, np.nanpercentile(P, 10, axis=0), np.nan)
            hi = np.where(ok, np.nanpercentile(P, 90, axis=0), np.nan)
        if band:
            fig.add_scatter(x=x, y=hi, mode="lines", line=dict(width=0), hoverinfo="skip", showlegend=False)
            fig.add_scatter(x=x, y=lo, mode="lines", line=dict(width=0), fill="tonexty",
                            fillcolor="rgba(91,141,239,.30)", name="10–90% band", hoverinfo="skip")
        fig.add_scatter(x=x, y=med, mode="lines", line=dict(color=BLUE, width=3), name="median path")
    rc = X.get("recent_cases") or []
    if rc:
        show = c2.toggle(f"Show the {len(rc)} case{'' if len(rc) == 1 else 's'} from the last year", value=bool(X.get("library")) and not X.get("custom"),   # custom studies: off by default (Alex 2026-11-11)
                         key=f"rc_{X['event']}_{X['subject']}",
                         help="Excluded from the counts: 1-year window incomplete.")
        k = 0
        for i, c in enumerate(rc):
            if c.get("path") is None or not ((show and not sel and not rsel) or (rsel and i in rsel)):
                continue
            yv = [np.nan if v is None else v for v in c["path"]]
            fin = [j for j, v in enumerate(yv) if np.isfinite(v)]
            lab = c["who"] or c["date"]
            col = RECENT_COLS[k % len(RECENT_COLS)]
            k += 1
            fig.add_scatter(x=x, y=yv, mode="lines", line=dict(color=col, width=2), name=f"{lab} ({c['date']})",
                            hoverinfo="text", text=f"{lab} {c['date']}", showlegend=False)
            if fin:
                fig.add_annotation(x=x[fin[-1]], y=yv[fin[-1]], text=f"<b>{html.escape(lab)}</b>", showarrow=False,
                                   xanchor="left", font=dict(color="#0e1117", size=11), bgcolor=col,
                                   borderpad=2, xshift=4)
    s = np.array([np.nan if v is None else v for v in X["path"]], float)
    if X.get("library") and not lib_status(X)[0]:
        s = s * np.nan
    if np.isfinite(s).any():
        fig.add_scatter(x=x, y=s, mode="lines", line=dict(color=GOLD, width=4),
                        name=f"{X['subject'] if X['kind'] == 'stock' else 'now'} (to {X['data_through']})")
    for k_, (lab, xo, yo) in enumerate(extra):   # drawn like the last-year cases: a coloured line with its own tag
        yv = [np.nan if v is None else v for v in yo]
        col = ([GOLD] + RECENT_COLS[::-1])[k_ % (1 + len(RECENT_COLS))]
        fig.add_scatter(x=xo, y=yv, mode="lines", line=dict(color=col, width=3), name=lab, hoverinfo="text",
                        text=f"{lab}, trailing year to {X['data_through']} (t=0 is today)", showlegend=False)
        fin = [j for j, v in enumerate(yv) if np.isfinite(v)]
        if fin:   # every typed stock ends at 0 today, so its tag sits at the start of its line
            fig.add_annotation(x=xo[fin[0]], y=yv[fin[0]], text=f"<b>{html.escape(lab)}</b>", showarrow=False,
                               xanchor="left", font=dict(color="#0e1117", size=11), bgcolor=col, borderpad=2)
    for tk in bad:
        cw.error(f"{tk}: Name not currently included in dataset", icon="🚩")
    if len(extra) > 1 and X.get("custom"):
        c3.caption(f"Factor cuts use {extra[0][0]} (first ticker).")
    fig.add_vline(x=0, line_color=DIM, line_dash="dot")
    yr = None
    if len(P) and not sel:   # fit the scale to the 80% band (with room), so a few extreme cases do not squash it
        with np.errstate(all="ignore"):
            lo_, hi_ = np.nanmin(np.nanpercentile(P, 5, axis=0)), np.nanmax(np.nanpercentile(P, 95, axis=0))
        if np.isfinite(lo_) and np.isfinite(hi_):
            pad = (hi_ - lo_) * 0.15
            yr = [lo_ - pad, hi_ + pad]
    ylab = (f"return relative to {X['against'].replace('the S&P 500 average', 'S&P 500')}, from t=0" if X["kind"] == "stock"
            else f"{measure(X)}, return from t=0")
    fig.update_layout(height=440, margin=dict(l=0, r=10, t=30, b=10), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font_color="#e6e9ef", legend=dict(orientation="h", y=1.08, x=0),
                      xaxis=dict(title="trading days from event day (t=0)", gridcolor="#2a3140"),
                      yaxis=dict(title=ylab, tickformat="+.0%", gridcolor="#2a3140", zerolinecolor=DIM, range=yr))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    if X.get("paths_from"):
        st.caption(f"Paths for the {len(P)} most recent cases only.")


def bars(rows: list, did: str):
    """rows: (ranking, (value, won, n) at 1 month, (value, won, n) at 1 year); grouped horizontal bars."""
    rows = [r for r in rows if (r[1][2] or 0) or (r[2][2] or 0)]
    if not rows:
        st.caption("Too few past cases.")
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


def back():
    """Back to the search a page was opened from (?from=search&q=...), else to today."""
    if st.query_params.get("from") == "search":
        if st.button("← Back to search"):
            q_ = st.query_params.get("q", "")
            clear_qp()
            st.query_params.update({"view": "search", "q": q_})
            st.rerun()
    elif st.button("← Back to today"):
        clear_qp()
        st.rerun()


def full(s: dict, X: dict, also: list | None = None):
    back()
    headline(X)
    boxes(X)
    take_box(X)
    who = "Now" if X["kind"] != "stock" else ("Event paths" if X.get("library") else X["subject"])
    st.markdown(f"**Event paths · {len(X['cases'])} past cases**" if X.get("library") and not (X["kind"] != "stock" and lib_status(X)[0])
                else f"**{who} vs. {len(X['cases'])} past cases**")
    box = f"ov_{X.get('id')}" if X.get("library") and X["kind"] == "stock" else None
    chart = st.container()   # drawn after the table, so the ticks in the table choose its lines
    cases = pd.DataFrame(X["cases"])
    sel: set = set()
    if X.get("rankings"):
        st.markdown(f"**Factor cuts: {html.escape(X['subject'])}**",
                    help="Top quintile within the S&P 500 on the event day. Median return relative to S&P 500.")
        rows = []
        for k, idx in X["rankings"].items():
            sub = cases.iloc[idx] if idx else cases.iloc[0:0]
            a, b = tally(sub.after_21.tolist()), tally(sub.after_252.tolist())
            rows.append((rk(k), (a[3], a[1], a[0]), (b[3], b[1], b[0])))
        bars(rows, "outperformed")
    elif X.get("custom") and len(cases) and "pk" in cases.columns:
        # Alex 2026-11-11: a custom study has no stock of its own, so a stand-in stock picks the cut: the rankings it
        # sits in today, and how the past cases that sat in the same ranking did. No stock typed: all the rankings.
        names = list(ed.get("picks") or {})
        now = ed.get("picks_now") or {}
        # the stock is the first one typed in the Tickers box above the chart that is in the price file (the box
        # is drawn later in this run, so its text is read from the session state)
        ov = load_overlay() or {"series": {}}
        typed = [t.strip().upper() for t in re.split(r"[,\s]+", st.session_state.get(box) or "") if t.strip()]
        tk = next((t for t in typed if t in ov["series"]), "")
        use = list(range(len(names)))
        if tk and tk not in now:
            st.warning(f"{tk}: no factor rankings (financials excluded). Showing all rankings.", icon="⚠️")
            tk = ""
        elif tk:
            use = now[tk]
        if tk and not use:
            st.caption(f"{tk}: in no top quintile today; no factor cut.")
        else:
            st.markdown(f"**Factor cuts: {html.escape(tk)}**" if tk else "**Factor cuts**",
                        help=(f"Rankings where {tk} is top quintile today. " if tk else "")
                             + "Top quintile within the S&P 500 on the event day. Median return relative to S&P 500.")
            rows = []
            for j in use:
                sub = cases[cases.pk.map(lambda v: j in (v or []))]
                a, b = tally(sub.after_21.tolist()), tally(sub.after_252.tolist())
                rows.append((rk(names[j]), (a[3], a[1], a[0]), (b[3], b[1], b[0])))
            a, b = tally(cases.after_21.tolist()), tally(cases.after_252.tolist())
            rows.append(("All cases", (a[3], a[1], a[0]), (b[3], b[1], b[0])))
            none = [r[0] for r in rows if not ((r[1][2] or 0) or (r[2][2] or 0))]
            bars(rows, "outperformed")
            if none:
                st.caption(f"No past cases: {', '.join(none)}.")
    elif X["kind"] != "stock" and (X.get("lead") or {}).get("picks_21"):
        st.markdown("**Factor returns after the event**",
                    help="Top quintile of the S&P 500 on each ranking. Mean return relative to S&P 500.")
        Ld = X["lead"]
        by = {r["pick"]: r for r in Ld.get("picks_252") or []}
        bars([(rk(r["pick"]), (r.get("avg"), r.get("won"), r.get("n")),
               ((by.get(r["pick"]) or {}).get("avg"), (by.get(r["pick"]) or {}).get("won"), (by.get(r["pick"]) or {}).get("n")))
              for r in Ld["picks_21"]], "outperformed")
    rsel: set = set()
    rc = X.get("recent_cases") or []
    if len(cases) or rc:
        st.markdown("**Past cases**")
        cols = (["who"] if X["kind"] == "stock" else []) + ["date", "year_before", "after_21", "after_252"]
        R = pd.DataFrame(rc)[cols].assign(_src="r", _i=range(len(rc))) if rc else pd.DataFrame(columns=cols + ["_src", "_i"])
        O = cases[cols].assign(_src="o", _i=range(len(cases))) if len(cases) else pd.DataFrame(columns=cols + ["_src", "_i"])
        # Alex 2026-11-11: active cases (last year, still running) go at the bottom of the table, not the top
        t = pd.concat([O.sort_values("date", ascending=False), R.sort_values("date", ascending=False)], ignore_index=True)
        src = list(zip(t["_src"], t["_i"]))
        for c in ("year_before", "after_21", "after_252"):
            t[c] = t[c].map(pct)
        t.insert(0, "active", ["\U0001F7E2" if a == "r" else "" for a, _ in src])
        t = t.drop(columns=["_src", "_i"]).rename(columns={"who": "ticker", "year_before": "prior 12m",
                                                            "after_21": "1 month", "after_252": "1 year"})
        ev = st.dataframe(t, hide_index=True, use_container_width=True, key=f"pick_{s['id']}",
                          on_select="rerun", selection_mode="multi-row")
        rows = ev.selection.rows if ev and ev.selection else []
        sel = {int(src[r][1]) for r in rows if src[r][0] == "o"}
        rsel = {int(src[r][1]) for r in rows if src[r][0] == "r"}
    if also and st.button(f"Similar cases ({len(also)}) →"):
        st.query_params.update({"view": "similar"})
        st.rerun()
    with chart:
        overlay(X, sel, box, rsel)
    if s.get("headline"):
        st.markdown(f"<p class='news'><b>News:</b> {html.escape(s['headline'])}. {html.escape(s.get('summary', ''))}</p>",
                    unsafe_allow_html=True)
    src = " · ".join(f"<a href='{html.escape(x.get('url', ''))}' target='_blank'>{html.escape(x.get('title') or 'source')}</a>"
                     for x in s.get("sources", [])[:3])
    st.markdown(f"<span class='meta'>{src}<br>Rule: <code>{html.escape(X['event'])}</code>. Returns relative to "
                f"{X['against'].replace('the S&P 500 average', 'S&amp;P 500')} (equal-weighted, ex-financials); entry at next close. "
                f"Prices through {X['data_through']}. {NOT_ADVICE}</span>", unsafe_allow_html=True)


def card(s: dict, X: dict, i: int, j: int = 0, n_also: int = 0):
    with st.container(border=True):
        headline(X, small=True, egg=(i == 0 and not CUR_DAY))
        boxes(X)
        take_box(X)
        extra = ""
        st.markdown(f"<p class='news'>{html.escape(s['headline'])}<span class='meta'>{extra}</span></p>", unsafe_allow_html=True)
        b1, b2, _ = st.columns([1, 1.3, 5])
        if b1.button("Details →", key=f"open{i}"):
            clear_qp()
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

if FUN:
    st.markdown(THEMES[FUN], unsafe_allow_html=True)
st.markdown("<div class='logo'>POLECAT</div><div class='logo-bar'></div>"   # Alex 2026-11-09: 70s-80s tech logotype
            "<div class='logo-sub'>EVENT TRAJECTORY EXPLORER</div>", unsafe_allow_html=True)
if not today:
    st.info("No edition published yet.")
    st.stop()


LIB = DATA / "library"


@st.cache_data(ttl=3600, show_spinner=False)
def load_lib_index(stamp: float) -> list:
    with gzip.open(DATA / "library_index.json.gz", "rt", encoding="utf-8") as fh:
        return json.load(fh)


@st.cache_data(ttl=3600, show_spinner=False)
def load_lib(pid: str, stamp: float) -> dict:
    with gzip.open(LIB / f"{pid}.json.gz", "rt", encoding="utf-8") as fh:
        return relabel(json.load(fh))


@st.cache_data(ttl=3600, show_spinner=False)
def _overlay(stamp: float) -> dict:
    with gzip.open(DATA / "overlay.json.gz", "rt", encoding="utf-8") as fh:
        return json.load(fh)


def load_overlay():
    f = DATA / "overlay.json.gz"
    return _overlay(f.stat().st_mtime) if f.exists() else None


def lib_index() -> list:
    f = DATA / "library_index.json.gz"
    return load_lib_index(f.stat().st_mtime) if f.exists() else []


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
            + (" · archived edition" if CUR_DAY else "") + "</span>", unsafe_allow_html=True)
stories = ed["stories"]
groups = [{"key": g.get("key"), "lead": (stories[g["lead"][0]], g["lead"][1]), "also": [(stories[i], j) for i, j in g["also"]]}
          for g in ed.get("front") or []]


RECENT = bool(st.session_state.get("recent", False))   # the switch itself sits at the bottom of the page


def recent_switch():
    st.toggle("Include last-year cases", key="recent",
              help="Off: only cases with a complete 1-year window.")


def trim(X: dict | None) -> dict | None:
    """Alex 2026-11-06: by default only past cases at least a year old (their 1-year result is in), so recent cases
    that overlap each other and today's move do not crowd the counts, the chart or the table."""
    if X is None or RECENT:
        return X
    keep = [i for i, c in enumerate(X["cases"]) if c.get("after_252") is not None]
    new = {old: k for k, old in enumerate(keep)}
    p0 = X.get("paths_from", 0)
    pk = [(new[p0 + i], p) for i, p in enumerate(X["paths"]) if p0 + i in new]
    pth = {p0 + i: p for i, p in enumerate(X["paths"])}
    rec = [{**X["cases"][i], "path": pth.get(i)} for i in range(len(X["cases"])) if i not in new]
    return {**X, "cases": [X["cases"][i] for i in keep], "paths": [p for _, p in pk], "recent_cases": rec,
            "paths_from": pk[0][0] if pk else 0,
            "rankings": {k: [new[i] for i in v if i in new] for k, v in (X.get("rankings") or {}).items()}}


def ex(s, j):
    return relabel(trim((s.get("exhibits") or [None])[j])) if j < len(s.get("exhibits") or []) else None


def search_ui(prefill: str = "", key: str = "q_tab"):
    q = st.text_input("Search event studies", value=prefill, key=key,
                      placeholder="oil crash, chip sell-off, stock up 10x then drops ...")
    if archive:
        df = pd.DataFrame(archive).assign(src="news")
        df = df.drop_duplicates(["story_id", "event"]).reset_index(drop=True)   # a story kept for days: newest copy
        li = lib_index()
        if li:   # the library: base-rate questions people look up (library_gen.py / library_build.py)
            L = pd.DataFrame(li).assign(src="library", headline=lambda d: d.title, summary="", tickers=[[]] * len(li),
                                        story_id=None, date="library", lead=None)
            df = pd.concat([df, L], ignore_index=True)
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
                    st.caption(f"Semantic search unavailable ({type(exc).__name__}); keyword match used.")
            if order is None:
                order = word_search(q, tuple(df.text))
            df = df.iloc[order]
        st.caption(f"{len(df)} studies" + (" matched" if q.strip() else ", newest first"))
        for r in df.head(30).itertuples():
            lead = r.lead or {}
            parts = []
            for h, name in (("21", "1 month"), ("252", "1 year")):
                a = lead.get(f"after_{h}") or {}
                if a.get("n"):
                    parts.append(f"{name}: {'outperformed' if r.kind == 'stock' else 'up'} {a.get('won')} of {a['n']} "
                                 f"(mean {pct(a.get('avg'))})")
            if r.src == "library":
                with st.expander(f"Library · {r.plain}"):
                    st.markdown(f"<code>{html.escape(r.event)}</code> · {r.past_cases} past cases<br>"
                                f"{html.escape(r.line)}", unsafe_allow_html=True)
                    if st.button("Open →", key=f"lib{r.Index}"):
                        clear_qp()
                        st.query_params.update({"lib": r.id, "from": "search", "q": q})
                        st.rerun()
                continue
            with st.expander(f"{r.date} · {r.headline} — {r.plain}"):
                st.markdown(f"<code>{html.escape(r.event)}</code> · {r.past_cases} past cases<br>"
                            f"{'; '.join(parts) or 'too few past cases'}", unsafe_allow_html=True)
                if st.button("Open →", key=f"srch{r.Index}"):
                    f_ = DATA / "days" / f"{r.date}.json.gz"
                    E_ = today if r.date == today["date"] else (load_day(r.date, f_.stat().st_mtime) if f_.exists() else None)
                    s_ = next((x for x in (E_ or {}).get("stories", []) if x["id"] == r.story_id), None)
                    j_ = next((k for k, x in enumerate((s_ or {}).get("studies", [])) if x.get("event") == r.event), None)
                    if s_ is None or j_ is None or not ((s_.get("exhibits") or [None] * (j_ + 1))[j_]):
                        st.caption("Full page unavailable.")
                    else:
                        clear_qp()
                        st.query_params.update({"story": r.story_id, "v": str(j_), "from": "search", "q": q,
                                                **({"day": r.date} if r.date != today["date"] else {})})
                        st.rerun()
    else:
        st.caption("No studies archived yet.")



if st.query_params.get("view") == "search":
    if st.button("← Back to today"):
        clear_qp()
        st.rerun()
    search_ui(st.query_params.get("q", ""), key="q_view")
    st.stop()


lib_id = st.query_params.get("lib")
if lib_id and (LIB / f"{lib_id}.json.gz").exists():
    XL = trim(load_lib(lib_id, (LIB / f"{lib_id}.json.gz").stat().st_mtime))
    XL = {**XL, "subject": XL.get("plain") or XL["subject"]}   # the rule's own words, not the question's
    full({"id": lib_id}, XL)
    sib = [r for r in lib_index() if r["qid"] == XL.get("qid") and r["id"] != lib_id]
    if sib:
        st.markdown(f"### Similar cases: {html.escape(XL.get('title') or XL['subject'])}")
        for r in sib:
            if st.button(f"{r['plain']} ({r['past_cases']} past cases) →", key=f"sib{r['id']}"):
                keep_ = {k: st.query_params.get(k) for k in ("from", "q") if st.query_params.get(k)}
                clear_qp()
                st.query_params.update({"lib": r["id"], **keep_})
                st.rerun()
    recent_switch()
    st.stop()

open_id, open_v = st.query_params.get("story"), int(st.query_params.get("v", 0) or 0)
s_open = next((s for s in stories if s["id"] == open_id), None)
if s_open and ex(s_open, open_v):
    g = next((g for g in groups if (g["lead"][0]["id"], g["lead"][1]) == (open_id, open_v)
              or any((s2["id"], j2) == (open_id, open_v) for s2, j2 in g["also"])), None)
    others = [] if g is None else [(s2, j2, ex(s2, j2)) for s2, j2 in [g["lead"]] + g["also"]
                                   if (s2["id"], j2) != (open_id, open_v) and ex(s2, j2)]
    if st.query_params.get("view") == "similar":
        if st.button("← Back to today"):
            clear_qp()
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

tab_today, tab_search, tab_ask = st.tabs(["Today", "Search", "Commission a study"])

def edit_front(groups: list):
    """Alex 2026-11-09: move cards up or down, note what is wrong, save; the original and final order are kept
    (editor.py) so the ranking can learn from them. Local only."""
    import subprocess
    import sys
    import editor as EDT
    byk = {g["key"]: g for g in groups}
    rec = EDT.load(ed["date"])
    original = [k for k in (rec["original"] if rec else []) if k in byk] or list(byk)
    original += [k for k in byk if k not in original]
    if st.session_state.get("ord_day") != ed["date"]:
        st.session_state.ord_day = ed["date"]
        st.session_state.ord = [k for k in (rec["final"] if rec else original) if k in byk] +             [k for k in original if rec and k not in rec["final"]]
        for k, v in ((rec or {}).get("notes") or {}).items():
            st.session_state[f"note_{k}"] = v
    order = st.session_state.ord
    st.info("Edit mode (local only): move cards with ▲ ▼, write a note on any card, then save. Saving keeps the "
            "original and your order so the ranking learns from it.")
    for r, k in enumerate(order):
        if r == TOP:
            st.markdown("**Below the fold** (behind Load more)")
        g = byk[k]
        a, b = st.columns([0.07, 0.93])
        a.markdown(f"**#{r + 1}**" + (f"<br><span class='meta'>was #{original.index(k) + 1}</span>"
                                       if original.index(k) != r else ""), unsafe_allow_html=True)
        if a.button("▲", key=f"up_{k}", disabled=r == 0):
            order[r - 1], order[r] = order[r], order[r - 1]
            st.rerun()
        if a.button("▼", key=f"dn_{k}", disabled=r == len(order) - 1):
            order[r + 1], order[r] = order[r], order[r + 1]
            st.rerun()
        with b:
            card(g["lead"][0], ex(*g["lead"]), r, g["lead"][1], len(g["also"]))
            st.text_input("Note", key=f"note_{k}", placeholder="What's wrong or right with this one?",
                          label_visibility="collapsed")
    c1, c2, _ = st.columns([1, 1.2, 4])
    def _save():
        cards = {k: EDT.card_info(byk[k]["lead"][0], ex(*byk[k]["lead"])) for k in order}
        return EDT.save(ed["date"], original, list(order), {k: st.session_state.get(f"note_{k}", "") for k in order}, cards)
    if c1.button("Save"):
        r_ = _save()
        st.success(f"Saved {ed['date']}: order {'changed' if r_['changed'] else 'unchanged'}, {len(r_['notes'])} notes.")
    if c2.button("Save and publish"):
        _save()
        root = HERE.parents[1]
        with st.spinner("Exporting and pushing..."):
            py = root / ".venv" / "Scripts" / "python.exe"
            out = [subprocess.run([str(py if py.exists() else sys.executable), str(HERE / f)], cwd=root, capture_output=True, text=True,
                                  env={**os.environ, "PYTHONUTF8": "1"}) for f in ("export.py", "publish.py")]
        ok = all(o.returncode == 0 for o in out)
        (st.success if ok else st.error)("Published; the live site updates in a minute or two." if ok else
                                         "Publish failed: " + (out[-1].stderr or out[0].stderr)[-300:])


with tab_today:
  if EDIT and not CUR_DAY:
    edit_front(groups)
  else:
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
    search_ui()

with tab_ask:
    st.markdown("Describe the event and the asset (market, sector or stock type). Results are sent by email.")
    ask = st.text_area("Study request", placeholder="What happens to small caps after the 10-year yield jumps half a point in a month?")
    to = secret("request_email")
    if to:
        st.link_button("Send by email", f"mailto:{to}?subject={quote('Event study request')}&body={quote(ask)}",
                       disabled=not ask.strip())
    else:
        st.button("Requests open soon", disabled=True)
