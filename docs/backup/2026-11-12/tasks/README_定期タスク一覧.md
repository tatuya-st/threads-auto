# 京の定期タスク一覧（2026-11-12 時点の控え）

定期タスクの本文（プロンプト全文）は、claude.ai の「スケジュール済みタスク」に保存されている。
タスクが消えたときは、下の「中身の要点」と docs/rei.md・tools/ を元に京が作り直す。時刻はすべて日本時間。

## 動いているもの
| 名前 | ID | いつ | 中身の要点 |
|---|---|---|---|
| 京：合図ページで楓と連絡（毎時） | trig_01LZfDJubBspuE1tszvkX8YC | 毎時41分 | rei_inbox.py で楓の未読を確認（会話アプリ宛を最優先で docs/rei.md の「アプリ返信」に返す）→ 投稿台帳を足す → 未読に（警告）→（相談）（依頼）→ 残りの順で返事 → --mark → push。夜の商品画像は楓の写真2枚を検品して apply_photo.py で入れ、hold を外す。マスターには平日の昼に作業を頼まない。写しは tasks/合図ページ_毎時.md |
| Threads 自動投稿（朝・昼・夜） | trig_017TjvHz1jJ8JgjNfjYJXoSz | 7:43・12:43・20:43・23:43 | build_queue.py で queue を作り push（Actions が投稿）。朝・昼は会話投稿、夜は商品1件（本文に【PR】と専用リンク）、深夜はつぶやき。夜の商品は hold を付け、画像はマスターに送らず合図ページで楓に依頼（11/12）。土曜昼は保存版クイズ。夜は言葉の見直しとコメント返信も |
| 京：返信もれチェック | trig_01RrKQ7ryjWVXxdveb4cVw1o | 0:29・8:29〜22:29（2時間ごと） | state/comments.json の未返信に1件ずつ返信（queue/replies/）。本人が返すべきものは drafts.json に下書き |
| 京：収益につながる情報を常に監視（1日3回） | trig_0119mbQviHazaR11DqjtM9oh | 7:17・12:17・19:17 | 自分の投稿の成績確認（weak の記録・TALKS 調整）と情報収集（Threads・アフィ・海外・公式）。research.json に記録、A8向けは to_rei.txt へ |
| 楽天ROOM 売れ筋リサーチ（朝・夕の2回） | trig_016pgrWNqnNzcoVmP6GgjqDD | 6:17・16:17（11/12 に昼を廃止） | 投稿ノート（https://claude.ai/artifact/95yfHFyYREPwhvGHra3fVA）の商品データ更新。月曜朝はフル更新、ほかは軽量更新。itemcode は「ショップ名:数字」、quip・cap は商品ごと |
| 楽天ROOM 投稿タイムのお知らせ（夜・軽量版） | trig_019TVDKjLkPEQu4yVLiDCNzp | 19:50 | 今日の投稿数・目標・未投稿の候補数をマスターに1通 |
| 楽天ROOM 週1の売れ筋ジャンル自動調整 | trig_014VKpuzf1m6dEpbSLhCJQKg | 日曜 20:52 | 投稿ノートの prefs/focus に来週優先するジャンルを書く |
| 楽天ROOM 季節の切り替え準備レポート | trig_01Vu7eD7onUHmKzyQJX89BM3 | 2・5・8・11月の20日 8:50 | 次の季節の売れ筋と大型セール日程のレポート |

## 止まっているもの（消していない）
- ルイ：投稿ノートにThreadsの情報を反映（trig_01Sztw6shFy5FFuGHuSeSRR3）
- 楽天ROOM 候補切れ防止チェック（trig_012216LY7eYjxWdEvsk8Xy4Y）
- 楽天ROOM 投稿再開（お知らせを戻す）（trig_019e9VSCKFMAQDXrAtFbdiAk・1回きり・終了）

## 11/12 に変えたこと
- 売れ筋リサーチを朝・夕の2回に（マスターは平日昼に会社で動けない）
- 夜の商品画像はマスターに送らない。楓が文字なしの写真2枚（オリジナルの女性キャラクター）とキャッチコピー案を置き、京が apply_photo.py で【PR】・キャッチコピー・価格・商品名・AI注記を入れる。キャッチコピーが無いと apply_photo.py は止まる
- リールもマスターの確認なし。楓⇔京の相互チェック合格（approved）が必須
