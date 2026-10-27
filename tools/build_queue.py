#!/usr/bin/env python3
"""投稿ノートのデータから、Threads のまとめ投稿（3件・画像つき）を1本作って queue/ に置く。

使い方:
  python3 tools/build_queue.py --html <投稿ノートの保存HTML> --posts <posts を保存したフォルダ> --repo <このリポジトリ> --slot morning|noon|night|late [--form 形]

- ROOM に投稿済み（posts）の商品から選ぶ。Threads に一度出した商品（state/sent.json）は二度と選ばない。
- 投稿ノートの「まとめてThreadsへ」と同じ考え方：ROOMで反応が確かめられた商品 → 1万円以下のガジェット・家電 → 1万円以下 → 3万円以下 → それ以外。
- 何も選べないときは何も作らず「なし」と出力する。
"""
import argparse, glob, json, os, re, sys, time, unicodedata
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
ROOM_URL = 'https://room.rakuten.co.jp/room_a9a129c5a9/items'
ROOM_COLS_URL = 'https://room.rakuten.co.jp/room_a9a129c5a9/collections'
LOOKBACK_DAYS = 14
PER_POST = 3

THEMES = {
    'apple': dict(re=re.compile(r'iPhone|Apple|MagSafe|Lightning|AirPods|アイフォン|アップル', re.I), name_only=False,
        title=['「残り5%」の恐怖、撲滅', 'ケーブル「あと10cm」問題', '純正は高い。でも妥協しない'],
        open=lambda n: [f'充電ケーブル、なぜか毎回「あと10cm」足りない問題。\niPhone民のための{n}選🔌', f'iPhoneの「残り5%」表示、\n見るたびに心拍数も上がる説。\n対策グッズ{n}つ👇', f'Apple製品は好き。\n純正の値段は…ちょっと考えたい。\nそんな人向けの{n}選🍎', f'ベッドで寝ながらスマホ、\n首だけ別の生き物になってました。\niPhoneまわり{n}選🔌'],
        ask=['充電、いつも何%で焦り始めますか？👇', 'ケーブル、家に何本あるか数えたことあります？👇', 'iPhoneまわりで一番困ってること、リプで教えてください👇']),
    'winter': dict(re=re.compile(r'ヒーター|毛布|暖房|こたつ|ストーブ|加湿|あったか|防寒|ブランケット|湯たんぽ|ひざ掛け|ひざかけ|ぬくぬく'), name_only=False,
        title=['布団から出る勇気、補助します', '脱衣所の修行、もうやめます', '「寒っ」禁止令、発令'],
        open=lambda n: [f'朝の脱衣所、もはや修行🥶\n冬支度{n}選です', f'布団から出るのに、毎朝3回の決意が必要な季節になりました。\n冬支度{n}つ👇', f'暖房のスイッチを押すか、まだ我慢するか。\n毎年この時期の小さな戦いに、{n}つの援軍を🔥', f'「寒っ」が口ぐせになる前に。\n冬支度{n}選です🧣'],
        ask=['家の中で一番寒い場所、どこですか？👇', '暖房、もうつけました？まだ我慢派？👇', '冬の朝、布団から出るまで何分かかります？👇']),
    'refill': dict(re=re.compile(r'詰め替え|つめかえ|詰替|レフィル|ストック|まとめ買い|\d+個入|\d+個組|[×x]\s*\d+(?![\d.]|\s*(?:cm|mm|ｃｍ|センチ))|\d+ロール|\d+袋|\d+(?:\.\d+)?kg'), name_only=True,
        title=['詰め替え地獄からの脱出', '「あっ、もう無い」撲滅', '床を汚さない詰め替え生活'],
        open=lambda n: [f'詰め替えるたびに床が大惨事の人、手を挙げて🙋‍♂️\n私です。\n\n今日はストック系{n}選', f'「あっ、もう無い」って言う回数、\n年間で数えたら怖いので数えてません。\nストック候補{n}つ👇', f'ボトルを逆さにして振る儀式、そろそろ卒業したい。\n詰め替え・ストック{n}選', f'玄関に重い荷物が届く幸せ（運ぶのは配達の方）。\nストック{n}選です📦'],
        ask=['あなたの家で一番早く無くなるもの、なんですか？👇', '詰め替え、こぼさない派？こぼす派？👇', '買い忘れて一番困ったもの、リプで教えてください😂']),
    'tabi': dict(re=re.compile(r'御朱印|お守り|ナザール|神社|ラーメン|旅行|トラベル|ネックピロー|夜行バス'), name_only=False,
        title=['物欲と神頼みの両立', '弾丸旅の装備会議', '神頼み、準備は万全'],
        open=lambda n: [f'物欲と神頼みで生きてる男の\n今日の{n}選です⛩️', f'休みの日は弾丸で神社巡り。\n荷物は少なく、ご利益は多めに。\n旅の相棒{n}つ👇', f'お守りは増える一方、\nラーメンの替え玉も増える一方。\nそんな男の{n}選です🍜', f'御朱印帳が埋まるたび、\n次の旅先を考え始める病です。\n今日の{n}選⛩️'],
        ask=['最近行った神社やおすすめのラーメン、リプで教えてください👇', 'お守り、何個持ってます？👇', '旅先でつい買っちゃう物、なんですか？😂']),
    'base': dict(re=None, name_only=False,
        title=['財布「やめて」私「見るだけ」', '物欲、フル充電完了', 'ポチる前の作戦会議', 'カート反復横跳びの成果'],
        open=lambda n: [f'財布「やめて」\n私「見るだけだから」\n\n…という言い訳つきの{n}選です👇', f'ランキングを見すぎて、楽天ポイントが夢に出てきた男の{n}選です', f'物欲のみなさん、お疲れさまです。\n本日の議題は{n}件。異議なしで可決されそうです🫡', f'「何も買わない日」を作ろうとした結果、\n気になるものが{n}つ増えました🔍', f'カートに入れては消す反復横跳び、今日も元気にやってます。\n本日の候補{n}つ👇', f'寝る前の楽天パトロール、本日の成果{n}件です🌙', f'「今月は節約する」と言ってから、今日で3週間。\n言うだけなら無料なので、今日も言います。\n本日の{n}選👇', f'楽天のお気に入り、そろそろ倉庫が必要な量になってきました。\nその中から厳選{n}件です📦'],
        ask=['あなたなら何番？番号だけのリプでも喜びます👇', '「うちもそれ困ってる」って人はリプで教えてください😂', 'この中で一番気になるの、何番ですか？👇', 'カートに入れたまま一番長く寝かせてる物、なんですか？😂', '「これは買ってよかった」ってもの、ひとつだけ教えてください👇']),
}
NOON_OPEN = lambda n: [f'お昼休みのみなさん、おつかれさまです。\nごはんのお供に物欲会議、議題は{n}件です🍙', f'昼休み、スマホ片手に楽天パトロールした成果{n}件です🥪', f'午後もがんばるためのご褒美候補{n}つ。\n買うのは仕事が終わってからでOK☕']
MORNING_OPEN = lambda n: [f'通勤中のみなさん、おはようございます。\n今日の物欲会議、議題は{n}件です🫡', f'朝の満員電車で見る用の{n}選です🚃\n買うかどうかは帰ってから決めてOK', f'おはようございます。\n寝ぼけたまま楽天パトロールした成果{n}件です☕']
LINK_LINES = ['詳細はプロフィールのリンクから🔍', '保存しておくと、あとで探さずに済みます📌\n詳細はプロフィールのリンクから', '迷ったらカートで一晩寝かせるのがおすすめ💤\n詳細はプロフィールのリンクから', '見るだけでも大歓迎👀 プロフィールのリンクから楽天ROOMへ']
FOOTERS = ['▶ 財布と相談のうえ、プロフィールのリンクから', '▶ 見るだけでもどうぞ。プロフィールのリンクから楽天ROOMへ', '▶ レビューも見てから決めてね（プロフィールのリンクから）', '▶ 気になった番号はリプで教えてね（詳細はプロフのリンク）']
AXES = {
    'jitan': dict(label='時短', kw=re.compile(r'時短|自動|タイマー|上から給水|置くだけ|工事不要|急速|ワンタッチ|ボタン|洗える|すぐ|まとめて|一度に|手軽'), title=['時短で選ぶ3つ', '家事も充電も、時短したい人へ'], open='今日は「時短」目線で{n}つ。'),
    'cospa': dict(label='コスパ', kw=re.compile(r'送料無料|セット|\d個|個入|×\s*\d|大容量|まとめ買い|ポイント\d+倍|\d+円以下|ポッキリ|訳あり|\d+ロール|\d+袋'), title=['コスパで選ぶ3つ', '財布と相談済みの3つ'], open='今日は「コスパ」目線で{n}つ。'),
    'look': dict(label='見た目', kw=re.compile(r'色|カラー|デザイン|ガラス|木目|ウォールナット|ホワイト|ブラック|マット|インテリア|陶器|鉢|薄型|スリム|モコモコ'), title=['見た目で選ぶ3つ', '置くだけで部屋が整う3つ'], open='今日は「見た目」目線で{n}つ。'),
    'trust': dict(label='口コミ', kw=re.compile(r'レビュー|公式|正規|1位|人気|いいね'), title=['口コミで選ぶ3つ', 'レビューが背中を押す3つ'], open='今日は「口コミ」目線で{n}つ。'),
}
STRONG_GIDS = {'senen', 'refill', 'cosme', 'plant', 'x-skin', 'x-kitchen'}
STRONG_RE = re.compile(r'iFace|スマホケース|iPhone.{0,6}ケース|充電器|モバイルバッテリー|ケーブル|ポッキリ|tower|山崎実業|詰め替え|つめかえ|詰替|観葉|ガジュマル|サボテン|多肉|美容液|化粧水|乳液|エマルジョン|スイーツ|焼き菓子|ロールケーキ|チロリアン')
NUM = ['1️⃣', '2️⃣', '3️⃣', '4️⃣']


def norm(s):
    s = unicodedata.normalize('NFKC', str(s or '')).lower()
    return re.sub(r'[\s\W_]+', '', s)


def price_num(p):
    m = re.search(r'[\d,]+', str(p or ''))
    return int(m.group().replace(',', '')) if m else 0


def h31(s):
    x = 0
    for ch in str(s):
        x = (x * 31 + ord(ch)) & 0xffffffff
    return x


def pick(arr, seed):
    return arr[seed % len(arr)]


def recent_texts(repo, days=3):
    # 直近の投稿（朝・昼・夜）の本文。書き出し・問いかけ・締めの文が続けて同じにならないように使う
    since = (datetime.now(JST) - timedelta(days=days - 1)).strftime('%Y%m%d')
    out = ''
    for f in glob.glob(os.path.join(repo, 'queue', '*.json')):
        if os.path.basename(f)[:8] >= since:
            try:
                out += json.load(open(f, encoding='utf-8')).get('text', '') + '\n'
            except Exception:
                pass
    return out


def pick_fresh(arr, seed, recent, keys=()):
    # 直近3日に出た文（1行目で判定）と、同じ話題の言葉を含む文を避けて選ぶ。全部かぶるときは元のまま
    ok = [s for s in arr if s.split('\n')[0] not in recent and not any(k in s and k in recent for k in keys)]
    return pick(ok or arr, seed)


def load_room(html_path):
    html = open(html_path, encoding='utf-8').read()
    m = re.search(r'<script id="room-data" type="application/json">(.*?)</script>', html, re.S)
    return json.loads(m.group(1)) if m else {'genres': []}


def load_posts(d):
    out = []
    for f in glob.glob(os.path.join(d, '**', '*.json'), recursive=True):
        try:
            j = json.load(open(f, encoding='utf-8'))
        except Exception:
            continue
        r = j.get('data', j)
        if isinstance(r, dict) and r.get('itemcode'):
            out.append(r)
    return out


def cat_of(it, gid):
    c, tag = it.get('collection', ''), it.get('genreTag', '')
    if re.search(r'スキンケア・コスメ|ヘアケア・美容家電', c) or re.search(r'コスメ|スキンケア|メイク|ヘアケア|美容|保湿', tag) or gid == 'cosme':
        return 'beauty'
    if 'ガジェット' in c or re.search(r'ガジェット|スマホ|オーディオ|PC周辺|カメラ', tag) or gid in ('gadget', 'mini'):
        return 'gadget'
    if 'キッチン・生活家電' in c or re.search(r'家電|乾燥|加湿|暖房|暑さ', tag) or gid == 'kaden':
        return 'kaden'
    return 'life'


def theme_of(items):
    best, bn = 'base', 0
    for k in ('tabi', 'apple', 'winter', 'refill'):
        T = THEMES[k]
        n = sum(1 for it in items if T['re'].search(it['name'] if T['name_only'] else ' '.join([it['name'], it.get('hook', '')] + it.get('points', []))))
        if n > bn:
            best, bn = k, n
    # 1件だけ当てはまってもテーマにしない（例：イヤホン＋バームクーヘン×3 で「ストック」になるのを防ぐ）
    return best if bn >= 2 else 'base'


def axis_pt(ax, it):
    if ax == 'trust':
        if it.get('voice'):
            return it['voice']
        p = next((x for x in it.get('points', []) if AXES['trust']['kw'].search(x)), '')
        rv = price_num(it.get('reviews'))
        return p or (f"ROOMでいいね{it['likes']}件" if (it.get('likes') or 0) >= 30 else f"レビュー{it.get('reviews')}の定番" if rv >= 100 else '')
    return next((p for p in it.get('points', []) if AXES[ax]['kw'].search(p) and not re.search(r'送料\d', p)), '')


def th_col(it):
    n = ' '.join([it['name'], it.get('genreTag', '')] + it.get('tags', []))
    if re.search(r'iPhone|Apple|MagSafe|AirPods|Lightning|iPad|Apple ?Watch|AirTag', n, re.I):
        return 'apple'
    if re.search(r'暖房|ヒーター|ストーブ|毛布|電気敷|こたつ|カイロ|加湿|発熱|防寒|あったか|ブランケット', n):
        return 'winter'
    if it.get('_gid') == 'refill' or re.search(r'詰め替え|つめかえ|リフィル|まとめ買い', n):
        return 'refill'
    return ''


def clip(s, n):
    return s if len(s) <= n else s[:n - 1] + '…'


# 昼は商品を出さない「会話」投稿（宣伝が続くと見てもらえなくなるため）。テーマは日替わり、同じ文は二度使わない
TALKS = [
    'スマホの充電、何%から焦り始めますか？\n私は40%で「そろそろか…」ってなります🔋',
    'ケーブルって、なんで使いたい時だけ1本も見つからないんでしょうね。\n家に何本あるか、数えたら負けな気がしてます🔌',
    '朝の脱衣所、もはや修行の場。\n冬の朝いちばんつらい場所、どこですか？🥶',
    '暖房のスイッチ、もう入れました？\nまだ我慢してる派の人、仲間です🔥',
    '詰め替えるとき、毎回ちょっとこぼす派です。\nこぼさない人、コツ教えてください🙏',
    '買い忘れて一番困るもの、トイレットペーパー説。\nみなさんは何ですか？🧻',
    'イヤホン、片方だけ行方不明になる現象に名前つけたい。\n経験ある人いますか？🎧',
    'iPhoneの「残りわずか」通知、心臓に悪すぎません？📱',
    '「これ便利だった！」って買って本当に使い続けてるもの、ひとつ教えてください👇\n参考にさせてもらいます',
    '休みの日は弾丸で神社巡りしてます⛩️\n最近行ってよかった神社、ありますか？',
    'お守り、気づいたら増える一方です。\n何個持ってるか、正直に教えてください😂',
    '旅先で毎回ラーメン食べちゃう人、手を挙げて🙋‍♂️\nご当地のおすすめあれば知りたい',
    '楽天のカート、入れっぱなしの商品が何個ありますか？\n私は数えるのをやめました🛒',
    'お買い物マラソン、何店舗まで回る派ですか？\n毎回「今回は控えめに」と言ってる気がします',
    '布団から出るまでの時間、冬になると倍になりません？\nみなさん何分かかってます？⏰',
    '加湿器のお手入れ、ちゃんとやれてる人を尊敬してます。\nコツありますか？💧',
    'ガジェット買うとき、レビューどこまで読みますか？\n私は星1から読む派です🔍',
    '家電って「買ってよかった」と「買わなきゃよかった」が極端ですよね。\nみなさんの一番の当たりは？',
    'スマホ、何年使ってますか？\n私は電池が持たなくなるまで粘る派です📱',
    '在宅のとき、首と肩がガチガチになる問題。\nみなさんどう対策してます？',
    '冬になると静電気でドアノブと戦ってます⚡\n対策してる人いますか？',
    'ネットで買い物するとき、送料無料じゃないと急に冷める現象、わかる人いますか？📦',
    '朝のコーヒー派？お茶派？\nちなみに私はその日の気分です☕',
    '寝る前のスマホ、やめなきゃと思いながら今日も見てます🌙\n同じ人いますか？',
    # 10/25 方針(2)：ROOMを実際にやっている人が共感する本人の実体験（事実だけ）
    '楽天ROOMって、いいねは付くのに売れない問題ありません？🤔\nROOMやってる方、「買いたい人」にどうやって届けてますか？',
    'ROOMで意外だったこと。\n派手な新商品より、詰め替えや定番の消耗品がおすすめに乗りました🧴\nみなさんは何がおすすめに乗りました？',
    '楽天ROOMの投稿、毎日の流れを決めてコツコツ続けてます📱\nROOMやってる方、1日のルーティンありますか？',
    'ガジェット好きとして聞きたいです🔌\nここ1年で「これは買ってよかった」ガジェット、ひとつだけ挙げるなら何ですか？',
    'パソコン、何年使ってますか？\n私は「起動中にコーヒーが淹れられる」まで粘ります💻',
    'イヤホン、今ので何代目ですか？\n私は数えるのが怖くて途中でやめました🎧',
    'スマホの写真、今何枚入ってますか？\n私は消すのが面倒で増える一方です📸',
    '充電器、家に何個ありますか？\n数えたら「なんでこんなに」ってなりました🔌',
    'スマホのケース、何回替えましたか？\n私は本体より先に飽きる派です📱',
    # 10/27 他の人の投稿から：「安い・すぐ使える・場面が浮かぶ」が売れるという声 → 選び方を聞く二択に
    '通販で買うとき、決め手は値段？レビュー？\n私は「使う場面が浮かぶか」で最後に決めてます🔍\nみんなは？',
    '1000円以下のガジェット、買ってよかった物ありますか？\n私はケーブルをまとめるだけの小物が地味に当たりでした🔌\nみんなの当たりは？',
    'セールの日、カートに入れてから買うまで何日寝かせます？\n私は最長で2週間寝かせたことがあります💤\nみんなは？',
    '楽天のお気に入り、何個入ってますか？\n私は数字を見ないようにしてます📦\nみんなは？',
]


# ROOM仲間募集の投稿（他の人の「初報酬報告＋仲間募集」がいいね149・コメント87だったので取り入れる）。
# 1日おきに昼の会話投稿をこちらにする。売上などの数字は作らない（本当の数字だけ使う）
NAKAMA = [
    # 10/27：仲間募集も「数字・一言・二択で答えられる問いかけ＋先に自分の答え＋みんなは？」の形にする（事実の体験だけ）
    '楽天ROOM、いいねは付くのに売れない…わかる人？🙋‍♂️\n私はまさにそれで、Threadsで話しかける方に力を入れ始めました\nROOMやってる人、みんなはどう？',
    'ROOMでおすすめに乗ったの、新商品？定番？\n私は意外にも、詰め替えや定番の消耗品でした🧴\nみんなはどっち？👇',
    'ROOMの投稿、朝派？夜派？\n私は毎日の流れを決めて、コツコツ足してます📱\nみんなは何時ごろ？',
    '楽天ROOM、始めて何年目ですか？\n私はまだまだ手探り組です🔰\nみんなは？👇',
    'ROOMで紹介するの、ガジェット多め？日用品多め？\nガジェット好きなのに、気づけば日用品も増えてます🔌\nみんなは？',
    '楽天ROOM、1日に何件投稿してますか？\n私は「毎日ちょっとずつ」派です📱\nROOMやってる人、みんなは？',
    'ROOMの商品、写真の映え重視？口コミ重視？\n私はレビュー件数を見てから決める派です🔍\nみんなは？',
]


def log_text(repo):
    """Threads運用ログ：insights の本当の数字だけで作る。数字がそろわなければ空文字。"""
    try:
        lg = json.load(open(os.path.join(repo, 'state', 'insights_log.json'), encoding='utf-8'))
        days = sorted(lg)
        cur = lg[days[-1]]['account']['followers_count']
        prev = lg[days[-2]]['account']['followers_count'] if len(days) > 1 else None
        posts = lg[days[-1]].get('posts', {})
        best = max(posts.items(), key=lambda kv: kv[1].get('views', 0)) if posts else None
    except Exception:
        return ''
    n = (datetime.now(JST).date() - datetime(2026, 10, 21, tzinfo=JST).date()).days + 1
    diff = '' if prev is None else f'（前日比 {cur - prev:+d}）'
    kind = {'morning': '朝の投稿', 'noon': '昼の会話投稿', 'night': '夜の投稿'}
    line = f"\n最近いちばん見られたのは{kind.get(best[0].split('-')[-1], '投稿')}（{best[1].get('views', 0)}回）" if best and best[1].get('views') else ''
    return f'Threads運用ログ {n}日目📊\nフォロワー {cur}人{diff}{line}\n同じくROOMやってる方、一緒にコツコツいきましょう🤝'


def followers(repo):
    try:
        return int(json.load(open(os.path.join(repo, 'state', 'insights.json'), encoding='utf-8'))['account']['followers_count'])
    except Exception:
        return 0


TALK_KEYS = ['充電', 'ケーブル', '寒い', '暖房', '詰め替え', '買い忘れ', 'イヤホン', 'iPhone', '神社', 'お守り', 'ラーメン', 'カート',
             'マラソン', '布団', '加湿器', 'レビュー', '家電', 'コーヒー', 'スマホ', '旅', 'おすすめに乗', 'ルーティン', 'ガジェット']


def talk(repo):
    used_p = os.path.join(repo, 'state', 'talk.json')
    used = json.load(open(used_p, encoding='utf-8')) if os.path.exists(used_p) else []
    # 1日おきに仲間募集の投稿にする
    f = followers(repo)
    pool = TALKS
    if datetime.now(JST).toordinal() % 2 == 0:
        pool = [t for t in NAKAMA if ('{f}' not in t or f >= 100) and (t != '{log}' or log_text(repo))]
    pool = [t for t in pool if not banned(t)]
    left = [t for t in pool if t not in used]
    if not left:
        used = [t for t in used if t not in pool]
        left = pool[:]
    # 同じ日の朝の投稿と話題がかぶらないようにする（例：朝「お守り何個？」→昼もお守り、を避ける）
    # 10/27：直近3日の投稿（text・reply）と話題・相手がかぶらないようにする
    seen = ''
    for k in range(7):  # 10/27：伸びた話題（スマホ）の焼き直しが伸びなかったため、話題は7日あける
        day = (datetime.now(JST) - timedelta(days=k)).strftime('%Y%m%d')
        for f in glob.glob(os.path.join(repo, 'queue', day + '-*.json')):
            d = json.load(open(f, encoding='utf-8'))
            seen += d.get('text', '') + str(d.get('reply', ''))
    fresh = [t for t in left if not any(k in t and k in seen for k in TALK_KEYS)]
    left = fresh or left
    text = left[h31(datetime.now(JST).strftime('%Y%m%d')) % len(left)]
    used.append(text)
    text = log_text(repo) if text == '{log}' else text.replace('{f}', str(f))
    if not re.search(r'(？|\?|👇|ますか|ませんか|ですか)[^\n]{0,3}$', text):
        text += '\nみんなは？'  # 10/27：最後にもう一度聞く（決まり文句の👇は付けない）
    os.makedirs(os.path.dirname(used_p), exist_ok=True)
    json.dump(used, open(used_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    stamp = datetime.now(JST)
    qid = stamp.strftime('%Y%m%d-%H%M') + '-noon'
    q = {'id': qid, 'slot': 'noon', 'form': 'talk', 'kind': 'talk', 'created': stamp.isoformat(timespec='minutes'), 'text': text, 'items': []}
    os.makedirs(os.path.join(repo, 'queue'), exist_ok=True)
    with open(os.path.join(repo, 'queue', qid + '.json'), 'w', encoding='utf-8') as f:
        json.dump(q, f, ensure_ascii=False, indent=1)
    print(f'{qid} 会話投稿')


def gather(a):
    """ROOMに投稿済みで、まだThreadsに出していない商品を、選ぶ順に並べて返す。"""
    room = load_room(a.html)
    by_code = {}
    for g in room.get('genres', []):
        for it in g.get('items', []):
            if it.get('itemcode'):
                by_code.setdefault(it['itemcode'], dict(it, _gid=g['id']))

    sent_path = os.path.join(a.repo, 'state', 'sent.json')
    sent = json.load(open(sent_path, encoding='utf-8')) if os.path.exists(sent_path) else {}
    # まだ公開されていない（queue にあって posted に無い）商品も選ばない
    pending = set()
    for f in glob.glob(os.path.join(a.repo, 'queue', '*.json')):
        qid = os.path.splitext(os.path.basename(f))[0]
        if not os.path.exists(os.path.join(a.repo, 'state', 'posted', qid + '.json')):
            for it in json.load(open(f, encoding='utf-8')).get('items', []):
                pending.add(it['itemcode'])
                pending.add(norm(it['name']))
    sent_names = {norm(v.get('name')) for v in sent.values() if isinstance(v, dict)}

    now = time.time() * 1000
    lim = now - LOOKBACK_DAYS * 864e5
    cands = []
    for r in load_posts(a.posts):
        if r.get('ng') or (r.get('postedAt') or 0) < lim:
            continue
        code = r['itemcode']
        if code in sent or code in pending or norm(r.get('name')) in sent_names or norm(r.get('name')) in pending:
            continue
        base = by_code.get(code)
        it = dict(base) if base else {'itemcode': code, 'name': r.get('name', ''), 'price': r.get('price', ''), 'hook': r.get('hook', ''), 'quip': r.get('quip', ''), 'points': [], '_gid': r.get('genre', '')}
        it.setdefault('hook', r.get('hook', ''))
        it.setdefault('quip', r.get('quip', ''))
        it['_t'] = r.get('postedAt') or 0
        gid, p, c = it.get('_gid', ''), price_num(it.get('price')), cat_of(it, it.get('_gid', ''))
        likes = it.get('likes') or 0
        proven = -3 if (gid == 'likepop' or likes > 0) else -2 if gid == 'fanpop' else -1 if gid == 'roompop' else None
        # Threads向き：話のネタになる「神社・旅・ラーメン」の商品を最優先（1本に2件まで）
        # いいねが多いジャンル（千円スイーツ・tower収納・コスメ・詰め替え・観葉植物）と、実際に売れたスマホケース・充電まわり（10/24確認）。1,000〜10,000円を優先
        strong = 1000 <= p <= 10000 and (gid in STRONG_GIDS or STRONG_RE.search(it['name']))
        sc = -4 if gid == 'tabi' else -3.5 if strong else proven if proven is not None else (0 if c in ('gadget', 'kaden') else 1) if 0 < p <= 10000 else 2 if 0 < p <= 30000 else 3
        it['_c'] = c
        cands.append((sc, -likes, -it['_t'], it))
    cands.sort(key=lambda x: x[:3])
    return [c[-1] for c in cands]


def summary(a, cands):
    """夜（と、以前の朝）の「3件まとめ」投稿。"""
    now = time.time() * 1000
    items, seen = [], set()
    for it in cands:
        k = norm(it['name'])
        if k in seen:
            continue
        # quip（ひと言）が無い・「やつ」を含む・重複する商品は使わない
        q = it.get('quip') or ''
        if not q or 'やつ' in q or any(q == o.get('quip') for o in items):
            continue
        if it.get('_gid') == 'tabi' and sum(1 for o in items if o.get('_gid') == 'tabi') >= 2:
            continue
        seen.add(k)
        items.append(it)
        if len(items) == PER_POST:
            break
    if len(items) < 2:
        print('なし')
        return

    n = len(items)
    dn = int(now // 864e5) * 3 + SLOTS.index(a.slot)
    th = theme_of(items)
    # 切り口（時短・コスパ・見た目・口コミ）は合う商品が多いものから、前回と同じにならないよう日替わりで
    last_ax = ''
    lp = sorted(glob.glob(os.path.join(a.repo, 'state', 'posted', '*.json')))
    if lp:
        try:
            last_ax = json.load(open(lp[-1], encoding='utf-8')).get('axis', '')
        except Exception:
            pass
    ax_scores = []
    for i, ax in enumerate(AXES):
        fit = sum(1 for it in items if axis_pt(ax, it))
        ax_scores.append((-(min(fit, 2) * 0.6 - (1.5 if ax == last_ax else 0) - (0 if fit else 9) + ((dn + i) % 4) * 0.05), ax))
    ax = sorted(ax_scores)[0][1]
    if not any(axis_pt(ax, it) for it in items):
        ax = ''  # 切り口に合う推しポイントが無いときは切り口の行を出さない

    T = THEMES[th]
    title = pick(T['title'], dn) if (th != 'base' or not ax) else pick(AXES[ax]['title'], dn)
    opens = (MORNING_OPEN(n) if a.slot == 'morning' else NOON_OPEN(n) if a.slot == 'noon' else T['open'](n)) if th == 'base' else T['open'](n)
    recent = recent_texts(a.repo)
    today_txt = recent_texts(a.repo, 1)
    hook = pick_fresh(opens, dn, recent)
    ask = pick_fresh(T['ask'], dn * 3 + 1, recent, [k for k in TALK_KEYS if k in today_txt])
    link_line = pick_fresh(LINK_LINES, dn * 7 + 2, recent)
    footer = pick(FOOTERS, dn * 7 + 3)
    link = ROOM_COLS_URL if n > 1 else ROOM_URL
    topic = 'ガジェット' if any(it['_c'] in ('gadget', 'kaden') for it in items) else '楽天ROOM'

    def free(it):
        return '送料無料' in ' '.join(it.get('points', []) + it.get('badges', []) + [it.get('desc', '')])

    def body(with_ax):
        rows = []
        for i, it in enumerate(items):
            s = f"{NUM[i]} {it.get('hook') or it['name']}\n　{it.get('price', '')}{'・送料無料' if free(it) else ''}"
            if it.get('quip'):
                s += f"\n　💬 {it['quip']}"
            if (it.get('likes') or 0) >= 30 and ax != 'trust':
                s += f"\n　❤️ ROOMでいいね{it['likes']}件"
            if with_ax and ax and axis_pt(ax, it):
                s += f"\n　🎯 {clip(axis_pt(ax, it), 32)}"
            rows.append(s)
        return '\n\n'.join(rows)

    def build(with_ax, with_link):
        axl = AXES[ax]['open'].format(n=n) + '\n\n' if (with_ax and ax) else ''
        # URLは本文に入れない（リンク付きは広がりにくいため、リンクは自分の返信に付ける）
        return f"【PR・楽天ROOM】\n{hook}\n\n{axl}{body(with_ax)}\n\n{ask}\n{link_line if with_link else '詳細はプロフィールのリンクから'}\n※価格は投稿時点のものです"

    text = build(True, True)
    if len(text) > 490:
        text = build(False, True)
    if len(text) > 490:
        text = build(False, False)
    text = clip(text, 490)

    stamp = datetime.now(JST)
    qid = stamp.strftime('%Y%m%d-%H%M') + '-' + a.slot
    q = {
        'id': qid, 'slot': a.slot, 'form': 'summary', 'created': stamp.isoformat(timespec='minutes'),
        'title': title, 'footer': footer, 'axis': ax, 'theme': th, 'topic': topic, 'text': text,
        'reply': f"▼楽天ROOMはこちら\n{link}",
        'items': [{'itemcode': it['itemcode'], 'name': it['name'], 'hook': it.get('hook', ''), 'price': it.get('price', ''), 'quip': it.get('quip', '')} for it in items],
    }
    os.makedirs(os.path.join(a.repo, 'queue'), exist_ok=True)
    with open(os.path.join(a.repo, 'queue', qid + '.json'), 'w', encoding='utf-8') as f:
        json.dump(q, f, ensure_ascii=False, indent=1)
    print(f'{qid} {n}件')


# ───────── 形（ネタ帳）─────────
# 時間帯ごとに使える形。BASE_FORMS はその時間帯の基本形で「3日以内に繰り返さない」の対象外
SLOTS = ['morning', 'noon', 'night', 'late']
FORMS = {
    'morning': ['basic', 'discover', 'n1', 'n5', 'n2', 'n11', 'n3'],
    'noon': ['talk', 'n2', 'n11'],
    'night': ['basic', 'kuyou', 'n12'],
    'late': ['n15'],
}
ALL_FORMS = {f for v in FORMS.values() for f in v}
BASE_FORMS = {'basic', 'talk', 'summary', 'n15'}
OLD_FORM = {'morning': 'summary', 'noon': 'talk', 'night': 'summary', 'late': 'n15'}  # form が無い昔の投稿
PR_LINE = '※PR：返信に楽天ROOMのリンクがあります'

# 商品の「種類」。本文には商品名を出さず、この種類で書く（並びは細かいものから）
TYPES = [
    (r'ロボット掃除機|ルンバ|Roomba|DEEBOT', 'ロボット掃除機', 0), (r'水拭き', '水拭きクリーナー', 0),
    (r'掃除機|クリーナー', 'コードレス掃除機', 0), (r'イヤホン|イヤフォン', 'ワイヤレスイヤホン', 1),
    (r'ヘッドホン|ヘッドフォン', 'ヘッドホン', 1), (r'スピーカー', 'スピーカー', 1), (r'マイク', 'ワイヤレスマイク', 1),
    (r'スマートウォッチ|WATCH|GPSウォッチ|vivoactive', 'スマートウォッチ', 1), (r'モバイルバッテリー', 'モバイルバッテリー', 1),
    (r'充電器', '充電器', 1), (r'ケーブル', '充電ケーブル', 1), (r'スマホケース|iFace|iPhone.{0,12}ケース', 'スマホケース', 1),
    (r'食洗機|洗剤|フィニッシュ', '食洗機用洗剤', 0), (r'タブレット', 'タブレット', 1), (r'ミラーレス|一眼|カメラ', 'カメラ', 1), (r'プロジェクター', 'プロジェクター', 0),
    (r'SIMフリー|スマホ|iPhone|Pixel', 'スマホ', 1), (r'加湿器', '加湿器', 0), (r'除湿機', '除湿機', 0),
    (r'空気清浄', '空気清浄機', 0), (r'ドライヤー', 'ドライヤー', 0), (r'電気毛布', '電気毛布', 0), (r'こたつ', 'こたつ', 0),
    (r'ヒーター|ストーブ', 'ヒーター', 0), (r'ケトル', '電気ケトル', 0), (r'炊飯器', '炊飯器', 0), (r'フライパン', 'フライパン', 0),
    (r'ハンディガン', 'ハンディガン', 1), (r'ルーター', 'Wi-Fiルーター', 0), (r'キーボード', 'キーボード', 1), (r'マウス', 'マウス', 1),
    (r'モニター', 'モニター', 0), (r'コンポ', 'コンポ', 0), (r'タオル', 'タオル', 0), (r'観葉植物|鉢植え|\d号鉢', '観葉植物', 0),
    (r'化粧水|ローション', '化粧水', 0), (r'美容液', '美容液', 0),
]
SPEC_RE = re.compile(r'IP[X\d]\d|Bluetooth\s*\d|\d+(?:\.\d+)?\s*(?:時間|畳|mm|cm|インチ|W|mAh|GB|TB|℃|ml|mL|L|kg|g|色|段階|台|枚|個|Hz|dB|万画素|号)')
NOT_SPEC = re.compile(r'円|レビュー|件|★|送料|発送|お届け|ポイント|OFF|位|保証|公式|正規|予約|出荷|年')


def type_of(it):
    for rx, label, portable in TYPES:
        if re.search(rx, it.get('name', '')):
            return label, portable
    return None, 0


def spec_facts(it):
    """数字の入った事実（投稿ノートの points と商品名から）。最大2つ。"""
    out = []
    for p in it.get('points', []):
        if SPEC_RE.search(p) and not NOT_SPEC.search(p):
            out.append(clip(p.strip(), 26))
    if len(out) < 2:
        for seg in re.split(r'[\s　【】\[\]（）()/／]+', it.get('name', '')):
            if 2 <= len(seg) <= 16 and SPEC_RE.search(seg) and not NOT_SPEC.search(seg) and seg not in ' '.join(out):
                out.append(seg)
    return out[:2]


def free_ship(it):
    return '送料無料' in ' '.join(it.get('points', []) + it.get('badges', []) + [it.get('desc', '')])


# 朝の基本形：会話の書き出し＋問いかけ（本文に商品名は出さない）。商品は返信に1件
BASIC_OPEN = {
    'gadget': ['ガジェット好きあるある。\n箱を開ける前に、スペック表をもう一回読み直す。\nみなさんは開封の儀、じっくり派？即開け派？📦',
               'ガジェットの保護フィルム、気泡ゼロで貼れた日は一日中機嫌がいいです📱\nみなさんは自分で貼る派？お店で貼ってもらう派？',
               'ガジェット選びで最後の決め手になるの、スペック？見た目？\n私はだいたい「充電端子が何か」で決まります🔌',
               'ガジェット好きの朝は、まず全部の充電残量チェックから🔋\nみなさんの朝イチの儀式、何ですか？'],
    'kaden': ['家電って、買う前はスペック表を毎日眺めるのに、届いたら説明書は読まない不思議。\nみなさんは説明書読む派？読まない派？📖',
              '家電の「型落ち」と「最新」、毎回ここで30分迷います。\nみなさんはどっち派ですか？🔌',
              '一番「買ってよかった」家電、ひとつだけ挙げるなら何ですか？\nみなさんの答えを参考にさせてください🙏',
              '家電の箱って、なぜか捨てられずに押し入れに積んでしまう。\nみなさんは箱、取っておく派？すぐ捨てる派？📦'],
    'beauty': ['朝の支度、何分でできますか？\n5分のつもりが、毎回15分かかってます⏰',
               '季節の変わり目、スキンケアを変える派？ずっと同じ派？\nガジェット好きなのに、ここだけは保守派です',
               '洗面台に並ぶボトル、気づいたら増えてません？\nみなさんの家、何本ありますか？🧴'],
    'life': ['「これ、もっと早く買えばよかった」って思った日用品、ありますか？\nみなさんの当たりを知りたいです👇',
             '休みの日の朝、最初にやること何ですか？\nとりあえず楽天のカートを確認してしまいます🛒',
             '家の中で「ここだけは整えたい」場所、どこですか？\n充電コーナーだけは死守してます🔌'],
}
BASIC_TAIL = ['今朝の1品は返信に置いておきます👇', '今日の1品、返信にそっと置いておきます👇', '気になる1品を返信に置いておきますね👇']

# 発見型（10/25 本人提案）：書き出し・ツッコミ・二択はそれぞれ8個以上
DISC_SCENE = [  # (場面, 持ち歩く物だけか, 二択)
    ('通勤にも在宅にも', 1, 'みんなは出社派？在宅派？'),
    ('キャンプにも部屋にも', 1, 'みんなはアウトドア派？インドア派？'),
    ('旅行にも近所のカフェにも', 1, '休みの日は遠出派？近場派？'),
    ('ジムにも散歩にも', 1, '体を動かすならジム派？外を歩く派？'),
    ('出張にも帰省にも', 1, '移動中は寝る派？起きてる派？'),
    ('朝のランニングにも夜の散歩にも', 1, '体を動かすなら朝派？夜派？'),
    ('平日にも休日にも', 0, '平日にがんばる派？休日に本気出す派？'),
    ('朝にも夜にも', 0, 'みんなは朝型？夜型？'),
    ('リビングにも寝室にも', 0, '家で一番長くいるの、リビング派？寝室派？'),
    ('ひとり時間にも家族時間にも', 0, 'ひとり時間がほしい派？みんなでわいわい派？'),
    ('仕事の日にもだらだらの日にも', 0, 'オンオフの切り替え、得意派？苦手派？'),
    ('自分用にもプレゼントにも', 0, '買うなら自分用派？贈り物派？'),
]
DISC_OPEN = ['{scene}{verb}{type}、見つけてしまった…。', '見つけてしまった…。{scene}{verb}{type}。',
             '楽天パトロール中、{scene}{verb}{type}を見つけてしまった…。', '朝から{scene}{verb}{type}を見つけてしまった…。今日の集中力、ここで使い切りそう。',
             '{scene}{verb}{type}、見つけてしまいました…（小声）', 'ちょっと聞いてください。{scene}{verb}{type}、見つけてしまった…。',
             '見なかったことにしたい。でも見つけてしまった。{scene}{verb}{type}。', '{type}を探してたわけじゃないのに、{scene}{verb}一品を見つけてしまった…。']
DISC_TSUKKOMI = ['{spec}って、物欲会議が開会してしまう。', '{spec}…財布欠席くんが耳をふさいでる。', '{spec}と聞いて、ガジェット好きの血が騒いでいる。',
                 '{spec}。この数字だけでごはんが進む。', '{spec}って書いてあるだけで、スペック表を3回読み返した。', '{spec}…ガジェット好きには、この数字がごちそう。',
                 '{spec}って、カートの前で腕組みが止まらない。', '{spec}って、それはもう反則では。']

# N1「買ってないのに詳しい」選手権
N1_OPEN = ['{type}について、語らせてください。', '今日のお題は{type}です。', '{type}の話になると、急に早口になります。', '聞かれてないけど、{type}を語ります。',
           '本日のエントリーは{type}。', '{type}のことなら、持ち主より詳しいかもしれません。', '{type}、スペック表なら暗記しました。', '{type}について、持ってる人のふりをして語ります。']
N1_CLOSE = ['これはもう、実質持ってる。', '語れば語るほど欲しくなる仕組み、誰か止めて。', 'ここまで詳しいなら、もう買ってもいい気がしてきた。', '…と語り終わった今、カートが温まってきました。',
            '我ながら完璧なプレゼンでした。', '持ち主の方、答え合わせお願いします。', '熱量だけなら持ち主に負けません。', '財布欠席くん、今の聞いてた？']
N1_ASK = ['持ってる人、答え合わせお願いします👇', 'みなさんの「買ってないのに詳しいもの」も教えてください👇', 'あなたが買ってないのに語れるもの、何ですか？👇', '持ってる人の本音、こっそり教えてください👇',
          '同じく「買う前に詳しくなる派」の人、いますか？👇', '詳しくなるだけで満足しちゃう派、いますか？👇', 'あなたなら、ここまで調べたら買いますか？👇', '次に語ってほしいジャンル、リプで募集中👇']

# N5 逆レビュー
N5_HEAD = ['【逆レビュー】{type}', '【辛口レビュー（のつもり）】{type}', '【逆レビュー】{type}、正直に言います', '【逆レビュー】{type}の悪いところ',
           '【本音レビュー】{type}', '【逆レビュー】{type}、心を鬼にして', '【逆レビュー】{type}、厳しめに', '【逆レビュー】{type}に物申す']
N5_BAD = ['悪いところ：買う理由が多すぎる。', '悪いところ：断る理由が見つからない。', '悪いところ：スペック表を読むと欲しくなる。', '悪いところ：見れば見るほど欠点が見つからない。',
          '悪いところ：財布欠席くんの立場がない。', '悪いところ：迷う時間が長くなる。', '悪いところ：数字を見ると冷静でいられない。', '悪いところ：他の候補がかすむ。']
N5_ASK = ['あなたの「悪いところが見つからないもの」、教えてください👇', '逆レビューしてほしい物、リプで募集中👇', '持ってる人、本当の悪いところ教えてください👇', 'あなたなら、どこにツッコみますか？👇',
          '最近「欠点が見つからない」と思った物、ありますか？👇', 'これ以上の悪いところ、思いつく人いますか？👇', 'みなさんの辛口レビュー、待ってます👇', '次に逆レビューしてほしいジャンル、教えてください👇']

# N2 擬人化の会話劇（商品×財布欠席くん）。商品のセリフは事実のスペックだけ
N2_PROD = ['俺、{f}やで', 'ちなみに{f}です', '{f}、知ってた？', '聞いて。{f}なんよ', '{f}って、すごない？', 'ほな言わせてもらうけど、{f}', 'もう一回言うで。{f}', '{f}、これが実力です']
N2_WALLET = ['聞こえません', '本日は欠席です', 'その話、また今度で', '耳をふさいでます', '中身がありません', '…（ふたを閉じる音）', '検討します（しない）', '心が揺れてるけど欠席です']
N2_ASK = ['この勝負、どっちの勝ちですか？👇', 'あなたの財布はどっち派？👇', '財布、そろそろ負けそうです。みなさんの財布は？👇', '次は何と財布を戦わせますか？👇',
          '財布が一番弱くなる時間帯、いつですか？👇', 'あなたの家の財布、出席率どれくらいですか？👇', '財布欠席くんに一言お願いします👇', 'あなたなら、どっちの味方をしますか？👇']

# 供養投稿（10/25 本人提案）。語り手は財布欠席くん。商品をけなさない・買わないことを強く勧めない
KU_OPEN = ['🕯 本日の供養', '🕯 本日の見送り報告', '🕯 今日の供養コーナー', '🕯 本日、見送られた物', '🕯 今夜の供養', '🕯 見送り速報', '🕯 本日の供養（財布欠席くん調べ）', '🕯 財布欠席くんの見送り帳']
KU_SERIF = ['今日は欠席です。見送りましょう', 'カートの前まで来ましたね。今日はここまでです', 'いい物なのは知ってます。でも今日は欠席で', '中身がないので、今日は見送りです',
            '心は出席、体は欠席です', '見送るのも、立派な判断です', 'また会える日まで、そっとカートに', '今日はお気持ちだけ受け取ります']
KU_PRAISE = ['見送ったあなたも、えらい。', '見送れた人、今日いちばんえらい。', '見るだけで済ませたあなた、立派です。', '今日も耐えた。それだけで100点。',
             '見送り、それもまた愛。', 'ポチらなかった指に、拍手。', '欲しい気持ちは本物。見送った判断も本物。', '迷えるのは、良い物を知っている証拠。']
KU_ASK = ['今週の見送り報告、待ってます👇', 'あなたが最近見送った物、教えてください👇', '今日見送った物、ここで供養していきませんか？👇', '見送り仲間、リプで集まりましょう🕯',
          'みなさんの「えらかった見送り」、聞かせてください👇', '最近いちばん悩んで見送った物、何ですか？👇', '見送ったけど、まだ気になってる物ありますか？👇', '今月の見送り記録、更新した人いますか？👇']

# N15 深夜の物欲つぶやき（2〜4行・商品名やリンクなし・画像なし）
N15 = ['夜の楽天は、\n昼の私とは別人が見ている。\n朝の私、先に謝っておきます。', '「見るだけ」と言って開いたアプリ、\n閉じ方を忘れました。',
       '理性はもう寝ました。\n起きているのは物欲だけです。', 'カートの中身が増えるたび、\n財布欠席くんの目が遠くなる。', '夜のスペック表は、\nなぜかいつもより輝いて見える。',
       'お気に入り登録は無料。\nそう言い聞かせて、今夜も増えていく。', 'ポチる前に寝る。\nそれが今夜の唯一の目標です。', '夜は判断力が下がるらしい。\nだからカートに入れるだけにしておく。\n…入れるだけ。',
       '財布「もう寝なよ」\n私「あと1ページだけ」', '明日の私へ。\nカートの中身は、夜の私が勝手にやりました。', '物欲にも、\n消灯時間がほしい。', 'おやすみなさい。\nカートは開けっぱなしで寝ます。']

# N11「物欲会議」議事録（議題＝商品の種類と事実のスペック。決議はいつも保留寄り）
N11_HEAD = ['【物欲会議 議事録】', '【第◯回 物欲会議・議事録】', '【物欲会議（臨時）議事録】', '【物欲会議 議事録・要約版】',
            '【物欲会議 議事録（非公開のはずが公開）】', '【本日の物欲会議 議事録】', '【物欲会議・緊急招集 議事録】', '【物欲会議 議事録・速報】']
N11_SHINGI = ['物欲「{f}。これ以上の説明いる？」', '物欲「{f}って、もう答え出てません？」', '物欲「{f}。以上、賛成の方は挙手を」', '理性「{f}…確かに強い」',
              '物欲「{f}。異議のある方はいますか」\n（沈黙）', '物欲「まず{f}。話はそれからだ」', '理性「{f}は認める。認めるけど」', '物欲「{f}。これは会議する必要あった？」']
N11_KETSUGI = ['保留（カートには入れた）', '保留（お気に入りには登録した）', '継続審議（毎晩スペック表を見る）', '保留（次のセールまで）',
               '保留（財布の復帰を待つ）', '可決…と見せかけて保留', '保留（でも気持ちは可決）', '保留（議長が寝落ち）']
N11_ASK = ['あなたの物欲会議、今日の議題は何ですか？👇', 'この議題、あなたなら可決？否決？👇', '最近いちばん長引いた物欲会議、教えてください👇',
           'みなさんの家の会議、財布は出席してますか？👇', '次の会議の議題、リプで募集してます👇', 'あなたの決議はいつも何で終わりますか？👇',
           '保留のままカートに眠ってる物、何個ありますか？👇', '議長（あなた）の判断、聞かせてください👇']

# N12 金曜夜「今週買わずに耐えたもの発表会」（司会は財布欠席くん。商品なし・画像なし）
N12_HEAD = ['🎤 今週買わずに耐えたもの発表会', '🎤 金曜恒例・今週耐えたもの発表会', '🎤 今週の「買わずに耐えた」発表会、開会します',
            '🎤 週末前の発表会：今週買わずに耐えたもの', '🎤 今週も開催・耐えたもの発表会', '🎤 発表会のお時間です（今週耐えたもの）',
            '🎤 今週の耐えた記録、発表会', '🎤 金曜夜の発表会：買わずに耐えたもの']
N12_HOST = ['司会の財布欠席くんです。今週もカートの前で踏みとどまった皆さん、えらい。', '司会は財布欠席くん。本日は出席しております。耐えた話だけ聞きに来ました。',
            '司会の財布欠席くんです。「見るだけ」で済ませた1週間、拍手を送ります👏', '財布欠席くん「今週も皆さんのおかげで、中身が守られました」',
            '財布欠席くん「耐えた物の大きさは問いません。耐えたこと自体が優勝です」', '司会の財布欠席くんです。セールの誘惑を越えてきた皆さん、ようこそ。',
            '財布欠席くん「お気に入り登録で止めた人も、立派な入賞です」', '財布欠席くん「今週、カートに入れて出した人。それも耐えたにカウントします」']
N12_ASK = ['あなたが今週買わずに耐えたもの、発表してください👇', '今週いちばん危なかった「耐えたもの」、教えてください👇', 'エントリーはリプで。耐えたもの、ひとつどうぞ👇',
           '今週の耐えた記録、ここで発表していきませんか？👇', '耐えたもの＋耐えた理由、ひとことでどうぞ👇', '今週「あと一歩でポチりそうだった物」、何でした？👇',
           '耐えた人から順番にどうぞ。財布欠席くんが全員ほめます👇', 'みなさんの今週の耐えたもの、聞かせてください👇']

# N3 値段を別の単位に変換（使った基準は本文に書く。オチは効果の話にしない）
N3_UNITS = [('ラーメン', '杯', 900), ('牛丼', '杯', 500), ('コンビニのおにぎり', '個', 180), ('缶コーヒー', '本', 150),
            ('映画', '本', 2000), ('回転寿司', '皿', 120), ('銭湯', '回', 550), ('ハンバーガー', '個', 400)]
N3_OPEN = ['この{type}、値段を{u}に換算してみました。', '{type}の値段、{u}で数えたら現実味が出るかと思って。', '物欲を落ち着かせるため、{type}を{u}に換算します。',
           '計算してみました。この{type}は、{u}でいうと…', '{type}の値段を{u}換算する会、開催します。', 'ガジェット好きの悪いクセ。{type}の値段を{u}で数える。',
           '値段だけだとピンとこないので、{type}を{u}に置き換えてみた。', '{type}、{u}で言うといくら？を計算しました。']
N3_OCHI = ['換算したら、余計に悩み始めました。', '計算したら、なぜか安く見えてきた。危ない。', '結論：計算は物欲を止めない。', '財布欠席くん「どっちにしても欠席です」',
           '数字にしたら、心が揺れ始めました。', 'でも{u}は、{type}の代わりにはなってくれない。', 'この計算、誰も得しない気がしてきた。', '{u}をガマンすれば…いや、それは無理です。']
N3_ASK = ['あなたなら何に換算しますか？👇', 'みなさんの「換算の単位」、教えてください👇', 'この換算、高い？安い？どっちに見えます？👇', 'あなたの心の通貨は何ですか？👇',
          '物欲を止める換算、他にいい単位あったら教えてください👇', '{u}換算で買ったこと、ありますか？👇', 'これ、あなたなら何{c}分まで出せますか？👇', '次は何を換算してほしいですか？👇']

# 10/27 本人指示「いいね・コメントが来る投稿に」：どの形も
# 1行目＝誰でも数字・一言・二択で答えられる問いかけ（呼びかける相手を毎回変える）→ 2行目＝先に自分の答え（好み・派だけ。体験談は作らない）
# → 3行目＝形ごとのひと言（商品は種類だけ）→ 4行目＝もう一度「みんなは？」。本文は5行以内、商品は返信に1件だけ
# (対象の種類 or カテゴリ, 呼びかける相手, 切り口, 問いかけ, 自分の答え)
QA = [
    ({'ワイヤレスイヤホン', 'ヘッドホン'}, '通勤中', '時短', '通勤中のみなさん、イヤホンは片耳派？両耳派？', 'ガジェット好きの私は、駅のアナウンスが気になる片耳派です🎧'),
    ({'ワイヤレスイヤホン', 'ヘッドホン'}, 'ガジェット好き', '見た目', 'イヤホンを選ぶとき、音質派？見た目派？', '私はケースのフタの開け心地で決める派です🎧'),
    ({'スピーカー', 'コンポ'}, '一人暮らし', '見た目', '一人暮らしのみなさん、家に帰ったら音楽つける派？無音派？', '私は帰ったらまずスピーカーの電源を入れる派です🔊'),
    ({'スピーカー', 'コンポ'}, '夜ふかし', '口コミ', '夜ふかし派の人、寝る前の音楽は何時まで聴いてます？', '私は「あと1曲」が止まらない派です🔊'),
    ({'スマートウォッチ'}, 'ガジェット好き', '見た目', '腕時計、毎日つける派？たまにつける派？', '私は充電さえ忘れなければ毎日つけたい派です⌚'),
    ({'スマートウォッチ'}, '通勤中', '時短', '通勤中のみなさん、スマホの通知は手首で見たい派？画面で見たい派？', '私はポケットから出すのが面倒な手首派です⌚'),
    ({'モバイルバッテリー', '充電器', '充電ケーブル'}, '通勤中', '時短', '家を出るとき、スマホの電池が何％なら安心ですか？', '私は80％を切ってたらバッテリーを連れて出ます🔋'),
    ({'モバイルバッテリー', '充電器', '充電ケーブル'}, 'ガジェット好き', 'コスパ', '充電器、純正派？サードパーティ派？', 'ガジェット好きの私は、出力の数字を見て決める派です🔌'),
    ({'スマホ', 'スマホケース', 'タブレット'}, 'ガジェット好き', '見た目', 'スマホケース、手帳型派？背面だけ派？', '私は薄さと軽さを取る背面派です📱'),
    ({'スマホ', 'スマホケース', 'タブレット'}, '節約中', 'コスパ', '節約中のみなさん、スマホは新品派？型落ち・中古派？', '私は値下がりした型落ちを狙う派です📱'),
    ({'カメラ'}, 'ガジェット好き', '見た目', '写真を撮るの、スマホだけ派？カメラも持つ派？', '私はスペック表を読むたびにカメラが気になる派です📷'),
    ({'カメラ'}, '子育て中', '口コミ', '子育て中のみなさん、写真ってスマホに何枚入ってます？', '私は消すのが面倒で増える一方の派です📷'),
    ({'コードレス掃除機', 'ロボット掃除機', '水拭きクリーナー'}, '家事を回してる', '時短', '家事を回してるみなさん、掃除機は毎日派？週末まとめて派？', '私は気になったときにサッとかけたい派です🧹'),
    ({'コードレス掃除機', 'ロボット掃除機', '水拭きクリーナー'}, '一人暮らし', '時短', '一人暮らしのみなさん、掃除は何曜日にしてます？', '私は「気づいた日が掃除の日」派です🧹'),
    ({'加湿器', '除湿機', '空気清浄機'}, '冬が苦手', '口コミ', '冬が苦手な人、部屋の湿度って気にする派？気にしない派？', '私は数字が見えないと落ち着かない派です💧'),
    ({'加湿器', '除湿機', '空気清浄機'}, '家事を回してる', '時短', '洗濯物、部屋干し派？外干し派？', '私は天気予報を見てから決める派です👕'),
    ({'ヒーター', '電気毛布', 'こたつ'}, '冬が苦手', 'コスパ', '冬が苦手な人、暖房は何月からつけますか？', '私は「まだ早い」と言いながら毎年負ける派です🔥'),
    ({'ヒーター', '電気毛布', 'こたつ'}, '夜ふかし', 'コスパ', '寒い夜、部屋ごと温める派？足元だけ温める派？', '私は足元だけ温めたい派です🔥'),
    ({'ドライヤー'}, '子育て中', '時短', '髪を乾かすのに何分かかってます？', '私はできれば5分で終わらせたい派です💨'),
    ({'電気ケトル', '炊飯器', 'フライパン'}, '一人暮らし', '時短', '一人暮らしのみなさん、朝ごはん食べる派？食べない派？', '私はコーヒーだけで済ませがちな派です☕'),
    ({'電気ケトル', '炊飯器', 'フライパン'}, '節約中', 'コスパ', '節約中のみなさん、自炊は週に何回くらい？', '私は「作れる日に作る」ゆるい派です🍳'),
    ({'食洗機用洗剤'}, '家事を回してる', '時短', '家事を回してるみなさん、食器は手洗い派？食洗機派？', '私は洗い物をためたくない食洗機派です🍽'),
    ({'観葉植物'}, '一人暮らし', '見た目', '部屋に植物、置いてる派？置いてない派？', '私は置きたいけど枯らすのがこわい派です🪴'),
    ({'観葉植物'}, '家事を回してる', '口コミ', '植物の水やり、忘れる派？やりすぎる派？', '私は気にしすぎてやりすぎる派です🪴'),
    ({'Wi-Fiルーター', 'キーボード', 'マウス', 'モニター', 'プロジェクター', 'ワイヤレスマイク', 'ハンディガン'}, 'ガジェット好き', 'コスパ', 'ガジェット、新品で買う派？型落ちを待つ派？', '私は値下がりした瞬間を狙う型落ち派です🔌'),
    ({'gadget'}, 'ガジェット好き', '見た目', 'ガジェット選びの決め手、スペック派？見た目派？', '私はスペック表を3回読んでから見た目で決める派です🔌'),
    ({'gadget'}, '夜ふかし', '口コミ', '夜ふかし派の人、寝る前にスマホを何分見てます？', '私は「あと5分」が3回続く派です🌙'),
    ({'kaden'}, '家事を回してる', '口コミ', '家電の説明書、読む派？読まない派？', '私はスペック表は読むのに説明書は読まない派です📖'),
    ({'kaden'}, '節約中', 'コスパ', '家電を買うなら、最新派？型落ち派？', '私は型落ちが値下がりするのを待つ派です🔌'),
    ({'beauty'}, '通勤中', '時短', '朝の支度、何分で終わりますか？', '私は5分のつもりが毎回15分かかる派です⏰'),
    ({'beauty'}, '冬が苦手', '口コミ', '季節の変わり目、スキンケアを変える派？ずっと同じ派？', 'ガジェット好きの私も、ここだけは保守派です🧴'),
    ({'life'}, '節約中', 'コスパ', '節約中のみなさん、日用品はまとめ買い派？その都度派？', '私は置き場所が許すかぎりまとめ買い派です📦'),
    ({'life'}, '一人暮らし', '時短', '日用品の買い忘れ、月に何回ありますか？', '私は「切れてから気づく」派です🧴'),
]
QA_CLOSE = ['みんなは？', 'みんなはどう？', 'あなたは？', 'みんなのも聞きたいです', 'みんなはどうしてる？', '同じ人いますか？', 'ほかの人のも知りたい', 'みんなはどっち寄り？']  # 10/27：人間らしく。決まり文句と👇の連発をやめる
# 形ごとの3行目（商品は種類だけ。数字はスペックの事実だけ）
QA_LINE = {
    'basic': ['そんな人に{type}を1つ、返信に置いておきます👇', '今日の1品（{type}）は返信にそっと置いておきます👇', '気になる{type}を1つ、返信に置いておきますね👇',
              'ちなみに今日見つけた{type}は返信に👇', '話のついでに、{type}を1つ返信に置いておきます👇', '{type}の当たりを1つ、返信に置いておきます👇',
              '参考までに、{type}を1つ返信に👇', '今日の{type}は返信でこっそり紹介します👇'],
    'n1': ['【買ってないのに詳しい】{type}は{spec}。ここまで語れるのに※まだ買ってません', '{type}なら語れます。{spec}。※まだ買ってません',
           '聞かれてないけど{type}を語ると、{spec}。※まだ買ってません', '{type}のスペック、暗記しました。{spec}。※まだ買ってません',
           '{type}について早口で言うと、{spec}。※まだ買ってません', '持ち主のふりをして言います。{type}は{spec}。※まだ買ってません',
           '本日の詳しい選手権：{type}、{spec}。※まだ買ってません', '{type}、{spec}。…と詳しくなったところで※まだ買ってません'],
    'n5': ['逆レビュー：{type}の悪いところ＝{spec}で迷う時間が長くなる。以上。', '逆レビュー：{type}、{spec}。断る理由が見つからない。以上。',
           '逆レビュー：{type}の欠点は「{spec}」を見ると欲しくなること。以上。', '逆レビュー：{type}、{spec}。財布欠席くんの立場がない。以上。',
           '逆レビュー：{type}、{spec}。他の候補がかすむ。以上。', '逆レビュー：{type}の悪いところ、{spec}で冷静でいられない。以上。',
           '逆レビュー：{type}、{spec}。買う理由が多すぎる。以上。', '逆レビュー：{type}、{spec}。欠点が見つからないのが欠点。以上。'],
    'n2': ['{type}「{spec1}やで」財布欠席くん「聞こえません」', '{type}「ちなみに{spec1}です」財布欠席くん「本日は欠席です」',
           '{type}「{spec1}、知ってた？」財布欠席くん「その話、また今度で」', '{type}「聞いて。{spec1}なんよ」財布欠席くん「耳をふさいでます」',
           '{type}「{spec1}って、すごない？」財布欠席くん「中身がありません」', '{type}「もう一回言うで。{spec1}」財布欠席くん「…（ふたを閉じる音）」',
           '{type}「{spec1}、これが実力です」財布欠席くん「検討します（しない）」', '{type}「{spec1}やで？」財布欠席くん「心が揺れてるけど欠席です」'],
    'n11': ['物欲会議の決議：{type}（{spec1}）は「保留（カートには入れた）」', '物欲会議の結果：{type}（{spec1}）、継続審議。欠席：財布',
            '物欲会議：{type}（{spec1}）は「保留（次のセールまで）」', '物欲会議：{type}（{spec1}）、可決…と見せかけて保留',
            '物欲会議：{type}（{spec1}）は「保留（財布の復帰待ち）」', '物欲会議：{type}（{spec1}）、気持ちは可決・財布は欠席',
            '物欲会議：{type}（{spec1}）は「保留（お気に入りには登録）」', '物欲会議：{type}（{spec1}）、議長が寝落ちして保留'],
    'discover': ['…で、{scene}{verb}{type}を見つけてしまった。{spec}って、物欲会議が開会してしまう。', '{scene}{verb}{type}、見つけてしまった…。{spec}と聞いてガジェット好きの血が騒ぐ。',
                 '楽天パトロール中に{scene}{verb}{type}を発見。{spec}…財布欠席くんが耳をふさいでる。', '見つけてしまった…{scene}{verb}{type}。{spec}って、それはもう反則では。',
                 '{scene}{verb}{type}を見つけてしまった…。{spec}、スペック表を3回読み返した。', '{scene}{verb}{type}、見つけてしまいました（小声）。{spec}がごちそう。',
                 '探してないのに{scene}{verb}{type}を見つけてしまった…。{spec}って、腕組みが止まらない。', 'ちょっと聞いて。{scene}{verb}{type}、{spec}。物欲会議、開会です。'],
    'n3': ['ちなみに{type}は{price}＝{u}約{cnt}{c}分（1{c}{base}円で計算）。でも{u}は{type}の代わりにならない。',
           '{type}を換算：{price}＝{u}約{cnt}{c}分（1{c}{base}円で計算）。計算しても物欲は止まらない。',
           '{type}の{price}、{u}にすると約{cnt}{c}分（1{c}{base}円で計算）。なぜか安く見えてきた。',
           '試しに{type}（{price}）を{u}換算：約{cnt}{c}分（1{c}{base}円で計算）。余計に悩み始めました。'],
    'kuyou': ['財布欠席くん「本日の供養は{type}（{spec1}）。見送ったあなたも、えらい」', '財布欠席くん「{type}（{spec1}）、今日は見送りです。見送れた人、えらい」',
              '🕯 財布欠席くん「{type}（{spec1}）はお気持ちだけ。見送った判断も立派です」', '🕯 本日の供養：{type}（{spec1}）。財布欠席くん「今日も耐えた、100点」',
              '🕯 財布欠席くん「{type}（{spec1}）、心は出席・体は欠席で」', '🕯 見送り速報：{type}（{spec1}）。財布欠席くん「ポチらなかった指に拍手」',
              '🕯 財布欠席くん「{type}（{spec1}）はまた会える日まで、そっとカートに」', '🕯 今夜の供養：{type}（{spec1}）。財布欠席くん「迷えるのは良い物を知ってる証拠」'],
}
# 供養は語り手が財布欠席くんなので、問いかけと答えも見送りの話にする
KU_QA = [
    ('今日、カートの前で我慢した物ありますか？', '財布欠席くんは、我慢できた人を全員ほめる係です'),
    ('欲しい物、カートに入れて一晩寝かせる派？即ポチ派？', '財布欠席くんは、もちろん一晩寝かせる派です'),
    ('今月見送った物、何個ありますか？', '財布欠席くんは数えるたびに誇らしげです'),
    ('セールの通知、すぐ開く派？見ないふり派？', '財布欠席くんは通知が来ると隠れる派です'),
    ('「見るだけ」で終われる日、週に何日ありますか？', '財布欠席くんは毎日を目指しています'),
    ('お気に入り登録で止める派？カートまで入れる派？', '財布欠席くんはお気に入りで止めてほしい派です'),
    ('物欲がいちばん強くなる時間、朝？夜？', '財布欠席くん調べでは、だいたい夜です'),
    ('欲しい物リスト、いま何個ありますか？', '財布欠席くんはリストを見ないようにしています'),
]
AUD_KEYS = ['通勤中', '一人暮らし', '家事を回してる', '子育て中', 'ガジェット好き', '節約中', '夜ふかし', '冬が苦手']


def pick_qa(it, recent, seed):
    """商品の種類（なければカテゴリ）に合う問いかけ。直近3日に使った問いかけ・呼びかけ相手・切り口は避ける。"""
    t, _ = type_of(it)
    c = cat_of(it, it.get('_gid', ''))
    last = recent_axis_aud(recent)
    # 種類に合う問いかけを先に、なければカテゴリの問いかけ
    for pool in ([q for q in QA if t in q[0]], [q for q in QA if c in q[0]] or [q for q in QA if 'life' in q[0]]):
        fresh = [q for q in pool if q[3] not in recent and q[1] not in last]
        fresh2 = [q for q in fresh if q[2] != last.get('axis')]
        if fresh2 or fresh:
            return pick(fresh2 or fresh, seed)
    pool = [q for q in QA if t in q[0] or c in q[0]] or QA
    return pick([q for q in pool if q[3] not in recent] or pool, seed)


def recent_axis_aud(recent):
    """直近3日の本文に出た呼びかけ相手（と、最後に使った切り口）。"""
    out = {k: 1 for k in AUD_KEYS if k in recent}
    for q in QA:
        if q[3] in recent:
            out['axis'] = q[2]
    return out


TITLES = {'basic': '今朝の1品', 'discover': '見つけてしまった…', 'n1': '買ってないのに詳しい選手権', 'n5': '逆レビュー', 'n2': '財布欠席くんとの攻防', 'kuyou': '本日の供養', 'n11': '物欲会議 議事録', 'n3': '値段を換算してみた'}


def form_history(repo):
    """これまでの投稿の (id, 形, 閲覧数)。"""
    views = {}
    for name in ('insights_log.json', 'insights.json'):
        p = os.path.join(repo, 'state', name)
        if not os.path.exists(p):
            continue
        try:
            d = json.load(open(p, encoding='utf-8'))
        except Exception:
            continue
        days = [d] if name == 'insights.json' else [d[k] for k in sorted(d)]
        for day in days:
            for pid, m in (day.get('posts') or {}).items():
                if isinstance(m.get('views'), (int, float)):
                    views[pid] = m['views']
    out = []
    for f in sorted(glob.glob(os.path.join(repo, 'queue', '*.json'))):
        qid = os.path.splitext(os.path.basename(f))[0]
        try:
            q = json.load(open(f, encoding='utf-8'))
        except Exception:
            continue
        out.append((qid, q.get('form') or OLD_FORM.get(q.get('slot') or qid.rsplit('-', 1)[-1], ''), views.get(qid)))
    return out


def choose_form(repo, slot, feasible, seed):
    """3日以内に使っていない形から、反応（閲覧数）が良かった形を少し多めに選ぶ。まだ試していない形も試す。"""
    import random
    hist = form_history(repo)
    since = (datetime.now(JST) - timedelta(days=2)).strftime('%Y%m%d')
    recent = {fm for qid, fm, _ in hist if qid[:8] >= since}
    opts = [f for f in FORMS[slot] if f in feasible and (f in BASE_FORMS or f not in recent)]
    if not opts:
        opts = [f for f in FORMS[slot] if f in feasible and f in BASE_FORMS] or [f for f in FORMS[slot] if f in feasible]
    if not opts:
        return None
    vs = {}
    for _, fm, v in hist:
        if v is not None:
            vs.setdefault(fm, []).append(v)
    avg = {k: sum(v) / len(v) for k, v in vs.items()}
    top = max(avg.values()) if avg else 50
    w = [(avg[f] if f in avg else top) + 15 for f in opts]
    return random.Random(seed).choices(opts, w)[0]


def single_ok(it, form):
    t, _ = type_of(it)
    if not t:
        return False
    facts = spec_facts(it)
    if form == 'kuyou':
        return len(facts) >= 1
    if form == 'n3':
        return price_num(it.get('price')) >= 1000
    if form == 'n11':
        return len(facts) >= 1
    if form in ('discover', 'n1', 'n5', 'n2'):
        return len(facts) >= 1 and cat_of(it, it.get('_gid', '')) != 'beauty'
    return True


# 10/27 本人指示：不安・詐欺っぽさ・規約違反を連想させる言葉は使わない
BANNED = ['凍結', '垢バン', 'BAN', '規制', '稼げ', '稼ぐ', '副業', '月収', '万円稼', '絶対', '必ず儲', '儲か', '今だけ', '急いで', '限定公開', 'コンサル']


def banned(text):
    return [w for w in BANNED if w in (text or '')]


def slot_done(repo, slot):
    """今日この時間帯の投稿がすでにある（公開済み・公開待ち）なら True。削除・見送りした分は数えない。"""
    day = datetime.now(JST).strftime('%Y%m%d')
    for f in glob.glob(os.path.join(repo, 'queue', f'{day}-*-{slot}.json')):
        qid = os.path.splitext(os.path.basename(f))[0]
        pp = os.path.join(repo, 'state', 'posted', qid + '.json')
        if not os.path.exists(pp):
            return True
        r = json.load(open(pp, encoding='utf-8'))
        if not r.get('deleted') and not r.get('skipped'):
            return True
    return False


def write_q(a, q, note):
    bad = banned(q.get('text', '') + str(q.get('reply') or ''))
    if bad:
        print(f"なし（使わない言葉 {bad} が入ったため作り直しが必要）")
        return
    os.makedirs(os.path.join(a.repo, 'queue'), exist_ok=True)
    with open(os.path.join(a.repo, 'queue', q['id'] + '.json'), 'w', encoding='utf-8') as f:
        json.dump(q, f, ensure_ascii=False, indent=1)
    print(f"{q['id']} {note}")


def rotate(repo, pool, seed):
    """pool から、まだ使っていない文を選ぶ（state/talk.json に記録。全部使ったらその pool だけやり直す）。"""
    used_p = os.path.join(repo, 'state', 'talk.json')
    used = json.load(open(used_p, encoding='utf-8')) if os.path.exists(used_p) else []
    left = [t for t in pool if t not in used]
    if not left:
        used = [t for t in used if t not in pool]
        left = pool[:]
    text = left[seed % len(left)]
    used.append(text)
    os.makedirs(os.path.dirname(used_p), exist_ok=True)
    json.dump(used, open(used_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return text


def n12(a):
    stamp = datetime.now(JST)
    seed = h31(stamp.strftime('%Y%m%d') + 'n12')
    recent = recent_texts(a.repo, 8)
    text = pick_fresh(N12_HEAD, seed, recent) + '\n' + pick_fresh(N12_HOST, seed * 7 + 1, recent) + '\n\n' + pick_fresh(N12_ASK, seed * 7 + 2, recent)
    qid = stamp.strftime('%Y%m%d-%H%M') + '-' + a.slot
    write_q(a, {'id': qid, 'slot': a.slot, 'form': 'n12', 'kind': 'talk', 'created': stamp.isoformat(timespec='minutes'), 'text': text, 'items': []}, '耐えたもの発表会')


def late(a):
    stamp = datetime.now(JST)
    text = rotate(a.repo, N15, h31(stamp.strftime('%Y%m%d') + 'late'))
    qid = stamp.strftime('%Y%m%d-%H%M') + '-late'
    write_q(a, {'id': qid, 'slot': 'late', 'form': 'n15', 'kind': 'talk', 'created': stamp.isoformat(timespec='minutes'), 'text': text, 'items': []}, '深夜のつぶやき')


def single(a, form, it):
    """商品1件を使う形（本文に商品名は出さない。商品は返信に1件だけリンク付きで）。"""
    stamp = datetime.now(JST)
    seed = h31(stamp.strftime('%Y%m%d') + a.slot + form)
    recent = recent_texts(a.repo)
    t, portable = type_of(it)
    facts = spec_facts(it)
    price = it.get('price', '')

    def pf(arr, k):
        return pick_fresh(arr, seed * 7 + k, recent)

    spec = '、'.join(facts)
    spec1 = facts[0] if facts else ''
    if form == 'kuyou':
        q, ans = pick_fresh([x[0] for x in KU_QA], seed, recent), None
        ans = next(x[1] for x in KU_QA if x[0] == q)
    else:
        _, _, _, q, ans = pick_qa(it, recent, seed)
    fmt = dict(type=t, spec=spec, spec1=spec1, price=price)
    if form == 'discover':
        sc = [s for s in DISC_SCENE if s[1] == portable]  # 持ち歩く物は外の場面、置く物は家の場面
        fmt['scene'] = pick_fresh([s[0] for s in sc], seed, recent)
        fmt['verb'] = '連れていきたい' if portable else '置きたい' if t not in ('コードレス掃除機', 'ロボット掃除機', '水拭きクリーナー', 'ドライヤー') else '使いたい'
    if form == 'n3':
        pn = price_num(price)
        units = [u for u in N3_UNITS if pn >= u[2]]
        fmt['u'], fmt['c'], fmt['base'] = units[seed % len(units)]
        n = pn / fmt['base']
        fmt['cnt'] = f'{n:.0f}' if n >= 10 else f'{n:.1f}'.rstrip('0').rstrip('.')
        if '〜' in price:
            fmt['price'] = price.replace('〜', 'から')
    line3 = pf(QA_LINE[form], 2).format(**fmt)
    close = pf(QA_CLOSE, 3)
    # 10/27：人間らしく。basic は「返信に置いておきます」の宣伝行を入れず、会話だけにする（商品は返信で十分伝わる）
    body = [q, ans] if form == 'basic' else [q, ans, line3.rstrip('👇').rstrip()]
    if not re.search(r'(？|\?)$', body[-1]):
        body.append(close)
    text = '\n'.join(body)
    text = clip(text + '\n\n' + PR_LINE, 490)
    reply = f"【PR】今日の1品はこちら👇\n{it['name']}\n{price}{'・送料無料' if free_ship(it) else ''}\n楽天ROOM：{ROOM_URL}"
    qid = stamp.strftime('%Y%m%d-%H%M') + '-' + a.slot
    title = ('今夜の1品' if a.slot == 'night' else '今朝の1品') if form == 'basic' else TITLES.get(form, '今日の1品')
    q = {'id': qid, 'slot': a.slot, 'form': form, 'kind': 'talk' if a.slot == 'noon' else 'single', 'created': stamp.isoformat(timespec='minutes'),
         'title': title, 'footer': pick(FOOTERS, seed), 'topic': 'ガジェット' if cat_of(it, it.get('_gid', '')) in ('gadget', 'kaden') else '楽天ROOM',
         'text': text, 'reply': reply,
         'items': [{'itemcode': it['itemcode'], 'name': it['name'], 'hook': it.get('hook', ''), 'price': price, 'quip': it.get('quip', ''), 'points': facts}]}
    write_q(a, q, f'{form} 1件')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--html', required=True)
    ap.add_argument('--posts', required=True)
    ap.add_argument('--repo', required=True)
    ap.add_argument('--slot', choices=SLOTS, default='night')
    ap.add_argument('--form', choices=sorted(ALL_FORMS), default=None, help='形を指定（使えないときは自動で選ぶ）')
    ap.add_argument('--force', action='store_true', help='同じ時間帯の投稿が今日すでにあっても作る（削除後の出し直し用）')
    a = ap.parse_args()
    if not a.force and slot_done(a.repo, a.slot):
        print('なし（今日のこの時間帯はもう投稿済み）')
        return
    if a.slot == 'late':
        return late(a)
    has_data = os.path.isfile(a.html) and os.path.getsize(a.html) > 0
    cands = gather(a) if has_data else []
    singles = [it for it in cands if it.get('quip') and 'やつ' not in it.get('quip', '')]
    feasible = {'talk'} if a.slot == 'noon' else set()
    if len(singles) >= 2:
        feasible.add('summary')
    if singles:
        feasible.add('basic')
    if a.slot == 'night' and datetime.now(JST).weekday() == 4:
        feasible.add('n12')
    for fm in ('discover', 'n1', 'n5', 'n2', 'kuyou', 'n11', 'n3'):
        if any(single_ok(it, fm) for it in singles):
            feasible.add(fm)
    seed = h31(datetime.now(JST).strftime('%Y%m%d') + a.slot)
    form = a.form if (a.form in FORMS[a.slot] and a.form in feasible) else choose_form(a.repo, a.slot, feasible, seed)
    if 'n12' in feasible and not a.form:
        form = 'n12'  # 金曜の夜は「今週買わずに耐えたもの発表会」
    if not form:
        print('なし')
        return
    if form == 'talk':
        return talk(a.repo)
    if form == 'summary':
        return summary(a, cands)
    if form == 'n12':
        return n12(a)
    rec = recent_texts(a.repo)
    ok = [x for x in singles if single_ok(x, form)]
    # 10/27：情報収集（state/research.json の hot_words）で今話題の種類・ブランドを先に使う
    try:
        hot = json.load(open(os.path.join(a.repo, 'state', 'research.json'), encoding='utf-8')).get('hot_words', [])
    except Exception:
        hot = []
    if hot:
        ok.sort(key=lambda x: not any(w and w.lower() in (x.get('name', '') + x.get('hook', '')).lower() for w in hot))
    it = next((x for x in ok if type_of(x)[0] not in rec), ok[0])
    return single(a, form, it)


if __name__ == '__main__':
    main()
