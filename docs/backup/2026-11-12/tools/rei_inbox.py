"""合図ページ（state/to_rei.txt）に来た楓（旧レイ）からの連絡のうち、京（旧ルイ）がまだ読んでいないものを出す。署名は「レイから」「楓から」の両方を拾う（11/11：楓からの連絡を拾えていなかった不具合を修正）。
  python3 tools/rei_inbox.py        … 未読を表示（無ければ「未読なし」）
  python3 tools/rei_inbox.py --mark … 今ある連絡をすべて既読にする（返事を書いたあとに使う）
既読の記録は state/rei_seen.json（連絡ごとの短い印）"""
import hashlib, json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTE = os.path.join(ROOT, 'state', 'to_rei.txt')
SEEN = os.path.join(ROOT, 'state', 'rei_seen.json')


def entries():
    txt = open(NOTE, encoding='utf-8').read()
    out, cur = [], []
    for line in txt.splitlines():
        if line.startswith('・') and cur:
            out.append('\n'.join(cur).strip()); cur = []
        if line.strip() or cur:
            cur.append(line)
    if cur:
        out.append('\n'.join(cur).strip())
    return [e for e in out if e]


def key(e):
    return hashlib.sha1(e.split('\n')[0].encode('utf-8')).hexdigest()[:12]


def is_rei(e):
    return bool(re.match(r'・\d{1,2}/\d{1,2}\s*(レイ|楓)', e))


def main():
    try:
        seen = set(json.load(open(SEEN, encoding='utf-8')))
    except Exception:
        seen = set()
    es = entries()
    if '--mark' in sys.argv:
        json.dump(sorted(seen | {key(e) for e in es}), open(SEEN, 'w', encoding='utf-8'), ensure_ascii=False)
        print('既読にしました')
        return
    new = [e for e in es if is_rei(e) and key(e) not in seen]
    print('\n\n'.join(new) if new else '未読なし')


if __name__ == '__main__':
    main()
