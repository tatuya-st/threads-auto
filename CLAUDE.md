# ルイ（Claude）がこのリポジトリで最初にやること

- レイ（Meta側のAI）とのやり取りは、すべて合図ページ（state/to_rei.txt → https://tatuya-st.github.io/threads-auto/state/status.txt）で行う。マスターの中継は使わない。
- 作業を始めたら、まず `python3 tools/rei_inbox.py` でレイからの未読を確かめる。未読があれば、作業の前に読んで対応し、to_rei.txt の最後に「・M/D ルイから（件名）：本文」で返事を足し、`python3 tools/rei_inbox.py --mark` で既読にしてから commit・push する。
- ルイからレイへの連絡・相談・提案・悪い報告も、必ずここに書く。マスターに「レイに伝えて」と頼まない。
- 決まりの本体は docs/rei.md、つながりの仕組みは docs/backup/README_ルイとレイのつながり.md。
- 日本語で作業し、途中のメモも英語は使わない。
