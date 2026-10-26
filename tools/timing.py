#!/usr/bin/env python3
"""投稿を何秒待ってから出すかを決めて出力する（GitHub Actions の「投稿時間」ステップで使う）。

朝・昼・夜それぞれで、用意してから 0〜20 / 20〜40 / 40〜60 / 60〜80 分後のどの枠が一番見られたかを
state/insights_log.json の閲覧数から比べ、良い枠を多めに選ぶ（まだ試していない枠も時々試す）。
"""
import glob, json, os, random
from datetime import datetime, timezone, timedelta

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
JST = timezone(timedelta(hours=9))
BUCKETS = [0, 20, 40, 60]  # 分


def made_at(qid):
    return datetime.strptime(qid[:13], '%Y%m%d-%H%M').replace(tzinfo=JST)


def main():
    pending = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'queue', '*.json'))):
        qid = os.path.splitext(os.path.basename(f))[0]
        if not os.path.exists(os.path.join(ROOT, 'state', 'posted', qid + '.json')):
            pending.append(qid)
    if not pending:
        # コメント返信（queue/replies/）だけのときは待たずにすぐ出す
        print(0)
        return
    qid = pending[-1]
    # コメント返信の push が、まだ記録の付いていない投稿と同じ時間帯に重なったときも待たない
    # （返信が後から足されたなら、その投稿は前の実行で出ている）
    reps = [os.path.basename(f)[:13] for f in glob.glob(os.path.join(ROOT, 'queue', 'replies', '*.json'))
            if not os.path.exists(os.path.join(ROOT, 'state', 'replied', os.path.splitext(os.path.basename(f))[0] + '.json'))]
    if reps and max(reps) > qid[:13]:
        print(0)
        return
    slot = qid.rsplit('-', 1)[-1]

    # 投稿ごとの最新の閲覧数
    views = {}
    log_p = os.path.join(ROOT, 'state', 'insights_log.json')
    if os.path.exists(log_p):
        for day, d in sorted(json.load(open(log_p, encoding='utf-8')).items()):
            for pid, m in d.get('posts', {}).items():
                if isinstance(m.get('views'), (int, float)):
                    views[pid] = m['views']

    samples = {b: [] for b in BUCKETS}
    for f in glob.glob(os.path.join(ROOT, 'state', 'posted', f'*-{slot}.json')):
        rec = json.load(open(f, encoding='utf-8'))
        pid = rec.get('id', '')
        if pid not in views or not rec.get('at'):
            continue
        try:
            wait = (datetime.fromisoformat(rec['at']) - made_at(pid)).total_seconds() / 60
        except ValueError:
            continue
        b = max([x for x in BUCKETS if x <= max(wait, 0)] or [0])
        samples[b].append(views[pid])

    rare = [b for b in BUCKETS if len(samples[b]) < 2]
    if rare:
        b = random.choice(rare)  # まだ数字が足りない枠を先に試す
    elif random.random() < 0.2:
        b = random.choice(BUCKETS)  # 時々ほかの枠も試す
    else:
        b = max(BUCKETS, key=lambda x: sum(samples[x]) / len(samples[x]))
    # 古すぎる投稿は publish.py が見送るので、用意から2時間半を超えないようにする
    left = 150 * 60 - (datetime.now(JST) - made_at(qid)).total_seconds()
    if slot == 'late':
        # 深夜のつぶやきは 0:30 までに出す
        m = made_at(qid)
        end = (m + timedelta(days=1 if m.hour >= 12 else 0)).replace(hour=0, minute=30, second=0)
        left = min(left, (end - datetime.now(JST)).total_seconds())
    sec = int(min(b * 60 + random.randint(0, 1199), max(left, 0)))
    print(f'::notice::{slot} は {b}〜{b + 20}分の枠で投稿（{sec // 60}分待つ）', flush=True)
    print(sec)


if __name__ == '__main__':
    main()
