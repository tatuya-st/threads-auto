#!/usr/bin/env python3
"""マスターがMUSEで作った画像を、夜の商品投稿の画像に入れる（ルイが訂正してから投稿する用）。
使い方: python3 tools/apply_photo.py queue/<id>.json <マスターの画像> [吹き出しのひと言]
- 投稿画像まるごと（縦長）なら、場面の部分だけを切り出して使う
- 場面の写真（横長など）なら、場面の枠に合わせて切り抜く
- 【PR】表記・商品名・価格・「実際の商品とは異なります」は、ルイの正しい情報で入れ直す
- 結果は assets/photos/<id>.jpg と images/<id>.png。queue の photo を書きかえる"""
import json, os, sys
from PIL import Image

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
PW, PH = 860, 500


def panel(src):
    im = Image.open(src).convert('RGB')
    w, h = im.size
    if h / w > 1.1:  # 投稿画像まるごと（1080×1350 の比）→ 場面の位置（110,305〜970,805）を切り出す
        s = w / 1080
        im = im.crop((int(118 * s), int(313 * s), int(962 * s), int(797 * s)))
        w, h = im.size
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
    if len(sys.argv) > 3:
        q['photo_line'] = sys.argv[3]
    json.dump(q, open(qp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import render
    out = os.path.join(ROOT, 'images', q['id'] + '.png')
    render.render_scene(q, out)
    print(out)


if __name__ == '__main__':
    main()
