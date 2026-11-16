# インスタを「Facebookログイン版」に広げる手順（2026-11-16 京）

目的：削除・コラボ・ハッシュタグ検索・他アカウント分析・商品タグ・ストーリーズのリンククリック数を使えるようにする（state/sns-freedom-map-2026-11-16.md の①②）。
自分のアカウントだけで使うので、Metaの審査（App Review）は不要（アプリの役割を持つ人のアカウントは標準アクセスで使える）。
今のインスタログイン版はそのまま残し、つながったら切り替える（失敗しても今の投稿・記録は止まらない）。

## マスターの手順（スマホとパソコン、合計15分ほど）
1. Facebookページをインスタにつなぐ（スマホ・5分）
   インスタのアプリ → プロフィール →「プロフィールを編集」→「ページ」（または「Facebookページ」）→ 既存のページを選ぶ、なければ「Facebookページを作成」。
   ※メニューの名前は端末で少し違うことがある。
2. 便利アプリに「Facebookログイン」を足す（パソコン・10分）※京の準備ができた合図のあと
   Meta for Developers → 便利アプリ →「製品を追加」→「Facebookログイン for Business」→ 設定の「有効なOAuthリダイレクトURI」に
   https://tatuya-st.github.io/threads-auto/callback.html を入れて保存。
   使う許可：instagram_basic・instagram_content_publish・instagram_manage_comments・instagram_manage_insights・pages_show_list・pages_read_engagement・business_management（一覧に instagram_manage_contents があれば足す）。
3. 京が合図で送る「許可のURL」を開いて「許可」を押し、出たコードを今までのインスタの許可と同じやり方で入れる。

## 京・楓の手順
- 京：tools/ig.py に Facebookログイン版の許可とトークン保存を足す（graph.facebook.com・ページ経由でインスタのIDを取る）。.github は変えず、今の ig_oauth の流れを使う。準備ができたら合図ページとマスターに知らせる。
- 楓：つながったら、削除・コラボ・ハッシュタグ検索を道具側の使い方と合わせて、京と2人で小さく試す。
- 試した結果を、楓の統合報告で1回にまとめてマスターへ。
