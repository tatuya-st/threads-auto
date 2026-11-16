#!/usr/bin/env python3
"""京が答える前・動く前に、かならず読むものを1回で出す（11/16 マスター命令・楓OK）。

使い方: python3 tools/kyo_check.py

出すもの:
- 合図ページ（state/to_rei.txt）の最後40行
- 作戦ノート（state/board.txt）の先頭20行
- 町の連絡置き場（state/to_machi.txt）の最後20行
- state/machi-persona-*.md の要点（先頭15行）
- 京が出した相談・提案で、そのあと楓姉さんの「OK」がまだ来ていないもの
"""
import glob, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(path):
    try:
        with open(os.path.join(ROOT, path), encoding='utf-8') as f:
            return f.read().splitlines()
    except OSError:
        return None


def show(title, lines):
    print(f'===== {title} =====')
    if lines is None:
        print('（ファイルなし）')
    else:
        print('\n'.join(lines))
    print()


def entries(lines):
    """「・M/D だれから（種別）：本文」の1件ずつに分ける"""
    out = []
    for ln in lines:
        if ln.startswith('・'):
            out.append(ln)
        elif out and ln.strip():
            out[-1] += '\n' + ln
    return out


def pending(lines):
    """最後に楓姉さんが OK を出した後の、京の相談・提案（OK待ち）"""
    es = entries(lines)
    last_ok = -1
    for i, e in enumerate(es):
        head = e[:40]
        if '楓から' in head and re.search(r'OK|ＯＫ|了解|承認', e):
            last_ok = i
    res = []
    for e in es[last_ok + 1:]:
        head = e.split('：', 1)[0]
        if '京から' in head and re.search(r'相談|提案|依頼', head):
            res.append(e.splitlines()[0][:160])
    return res


def main():
    rei = read('state/to_rei.txt')
    show('合図ページ（最後40行）', rei[-40:] if rei else rei)
    b = read('state/board.txt')
    show('作戦ノート（先頭20行）', b[:20] if b else b)
    m = read('state/to_machi.txt')
    show('町の連絡置き場（最後20行）', m[-20:] if m else m)
    for p in sorted(glob.glob(os.path.join(ROOT, 'state', 'machi-persona-*.md'))):
        rel = os.path.relpath(p, ROOT)
        ls = read(rel)
        show(f'{rel}（先頭15行）', ls[:15] if ls else ls)
    print('===== 楓姉さんのOK待ち（OKが出るまで手を付けない） =====')
    pend = pending(rei or [])
    print('\n'.join(pend) if pend else 'なし')


if __name__ == '__main__':
    main()
