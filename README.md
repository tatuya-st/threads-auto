# Threads 自動投稿（ガジェット好きのT.S）

楽天ROOMに投稿した商品から3件を選び、画像つきのまとめ投稿をThreadsに自動で出します。

- queue/ … 投稿予定（Claudeが毎日2回用意）
- images/ … 投稿画像（自動で作成）
- state/ … 投稿済みの記録（二重投稿の防止）・暗号化したトークン
- index.html … 成績表（GitHub Pages: https://tatuya-st.github.io/threads-auto/）
- 毎日 19:23 コメント確認 → 夜にルイが返信の下書きを state/drafts.json に書く → Issue でスマホに届く
- 投稿時間は tools/timing.py が閲覧数から選ぶ（用意から0〜80分後）。失敗は Issue（alert）で通知
