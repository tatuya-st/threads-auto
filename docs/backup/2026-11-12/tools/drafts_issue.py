#!/usr/bin/env python3
"""state/drafts.json（ルイが書いたコメント返信の下書き）を GitHub の Issue にして、スマホの GitHub アプリに届ける。"""
import json, os, subprocess

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')


def gh(*args):
    return subprocess.run(['gh', *args], capture_output=True, text=True)


def main():
    p = os.path.join(ROOT, 'state', 'drafts.json')
    if not os.path.exists(p):
        return
    d = json.load(open(p, encoding='utf-8'))
    items = d.get('items', [])
    gh('label', 'create', 'comments', '--color', '0e8a16', '--description', 'コメント返信の下書き', '--force')
    # 前日までの下書きは閉じる（一覧を今日の分だけにする）
    old = gh('issue', 'list', '--label', 'comments', '--state', 'open', '--json', 'number', '--jq', '.[].number').stdout.split()
    for n in old:
        gh('issue', 'close', n)
    if not items:
        return
    # pri: reply（本人が返す）・auto（ルイが自動で返信済み）・like（いいねだけ）。pri なしは本人が返す扱い
    rep = [it for it in items if it.get('pri', 'reply') == 'reply']
    aut = [it for it in items if it.get('pri') == 'auto']
    lik = [it for it in items if it.get('pri') == 'like']
    lines = []
    if rep:
        lines += [f"@tatuya-st あなたが返したいコメントが{len(rep)}件あります。下書きをコピーして、Threadsで返信してください。", '']
    else:
        lines += ['今日はあなたが返すコメントはありません（ルイが返信済み・いいねだけ）。', '']
    for i, it in enumerate(rep, 1):
        # Threadsの名前に @ を付けると同じ名前の GitHub ユーザーに通知が飛ぶので付けない
        lines += [f"### ★{i}. {it.get('user', '').lstrip('★')} さん", '', '> ' + it.get('text', '').replace('\n', '\n> '), '',
                  '下書き：', '```', it.get('draft', ''), '```', f"[コメントを開く]({it.get('link', '')})", '']
    if aut:
        lines += ['---', '#### ✅ ルイが自動で返信しました', '']
        for it in aut:
            lines.append(f"- {it.get('user', '').lstrip('✅')} さん：{it.get('text', '')[:40]} → {it.get('draft', '').replace('✅ ルイが返信しました：', '')}　[開く]({it.get('link', '')})")
        lines.append('')
    if lik:
        lines += ['---', '#### 👍 いいねだけでOK', '']
        for it in lik:
            lines.append(f"- {it.get('user', '')} さん：{it.get('text', '')[:40]}　[開く]({it.get('link', '')})")
    parts = [f"★あなたが返す {len(rep)}件" if rep else '', f"✅自動で返信 {len(aut)}件" if aut else '', f"👍いいねだけ {len(lik)}件" if lik else '']
    title = "💬 " + '・'.join(x for x in parts if x) + f"（{d.get('date', '')}）"
    r = gh('issue', 'create', '--title', title, '--label', 'comments', '--body', '\n'.join(lines))
    print(r.stdout or r.stderr)


if __name__ == '__main__':
    main()
