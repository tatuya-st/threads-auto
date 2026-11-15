# 共有データ置き場（楓⇔京）

マスター指示（2026-11-15）で新設。今までの数字は全てここに集約し、グラフは `state/data-dashboard.md` で共有する。

## ファイル一覧
- `kpi_snapshots.csv`：フォロワー・いいね等の時点スナップショット（日時・出典つき）
- `threads_posts.csv`：Threads投稿ごとの表示・いいね・返信（insights_logの最新値）
- `instagram_posts.csv`：Instagram投稿ごとの表示・リーチ・いいね等（ig_insights自動収集。直近12件のみ）
- `a8_programs.csv`：A8の案件別クリック・発生・EPC・確定率・提携状態
- `rakuten_results.csv`：楽天アフィリエイトの成果（件数・売上・報酬）
- `reels_experiment.csv`：リール実験4本の24時間値と最新値
- `business_calendar.csv`：商戦と投稿予定のカレンダー

## 更新ルール
1. 数字は確認したものだけ書く。未確認は空欄か「未確認」と明記し、推測で埋めない。
2. 1行ごとに必ず出典（取得面・日時）を付ける。取得面が違う数字は混ぜない（例：Threadsフォロワーは accounts 取得値同士でのみ比較する。Instagramの「再生数」スクショ値と ig_insights の views は別定義なので別に扱う）。
3. 楓の担当：定時調査のたびに KPI と各CSVを更新し、`state/data-dashboard.md` のグラフも追随させる。
4. 京の担当：自分の投稿（夜の商品投稿・ROOM）の数字と、A8の投稿後48時間クリック確認結果を追記する。週の数字は金曜夜までにここへ揃える（役員会議の提出はこの置き場で代替する）。
5. 変更したら合図ページ（state/to_rei.txt）で相手に1行知らせる。
