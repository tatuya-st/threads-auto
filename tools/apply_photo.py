#!/usr/bin/env python3
"""マスターがMUSEで作った画像を、夜の商品投稿の画像に入れる（ルイが訂正してから投稿する用）。
使い方: python3 tools/apply_photo.py queue/<id>.json <画像1> [<画像2>] [ひと言]
　　　　python3 tools/apply_photo.py --asis queue/<id>.json <仕上がり1枚目> <仕上がり2枚目>（11/16からの統一型。文字を足さない）
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


def asis(qp, srcs):
    """11/15 マスター決定（IGとThreadsの型統一・11/16から）：楓の仕上がり2枚（1枚目＝商品だけ＋縦書きコピー／2枚目＝3人の日替わり出演＋確認ポイント帯）を
    文字を足さずにそのまま入れる。比率は4:5（1080×1350）にそろえる。検品に合格した画像だけに使う。"""
    if len(srcs) != 2:
        sys.exit('--asis は画像を2枚渡してください（1枚目＝商品だけ＋縦書きコピー、2枚目＝出演＋確認ポイント帯）')
    q = json.load(open(qp, encoding='utf-8'))
    outs = []
    for i, s in enumerate(srcs):
        im = Image.open(s).convert('RGB')
        w, h = im.size
        if not (1.0 <= h / w <= 1.26):
            sys.exit(f'{s} の比率が4:5以内ではありません（{w}×{h}）')
        im = im.resize((1080, int(1080 * h / w)))
        rel = f"images/{q['id']}{'' if i == 0 else '_2'}.png"
        im.save(os.path.join(ROOT, rel))
        outs.append(rel)
    q['photo'], q['photo2'], q['asis'] = outs[0], outs[1], True
    q.pop('hold', None)
    from datetime import datetime, timezone, timedelta
    q['released'] = datetime.now(timezone(timedelta(hours=9))).isoformat(timespec='minutes')
    json.dump(q, open(qp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('\n'.join(outs))


def main():
    if '--asis' in sys.argv:
        a = [x for x in sys.argv[1:] if x != '--asis']
        return asis(a[0], a[1:])
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
    # 11/12 マスター指示：画像には必ずキャッチコピーを入れる。無ければ入れずに止める
    it0 = q['items'][0] if q.get('items') else {}
    if not (q.get('photo_line') or it0.get('hook')):
        sys.exit('キャッチコピーがありません。apply_photo.py の最後にひと言（キャッチコピー）を渡してください')
    if q.get('photo2') and not (it0.get('quip') or it0.get('points')):
        sys.exit('2枚目のキャッチコピー（quip か points）がありません')
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
