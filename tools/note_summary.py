"""投稿ノートに出す「Threadsの反応」のまとめを作る。
state/insights.json・state/insights_log.json・state/posted・queue を読み、
ArtifactData に書き込む1つの JSON を標準出力に出す（文章は書き写さず、書き出し40字だけ）。
使い方: python3 tools/note_summary.py > summary.json
"""
import glob
import json
import os
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
SLOT = {"morning": "朝", "noon": "昼", "night": "夜", "late": "深夜"}


def load(p, default):
    try:
        with open(p, encoding="utf8") as f:
            return json.load(f)
    except Exception:
        return default


def head(text):
    for line in (text or "").splitlines():
        s = line.strip()
        if s and not s.startswith("※"):
            return s[:40]
    return ""


def main():
    ins = load("state/insights.json", {})
    log = load("state/insights_log.json", {})
    posts = ins.get("posts", {})
    now = datetime.now(JST)
    since = (now - timedelta(days=7)).strftime("%Y%m%d")

    rows = []
    for pid, m in posts.items():
        parts = pid.split("-")
        if len(parts) < 3:
            continue
        day, hm, slot = parts[0], parts[1], parts[2]
        q = load(f"queue/{pid}.json", {})
        pz = load(f"state/posted/{pid}.json", {})
        rows.append({
            "id": pid,
            "day": day,
            "label": f"{int(day[4:6])}/{int(day[6:8])} {SLOT.get(slot, slot)}",
            "slot": slot,
            "head": head(q.get("text")),
            "views": int(m.get("views") or 0),
            "likes": int(m.get("likes") or 0),
            "replies": int(m.get("replies") or 0),
            "reposts": int(m.get("reposts") or 0),
            "link": pz.get("permalink") or "",
        })
    rows.sort(key=lambda r: r["id"])
    week = [r for r in rows if r["day"] >= since]

    slots = {}
    for k in SLOT:
        rs = [r for r in week if r["slot"] == k]
        if rs:
            slots[k] = {
                "name": SLOT[k],
                "n": len(rs),
                "views": round(sum(r["views"] for r in rs) / len(rs)),
                "likes": round(sum(r["likes"] for r in rs) / len(rs), 1),
                "replies": round(sum(r["replies"] for r in rs) / len(rs), 1),
            }

    days = sorted(log.keys())[-14:]
    daily = [{
        "d": f"{int(d[5:7])}/{int(d[8:10])}",
        "views": int((log[d].get("account") or {}).get("views") or 0),
        "followers": int((log[d].get("account") or {}).get("followers_count") or 0),
    } for d in days]

    acc = ins.get("account") or {}
    fol = int(acc.get("followers_count") or 0)
    base = daily[-8]["followers"] if len(daily) >= 8 else (daily[0]["followers"] if daily else fol)

    out = {
        "id": "summary",
        "at": ins.get("at", ""),
        "followers": fol,
        "followersDelta": fol - base if base else 0,
        "week": {
            "posts": len(week),
            "views": sum(r["views"] for r in week),
            "likes": sum(r["likes"] for r in week),
            "replies": sum(r["replies"] for r in week),
        },
        "slots": slots,
        "top": sorted(week, key=lambda r: (r["views"], r["likes"]), reverse=True)[:3],
        "recent": list(reversed(rows))[:8],
        "daily": daily,
        "updatedAt": int(now.timestamp() * 1000),
    }
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    main()
