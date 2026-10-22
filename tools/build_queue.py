#!/usr/bin/env python3
"""投稿ノートのデータから、Threads のまとめ投稿（3件・画像つき）を1本作って queue/ に置く。

使い方:
  python3 tools/build_queue.py --html <投稿ノートの保存HTML> --posts <posts を保存したフォルダ> --repo <このリポジトリ> --slot morning|night

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
    'base': dict(re=None, name_only=False,
        title=['財布「やめて」私「見るだけ」', '物欲、フル充電完了', 'ポチる前の作戦会議', 'カート反復横跳びの成果'],
        open=lambda n: [f'財布「やめて」\n私「見るだけだから」\n\n…という言い訳つきの{n}選です👇', f'ランキングを見すぎて、楽天ポイントが夢に出てきた男の{n}選です', f'物欲のみなさん、お疲れさまです。\n本日の議題は{n}件。異議なしで可決されそうです🫡', f'「何も買わない日」を作ろうとした結果、\n気になるものが{n}つ増えました🔍', f'カートに入れては消す反復横跳び、今日も元気にやってます。\n本日の候補{n}つ👇', f'寝る前の楽天パトロール、本日の成果{n}件です🌙'],
        ask=['あなたなら何番？番号だけのリプでも喜びます👇', '「うちもそれ困ってる」って人はリプで教えてください😂', 'この中で一番気になるの、何番ですか？👇']),
}
MORNING_OPEN = lambda n: [f'通勤中のみなさん、おはようございます。\n今日の物欲会議、議題は{n}件です🫡', f'朝の満員電車で見る用の{n}選です🚃\n買うかどうかは帰ってから決めてOK', f'おはようございます。\n寝ぼけたまま楽天パトロールした成果{n}件です☕']
LINK_LINES = ['詳細はプロフィールのリンクから🔍', '保存しておくと、あとで探さずに済みます📌\n詳細はプロフィールのリンクから', '迷ったらカートで一晩寝かせるのがおすすめ💤\n詳細はプロフィールのリンクから', '見るだけでも大歓迎👀 プロフィールのリンクから楽天ROOMへ']
FOOTERS = ['▶ 財布と相談のうえ、プロフィールのリンクから', '▶ 見るだけでもどうぞ。プロフィールのリンクから楽天ROOMへ', '▶ レビューも見てから決めてね（プロフィールのリンクから）', '▶ 気になった番号はリプで教えてね（詳細はプロフのリンク）']
AXES = {
    'jitan': dict(label='時短', kw=re.compile(r'時短|自動|タイマー|上から給水|置くだけ|工事不要|急速|ワンタッチ|ボタン|洗える|すぐ|まとめて|一度に|手軽'), title=['時短で選ぶ3つ', '家事も充電も、時短したい人へ'], open='今日は「時短」目線で{n}つ。'),
    'cospa': dict(label='コスパ', kw=re.compile(r'送料無料|セット|\d個|個入|×\s*\d|大容量|まとめ買い|ポイント\d+倍|\d+円以下|ポッキリ|訳あり|\d+ロール|\d+袋'), title=['コスパで選ぶ3つ', '財布と相談済みの3つ'], open='今日は「コスパ」目線で{n}つ。'),
    'look': dict(label='見た目', kw=re.compile(r'色|カラー|デザイン|ガラス|木目|ウォールナット|ホワイト|ブラック|マット|インテリア|陶器|鉢|薄型|スリム|モコモコ'), title=['見た目で選ぶ3つ', '置くだけで部屋が整う3つ'], open='今日は「見た目」目線で{n}つ。'),
    'trust': dict(label='口コミ', kw=re.compile(r'レビュー|公式|正規|1位|人気|いいね'), title=['口コミで選ぶ3つ', 'レビューが背中を押す3つ'], open='今日は「口コミ」目線で{n}つ。'),
}
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
    for k in ('apple', 'winter', 'refill'):
        T = THEMES[k]
        n = sum(1 for it in items if T['re'].search(it['name'] if T['name_only'] else ' '.join([it['name'], it.get('hook', '')] + it.get('points', []))))
        if n > bn:
            best, bn = k, n
    return best


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--html', required=True)
    ap.add_argument('--posts', required=True)
    ap.add_argument('--repo', required=True)
    ap.add_argument('--slot', choices=['morning', 'night'], default='night')
    a = ap.parse_args()

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
        sc = proven if proven is not None else (0 if c in ('gadget', 'kaden') else 1) if 0 < p <= 10000 else 2 if 0 < p <= 30000 else 3
        it['_c'] = c
        cands.append((sc, -likes, -it['_t'], it))
    cands.sort(key=lambda x: x[:3])
    items, seen = [], set()
    for *_, it in cands:
        k = norm(it['name'])
        if k in seen:
            continue
        # quip（ひと言）が無い・「やつ」を含む・重複する商品は使わない
        q = it.get('quip') or ''
        if not q or 'やつ' in q or any(q == o.get('quip') for o in items):
            continue
        seen.add(k)
        items.append(it)
        if len(items) == PER_POST:
            break
    if len(items) < 2:
        print('なし')
        return

    n = len(items)
    dn = int(now // 864e5) * 2 + (0 if a.slot == 'morning' else 1)
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
    opens = MORNING_OPEN(n) if (a.slot == 'morning' and th == 'base') else T['open'](n)
    hook = pick(opens, dn)
    ask = pick(T['ask'], dn * 3 + 1)
    link_line = pick(LINK_LINES, dn * 7 + 2)
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
        return f"【PR・楽天ROOM】\n{hook}\n\n{axl}{body(with_ax)}\n\n{ask}\n{link_line if with_link else '詳細はプロフィールのリンクから'}\n{link}\n※価格は投稿時点のものです"

    text = build(True, True)
    if len(text) > 490:
        text = build(False, True)
    if len(text) > 490:
        text = build(False, False)
    text = clip(text, 490)

    stamp = datetime.now(JST)
    qid = stamp.strftime('%Y%m%d-%H%M') + '-' + a.slot
    q = {
        'id': qid, 'slot': a.slot, 'created': stamp.isoformat(timespec='minutes'),
        'title': title, 'footer': footer, 'axis': ax, 'theme': th, 'topic': topic, 'text': text,
        'items': [{'itemcode': it['itemcode'], 'name': it['name'], 'hook': it.get('hook', ''), 'price': it.get('price', ''), 'quip': it.get('quip', '')} for it in items],
    }
    os.makedirs(os.path.join(a.repo, 'queue'), exist_ok=True)
    with open(os.path.join(a.repo, 'queue', qid + '.json'), 'w', encoding='utf-8') as f:
        json.dump(q, f, ensure_ascii=False, indent=1)
    print(f'{qid} {n}件')


if __name__ == '__main__':
    main()
