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
    lines = [f"@tatuya-st 返信待ちのコメントが{len(items)}件あります。下書きをコピーして、Threadsで返信してください。", '']
    for i, it in enumerate(items, 1):
        # Threadsの名前に @ を付けると同じ名前の GitHub ユーザーに通知が飛ぶので付けない
        lines += [f"### {i}. {it.get('user', '')} さん", '', '> ' + it.get('text', '').replace('\n', '\n> '), '',
                  '下書き：', '```', it.get('draft', ''), '```', f"[コメントを開く]({it.get('link', '')})", '']
    title = f"💬 返信待ちのコメント {len(items)}件（{d.get('date', '')}）"
    r = gh('issue', 'create', '--title', title, '--label', 'comments', '--body', '\n'.join(lines))
    print(r.stdout or r.stderr)


if __name__ == '__main__':
    main()
