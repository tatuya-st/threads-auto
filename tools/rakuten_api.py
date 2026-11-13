#!/usr/bin/env python3
"""楽天ウェブサービス（楽天API）の小さな道具（11/14 マスター指示「楽天API：全部」）。

使い方:
  python3 tools/rakuten_api.py item <shop:12345>          … 1商品の今の価格・送料・在庫・レビューを表示
  python3 tools/rakuten_api.py check queue/<id>.json       … queue の商品を確かめ、価格・送料の数字を最新に直す（--write で保存）
  python3 tools/rakuten_api.py ranking [--genre 562637] [--out state/rakuten_candidates.json]
                                                            … ランキングから ROOM に載せる候補を作る

環境変数（GitHub の Secrets に登録）:
  RAKUTEN_APP_ID      … アプリID（applicationId）
  RAKUTEN_ACCESS_KEY  … アクセスキー（accessKey。2026年の新しい商品検索APIで必須）
どちらも無いときは何もしない（今までどおり動く）。

公式の仕様（2026-07-01版の商品検索API）：
  https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701
  itemPrice（価格）・postageFlag（0=送料込み）・availability（0=在庫なし）・reviewCount・reviewAverage・pointRate
"""
import json, os, re, sys, time, urllib.parse, urllib.request

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
SEARCH_URLS = [
    'https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701',
    'https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601',
]
RANKING_URLS = [
    'https://openapi.rakuten.co.jp/ichibaranking/api/IchibaItem/Ranking/20220601',
    'https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20220601',
]
GADGET_GENRE = 562637  # 家電（楽天市場のジャンルID）。スマホ周りは 560029 など、--genre で変えられる


def ready():
    return bool(os.environ.get('RAKUTEN_APP_ID'))


def _get(urls, params):
    """候補のURLを順に試す。同じ要求を短時間にくり返さない（公式の注意）ため、1つのURLは1回だけ。"""
    app = os.environ.get('RAKUTEN_APP_ID', '')
    key = os.environ.get('RAKUTEN_ACCESS_KEY', '')
    p = dict(params, applicationId=app, format='json', formatVersion=2)
    if key:
        p['accessKey'] = key
    last = None
    for u in urls:
        req = urllib.request.Request(u + '?' + urllib.parse.urlencode(p), headers={'User-Agent': 'threads-auto'})
        if key:
            req.add_header('accessKey', key)
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            last = f'HTTP {e.code} {e.read()[:200].decode("utf-8", "replace")}'
            if e.code == 429:
                break
        except Exception as e:  # 通信の失敗は止めずに次へ
            last = str(e)
        time.sleep(1)
    raise RuntimeError(f'楽天APIに接続できません：{last}')


def item(code):
    """itemCode（shop:12345）から今の情報を返す。見つからなければ None。"""
    d = _get(SEARCH_URLS, {'itemCode': code, 'hits': 1})
    its = d.get('Items') or d.get('items') or []
    if not its:
        return None
    it = its[0].get('Item', its[0]) if isinstance(its[0], dict) else its[0]
    return {
        'itemcode': it.get('itemCode'),
        'name': it.get('itemName'),
        'price': it.get('itemPrice'),
        'postage_free': it.get('postageFlag') == 0,
        'available': it.get('availability', 1) != 0,
        'review_count': it.get('reviewCount'),
        'review_avg': it.get('reviewAverage'),
        'point_rate': it.get('pointRate'),
        'url': it.get('itemUrl'),
    }


def yen(n):
    return f'{int(n):,}円'


def refresh_queue(q):
    """queue の商品を楽天APIで確かめる。戻り値 (q, notes, stop)。
    stop に理由が入ったら出さない（在庫切れ・商品が見つからない）。
    価格は queue の price が「N円」ちょうど（〜なし）のときだけ本文・返信の同じ文字を新しい価格に直す。
    送料が無料でなくなっていたら「送料無料」の文字を外す。API が使えないときは何も変えない。"""
    notes, stop = [], None
    if not ready() or not q.get('items'):
        return q, notes, stop
    for it in q['items']:
        code = it.get('itemcode')
        if not code:
            continue
        try:
            now = item(code)
        except Exception as e:
            notes.append(f'{code}：確認できず（{e}）。今までどおり出す')
            continue
        if now is None:
            stop = f'楽天で商品が見つからない（{code}）'
            break
        if not now['available']:
            stop = f'在庫切れ（{code}）'
            break
        old = (it.get('price') or '').strip()
        if now['price'] and re.fullmatch(r'[\d,]+円', old) and old != yen(now['price']):
            new = yen(now['price'])
            for k in ('text', 'reply'):
                if q.get(k):
                    q[k] = q[k].replace(old, new)
            it['price'] = new
            notes.append(f'{code}：価格 {old} → {new}')
        elif now['price'] and old and '〜' in old and old.replace('〜', '') != yen(now['price']):
            notes.append(f'{code}：表示 {old}、APIの価格 {yen(now["price"])}（〜つきなので本文はそのまま）')
        if not now['postage_free']:
            for k in ('text', 'reply'):
                if q.get(k) and '送料無料' in q[k]:
                    q[k] = re.sub(r'[・／/ ]?送料無料', '', q[k])
                    notes.append(f'{code}：送料無料でなくなったので文字を外した')
    return q, notes, stop


def ranking(genre=GADGET_GENRE, pages=1):
    out = []
    for pg in range(1, pages + 1):
        d = _get(RANKING_URLS, {'genreId': genre, 'page': pg})
        for it in d.get('Items') or d.get('items') or []:
            it = it.get('Item', it)
            out.append({
                'rank': it.get('rank'), 'itemcode': it.get('itemCode'), 'name': it.get('itemName'),
                'price': it.get('itemPrice'), 'review_count': it.get('reviewCount'),
                'review_avg': it.get('reviewAverage'), 'url': it.get('itemUrl'), 'shop': it.get('shopName'),
            })
        time.sleep(1)
    return out


def used_codes():
    codes = set()
    p = os.path.join(ROOT, 'state', 'sent.json')
    if os.path.exists(p):
        codes |= set(json.load(open(p, encoding='utf-8')))
    return codes


def main(a):
    if not a:
        print(__doc__)
        return
    if not ready():
        print('RAKUTEN_APP_ID が無いので楽天APIは使いません（Secrets に登録すると動きます）')
        return
    if a[0] == 'item':
        print(json.dumps(item(a[1]), ensure_ascii=False, indent=1))
    elif a[0] == 'check':
        f = a[1]
        q = json.load(open(f, encoding='utf-8'))
        q, notes, stop = refresh_queue(q)
        print('\n'.join(notes) or '数字の変化なし')
        if stop:
            print('出さない理由：' + stop)
        if '--write' in a:
            json.dump(q, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        sys.exit(3 if stop else 0)
    elif a[0] == 'ranking':
        g = int(a[a.index('--genre') + 1]) if '--genre' in a else GADGET_GENRE
        out = a[a.index('--out') + 1] if '--out' in a else os.path.join(ROOT, 'state', 'rakuten_candidates.json')
        used = used_codes()
        rows = [r for r in ranking(g, 2) if r['itemcode'] not in used and (r['review_count'] or 0) >= 100]
        json.dump({'genre': g, 'at': time.strftime('%Y-%m-%dT%H:%M%z'), 'items': rows[:30]},
                  open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'候補 {len(rows[:30])} 件 → {out}')


if __name__ == '__main__':
    main(sys.argv[1:])
