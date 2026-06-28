#!/usr/bin/env python3
"""Kīlauea episodic-eruption watcher.
Pulls the latest HVO daily update from the public USGS HANS API, reads the
UWD tiltmeter recharge, predicts the next fountaining episode, and emails you.
No paid services, no API key. Runs headless on a schedule (see watch.yml)."""

import os, re, json, ssl, smtplib, urllib.request, urllib.parse
from datetime import datetime, date, timedelta
from email.message import EmailMessage

UA = {"User-Agent": "kilauea-watch/1.0 (personal eruption monitor)"}
THRESH_FALLBACK = 15.5      # µrad needed to re-trigger, if HVO hasn't stated it
PATTERN_DAYS = 13           # recent-average pause, used until tilt data arrives
STATE = "state.json"
API = "https://volcanoes.usgs.gov/hans-public/api/notice"


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def newest_daily():
    """Return (notice_date, full_text) of the newest Kīlauea update carrying tilt data."""
    raw = get(f"{API}/recent/hvo/7")
    ids = sorted(set(re.findall(r"DOI-USGS-HVO-\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00", raw)), reverse=True)
    for nid in ids[:15]:
        for variant in (nid, urllib.parse.quote(nid, safe="")):
            try:
                t = get(f"{API}/getNoticeFormatted/{variant}/text")
            except Exception:
                continue
            if "KILAUEA" in t.upper() and "microradian" in t.lower():
                return re.search(r"HVO-(\d{4}-\d{2}-\d{2})T", nid).group(1), t
    raise RuntimeError("No recent Kīlauea daily update with tilt data found")


def fnum(pat, t, default=None):
    m = re.search(pat, t, re.I)
    return float(m.group(1)) if m else default


def parse(t):
    low = t.lower()
    em = re.search(r"episode\s+(\d+)\s+of the ongoing", t, re.I)
    dm = re.search(r"ended.*?on\s+([A-Z][a-z]+\s+\d{1,2},\s+\d{4})", t)
    end = None
    if dm:
        try:
            end = datetime.strptime(dm.group(1), "%B %d, %Y").date().isoformat()
        except ValueError:
            pass
    am = re.search(r"Volcano Alert Level:\s*([A-Z]+)", t, re.I)
    fm = re.search(r"between\s+(.+?)\s+with\s+(.+?)\s+most likely", t, re.I)
    return {
        "recovered": fnum(r"recovered\s+([\d.]+)\s+microradian", t, 0.0),
        "deflation": fnum(r"deflation\s+totaled\s+([\d.]+)\s+microradian", t),
        "episode": int(em.group(1)) if em else None,
        "end": end,
        "erupting": "paused" not in low,
        "alert": am.group(1).title() if am else None,
        "forecast": f"{fm.group(1).strip()} (most likely {fm.group(2).strip()})" if fm else None,
    }


def load_state():
    if os.path.exists(STATE):
        with open(STATE) as f:
            return json.load(f)
    return {"episode": None, "end": None, "deflation": None, "readings": []}


def predict(st):
    thr = st.get("deflation") or THRESH_FALLBACK
    r = {"thr": thr, "date": None, "pattern": None, "pct": 0.0,
         "rate": None, "days_left": None, "recovered": 0.0, "method": "pattern"}
    if not st.get("end"):
        return r
    end = date.fromisoformat(st["end"])
    r["pattern"] = end + timedelta(days=PATTERN_DAYS)
    if st["readings"]:
        last = st["readings"][-1]
        elapsed = (date.fromisoformat(last["date"]) - end).days
        r["recovered"] = last["recovered"]
        if last["recovered"] > 0.3 and elapsed > 0:
            rate = last["recovered"] / elapsed
            r.update(rate=rate, pct=min(100, last["recovered"] / thr * 100),
                     date=end + timedelta(days=thr / rate), method="tilt")
    if not r["date"]:
        r["date"] = r["pattern"]
        r["pct"] = min(100, r["recovered"] / thr * 100)
    r["days_left"] = max(0, (r["date"] - date.today()).days)
    return r


def build_body(st, p, nextep):
    bar = "█" * round(p["pct"] / 5) + "░" * (20 - round(p["pct"] / 5))
    d = p["date"].strftime("%A, %B %d, %Y") if p["date"] else "unknown"
    method = {"tilt": "Live UWD tilt recharge", "pattern": "Recent-pattern estimate (awaiting tilt data)"}[p["method"]]
    lines = [
        f"KĪLAUEA EPISODE {nextep} — RECHARGE WATCH",
        "",
        f"Predicted onset:  {d}",
        f"Recharge:         [{bar}] {round(p['pct'])}%",
        f"Method:           {method}",
        "",
        f"Tilt recovered:   {p['recovered']:.1f} µrad",
        f"Threshold:        {p['thr']:.1f} µrad (Episode {st.get('episode') or '?'} deflation)",
        f"Recharge rate:    {p['rate']:.2f} µrad/day" if p["rate"] else "Recharge rate:    pending",
        f"Days remaining:   {p['days_left']}",
        "",
        f"Status:           {'FOUNTAINING NOW' if st.get('erupting') else 'Paused / recharging'}  ·  Alert {st.get('alert') or '—'}",
    ]
    if st.get("forecast"):
        lines.append(f"HVO official window: {st['forecast']}")
    lines += [
        "",
        "How this works: each eruption drops the summit by a set amount of tilt;",
        "it then re-inflates ~1 µrad/day until it refills and fountains again.",
        "",
        "Source: USGS HVO daily update — https://www.usgs.gov/volcanoes/kilauea/volcano-updates",
        "This is a statistical aid. HVO's official forecast is authoritative.",
    ]
    return "\n".join(lines)


def send(st, p):
    user, pw = os.environ["SMTP_USER"], os.environ["SMTP_PASS"]
    to = os.environ.get("MAIL_TO", user)
    ep = st.get("episode") or "?"
    nextep = (st["episode"] + 1) if st.get("episode") else "next"
    when = p["date"].strftime("%b %d") if p["date"] else "?"
    pct = round(p["pct"])
    if st.get("erupting"):
        subj = f"🌋 Kīlauea Episode {ep} is fountaining now"
    elif (p["days_left"] is not None and p["days_left"] <= 2) or pct >= 85:
        subj = f"⚠️ Kīlauea Episode {nextep} likely ~{when} ({pct}% charged)"
    else:
        subj = f"Kīlauea watch · Episode {nextep} ~ {when} ({pct}% charged)"
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = user, to, subj
    msg.set_content(build_body(st, p, nextep))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(user, pw)
        s.send_message(msg)
    print("Sent:", subj)


def main():
    rdate, text = newest_daily()
    p = parse(text)
    st = load_state()
    if p["episode"] and st.get("episode") and p["episode"] > st["episode"]:
        st["readings"] = []  # new eruption cycle → reset curve
    st["episode"] = p["episode"] or st.get("episode")
    st["end"] = p["end"] or st.get("end")
    st["deflation"] = p["deflation"] or st.get("deflation") or THRESH_FALLBACK
    st["alert"], st["erupting"], st["forecast"] = p["alert"], p["erupting"], p["forecast"]
    if not p["erupting"] and st["end"]:
        st["readings"] = sorted(
            [r for r in st["readings"] if r["date"] != rdate] + [{"date": rdate, "recovered": p["recovered"]}],
            key=lambda r: r["date"])
    pred = predict(st)
    with open(STATE, "w") as f:
        json.dump(st, f, indent=2)
    send(st, pred)


if __name__ == "__main__":
    main()
