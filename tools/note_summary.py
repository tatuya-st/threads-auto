"""投稿ノートに出す「Threadsの反応」のまとめを作る。
state/insights.json・state/insights_log.json・state/posted・queue を読み、
ArtifactData に書き込む1つの JSON（反応・次の投稿・投稿待ち・最近の投稿文・コメント返信の下書き・画像の一覧） を標準出力に出す。
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

    # 次の投稿の予定（ルイは投稿の直前に文章を作るので、時間と形だけ）
    plan = [(7, 43, "morning", "朝：会話＋商品1件"), (12, 43, "noon", "昼：会話投稿"),
            (20, 43, "night", "夜：画像つきの投稿"), (23, 43, "late", "深夜：短いつぶやき")]
    nxt = None
    for add in (0, 1):
        base_day = (now + timedelta(days=add)).replace(second=0, microsecond=0)
        for h, mi, sk, lab in plan:
            t = base_day.replace(hour=h, minute=mi)
            if t > now:
                nxt = {"time": f"{t.month}/{t.day} {h}:{mi:02d}ごろ", "slot": sk, "label": lab}
                break
        if nxt:
            break

    # 投稿待ち（作られたがまだ投稿されていないもの）と、最後に投稿したもの
    def full(pid):
        q = load(f"queue/{pid}.json", {})
        pz = load(f"state/posted/{pid}.json", {})
        parts = pid.split("-")
        return {
            "id": pid,
            "label": f"{int(parts[0][4:6])}/{int(parts[0][6:8])} {SLOT.get(parts[2], parts[2])}" if len(parts) >= 3 else pid,
            "text": q.get("text", ""),
            "reply": q.get("reply", ""),
            "link": pz.get("permalink", ""),
            "image": os.path.exists(f"images/{pid}.png"),
        }

    qids = sorted(os.path.basename(f)[:-5] for f in glob.glob("queue/*.json"))
    posted = {os.path.basename(f)[:-5] for f in glob.glob("state/posted/*.json")}
    cutoff = (now - timedelta(hours=3)).strftime("%Y%m%d-%H%M")
    pending = [full(i) for i in qids if i not in posted and i >= cutoff][-2:]
    done = [i for i in qids if i in posted]
    last = [full(i) for i in done[-3:]][::-1]

    dr = load("state/drafts.json", {})
    drafts = {"date": dr.get("date", ""), "items": [
        {k: it.get(k, "") for k in ("user", "text", "draft", "link")} for it in (dr.get("items") or [])
    ][:20]}

    imgs = sorted(os.path.basename(f)[:-4] for f in glob.glob("images/*.png"))[-12:][::-1]

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
        "next": nxt,
        "pending": pending,
        "last": last,
        "drafts": drafts,
        "images": imgs,
        "updatedAt": int(now.timestamp() * 1000),
    }
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    main()
