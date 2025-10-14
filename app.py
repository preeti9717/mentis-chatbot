import datetime as dt
from pathlib import Path
import pandas as pd
import streamlit as st

# ---------- App config ----------
st.set_page_config(page_title="Mentis — Student Mental Health Companion", page_icon="🟢", layout="centered")
st.caption("Private, non‑clinical support; not medical advice.")  # onboarding microcopy [web:262]

# Color tokens
PRIMARY = "#2563EB"
SURFACE = "#0B1220"
TEXT_LIGHT = "#E5E7EB"
TEXT_MUTED = "#9CA3AF"
OK_GREEN = "#10B981"

# ---------- Paths / storage ----------
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
CSV_PATH = DATA_DIR / "entries.csv"

def load_history() -> pd.DataFrame:
    if CSV_PATH.exists():
        df = pd.read_csv(CSV_PATH, parse_dates=["timestamp"])
        return df.sort_values("timestamp")
    return pd.DataFrame(columns=["timestamp","score","focus","note"])

def append_entry(score:int, focus:str, note:str):
    if score is None or focus is None:
        return
    row = pd.DataFrame([{
        "timestamp": pd.Timestamp.now(),
        "score": int(score),
        "focus": str(focus),
        "note": (note or "").strip()[:500]
    }])
    header = not CSV_PATH.exists()
    row.to_csv(CSV_PATH, mode="a", index=False, header=header)  # header only on first write [web:265][web:271]

def last_n_days(df: pd.DataFrame, n:int=7) -> pd.DataFrame:
    if df.empty:
        return df
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=n)
    return df[df["timestamp"] >= cutoff]

def compute_streak(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    date_series = pd.to_datetime(df["timestamp"]).dt.date
    dates = pd.Series(date_series).sort_values(ascending=False).unique()
    streak = 0
    day_cursor = dt.date.today()
    for d in dates:
        if d == day_cursor:
            streak += 1
            day_cursor = day_cursor - dt.timedelta(days=1)
        elif d < day_cursor:
            break
    return streak

# ---------- Sidebar ----------
with st.sidebar:
    st.header("Settings")
    simple = st.toggle("Simple tips only", value=True)  # [web:269]
    focus = st.selectbox("Today's focus", ["General","Sleep","Study","Anxiety"])
    if st.button("Clear history"):
        if CSV_PATH.exists():
            CSV_PATH.unlink(missing_ok=True)
        st.toast("History cleared.", icon="🧹")  # immediate feedback [web:259]

# ---------- Header cards ----------
st.markdown(
    f"""
    <div style="padding:18px;border-radius:14px;background:{SURFACE};border:1px solid #1f2937;">
      <h2 style="margin:0;color:{TEXT_LIGHT};">Mentis — Mental Health Companion</h2>
      <p style="margin:6px 0 0;color:{TEXT_MUTED};">Caring, private, non‑clinical support for students — detect mood and try quick relaxation tips.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    f"""
    <div style="margin-top:14px;padding:14px;border-radius:10px;background:#0b3b2e;border:1px solid #14532d;">
      <b style="color:{OK_GREEN};">Important:</b> This is not medical advice or therapy. If there is risk of harm or a crisis, contact a professional or local helpline immediately.
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------- Check-in ----------
st.subheader("How are things today?")

# Single‑tap chips set the slider quickly [web:272]
st.write("Quick check‑in:")
chip_cols = st.columns(5)
labels = [("Very low",-3),("Low",-1),("OK",0),("Good",1),("Great",3)]
for (lbl,val), c in zip(labels, chip_cols):
    if c.button(lbl, use_container_width=True):
        st.session_state["mood_slider"] = val
        st.toast(f"Set mood to {val}.", icon="✅")  # [web:259]

mood_label = st.session_state.get("mood_slider", 0)
mood_label = st.select_slider("Mood", options=[-3,-2,-1,0,1,2,3], value=mood_label, help="Negative to positive")

note = st.text_input("Optional note", "")
energy_pct = int((mood_label + 3) / 6 * 100)
st.progress(energy_pct, text=f"Daily energy: {energy_pct}%")  # progress affordance [web:266]

# Save button with toast [web:259]
if st.button("Save check‑in"):
    append_entry(mood_label, focus, note)
    st.toast("Saved check‑in.", icon="💾")

# ---------- Show recent history above chart ----------
df = load_history()
streak = compute_streak(df)
st.caption(f"Streak: {streak} day(s) in a row.")

recent = df.tail(5)[["timestamp","score","focus"]]
if not recent.empty:
    st.dataframe(recent, hide_index=True, use_container_width=True)

# 7‑day trend chart [web:264]
last7 = last_n_days(df, 7)
if not last7.empty:
    daily = last7.set_index("timestamp").resample("1D")["score"].mean().fillna(0)
    st.line_chart(daily)
else:
    st.info("No history yet — save a check‑in to see trends.")

# ---------- Free‑text feeling → response (lightweight, transparent) ----------
st.subheader("Describe your feelings")
user_text = st.text_area(
    "Write a sentence or two about today.",
    placeholder="E.g., I'm anxious about an exam and slept late.",
    height=100
)

def analyze_text(txt: str):
    txt_l = txt.lower()
    negatives = ["tired","exhausted","sad","down","anxious","stressed","overwhelmed","angry","worried","panic","lonely"]
    positives = ["happy","excited","grateful","good","proud","calm","relaxed","hopeful","energized"]
    study_kw = ["exam","study","assignment","project","deadline","homework","class"]
    sleep_kw = ["sleep","insomnia","tired","awake","nap","rest"]
    anxiety_kw = ["anxiety","anxious","panic","worry","overthink","overwhelmed","nervous"]

    score = 0
    score += sum(1 for w in positives if w in txt_l)
    score -= sum(1 for w in negatives if w in txt_l)
    score = max(-3, min(3, score))

    inferred_focus = "General"
    if any(k in txt_l for k in anxiety_kw): inferred_focus = "Anxiety"
    elif any(k in txt_l for k in sleep_kw): inferred_focus = "Sleep"
    elif any(k in txt_l for k in study_kw): inferred_focus = "Study"
    return score, inferred_focus

def craft_reply(score: int, focus: str):
    openers = {
        -3: "That sounds really heavy, and it makes sense to feel weighed down by that.",
        -2: "Thanks for sharing—there’s a lot on the plate and it can stack up quickly.",
        -1: "Noting that dip is a good first step; small steps can still help today.",
         0: "Thanks for checking in—staying aware is a strong habit.",
         1: "Great to hear a bit of lift—let’s channel it into one helpful action.",
         2: "Nice momentum—locking in one or two wins can compound.",
         3: "Love the energy—let’s direct it where it matters most."
    }
    suggestions = {
        "General": [
            "Micro‑reset: 1‑minute slow breathing, then one tiny task.",
            "Two‑minute tidy or 3‑email inbox sweep.",
        ],
        "Anxiety": [
            "Box breathing 4‑4‑4‑4 for 60–120 seconds.",
            "Write 3 worries → 1 next action.",
        ],
        "Sleep": [
            "No screens 30 minutes before bed; dim lights.",
            "Warm shower and consistent wake time.",
        ],
        "Study": [
            "Set a 25‑minute focus timer and write a 3‑bullet outline.",
            "Close extra tabs; keep just the doc and one reference.",
        ],
    }
    body = openers.get(score, openers[0])
    tips = suggestions.get(focus, suggestions["General"])
    return body, (tips[:1] if st.session_state.get("simple", True) else tips)

if st.button("Get response", type="primary"):
    if not user_text.strip():
        st.warning("Write a sentence or two first.")
    else:
        score_from_text, inferred_focus = analyze_text(user_text)
        body, tips = craft_reply(score_from_text, inferred_focus)
        st.success(f"{body} Focus today: {inferred_focus}.")
        for t in tips:
            st.write(f"• {t}")
        append_entry(score_from_text, inferred_focus, user_text.strip())
        st.toast("Saved from text analysis.", icon="💬")
