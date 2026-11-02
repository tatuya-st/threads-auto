#!/usr/bin/env python3
"""マスターがMUSEで作った画像を、夜の商品投稿の画像に入れる（ルイが訂正してから投稿する用）。
使い方: python3 tools/apply_photo.py queue/<id>.json <画像1> [<画像2>] [ひと言]
- 画像を2枚渡すと2枚投稿（1枚目と2枚目で別の女性。同じ人に見えたら使わない）
- 投稿画像まるごと（縦長）なら、場面の部分だけを切り出して使う
- 場面の写真（横長など）なら、場面の枠に合わせて切り抜く
- 【PR】表記・商品名・価格・「実際の商品とは異なります」は、ルイの正しい情報で入れ直す
- 結果は assets/photos/<id>.jpg と images/<id>.png。queue の photo を書きかえる"""
import json, os, sys
from PIL import Image

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
PW, PH = 1080, 900  # レイ風：写真が主役（上の約3分の2）


def panel(src):
    im = Image.open(src).convert('RGB')
    w, h = im.size
    if h / w > 1.1:  # 縦長の写真はそのまま画面いっぱいに使う
        im.thumbnail((1080, 1350 * 2))
        return im
    r = PW / PH
    if w / h > r:
        nw = int(h * r); im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = int(w / r); im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    return im.resize((PW, PH), Image.LANCZOS)


def main():
    qp, src = sys.argv[1], sys.argv[2]
    q = json.load(open(qp, encoding='utf-8'))
    os.makedirs(os.path.join(ROOT, 'assets', 'photos'), exist_ok=True)
    rel = f"assets/photos/{q['id']}.jpg"
    panel(src).save(os.path.join(ROOT, rel), quality=92)
    q['photo'] = rel
    q.pop('hold', None)
    from datetime import datetime, timezone, timedelta
    q['released'] = datetime.now(timezone(timedelta(hours=9))).isoformat(timespec='minutes')
    rest = sys.argv[3:]
    if rest and os.path.isfile(rest[0]):
        rel2 = f"assets/photos/{q['id']}_2.jpg"
        panel(rest.pop(0)).save(os.path.join(ROOT, rel2), quality=92)
        q['photo2'] = rel2
    if rest:
        q['photo_line'] = rest[0]
    json.dump(q, open(qp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import render
    out = os.path.join(ROOT, 'images', q['id'] + '.png')
    render.render_scene(q, out)
    print(out)
    if q.get('photo2'):
        out2 = os.path.join(ROOT, 'images', q['id'] + '_2.png')
        render.render_scene(render.second(q), out2)
        print(out2)


if __name__ == '__main__':
    main()
