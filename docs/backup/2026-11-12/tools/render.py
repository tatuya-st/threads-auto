#!/usr/bin/env python3
"""queue/<id>.json から 1080×1350 の画像（images/<id>.png）を作る。
3件まとめ（投稿ノートの「まとめてThreadsへ」と同じデザイン）と、商品1件の形（kind: single）の2種類。
どの画像にも右下の隅に「財布欠席くん」（ルイのオリジナル）が小さく入る。"""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
ACC, INK, MUTED, SUB, LINE = '#b0581a', '#221a2b', '#6c6475', '#8a7f73', '#eadfd2'
HERE = os.path.dirname(os.path.abspath(__file__))
FD = os.path.join(HERE, '..', 'fonts')
FALLBACK = {
    'bold': ['/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'],
    'medium': ['/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc', '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'],
    'display': ['/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc'],
}
FILES = {'bold': 'ZenKakuGothicNew-Bold.ttf', 'medium': 'ZenKakuGothicNew-Medium.ttf', 'display': 'DelaGothicOne-Regular.ttf'}
_cache = {}


def font(kind, size):
    k = (kind, size)
    if k not in _cache:
        paths = [os.path.join(FD, FILES[kind])] + FALLBACK[kind]
        for p in paths:
            try:
                _cache[k] = ImageFont.truetype(p, size, index=0)
                break
            except Exception:
                continue
        else:
            raise SystemExit('日本語フォントが見つかりません')
    return _cache[k]


def tw(d, s, f):
    return d.textlength(s, font=f)


def wrap(d, text, f, maxw, maxlines):
    out, line = [], ''
    for ch in str(text or ''):
        if tw(d, line + ch, f) > maxw:
            out.append(line)
            line = ch
            if len(out) == maxlines:
                break
        else:
            line += ch
    if len(out) < maxlines and line:
        out.append(line)
    if len(out) == maxlines and tw(d, out[-1], f) > maxw - 40:
        out[-1] = out[-1][:-1] + '…'
    return out


def fit(d, s, kind, size, maxw, minsize):
    while size > minsize and tw(d, s, font(kind, size)) > maxw:
        size -= 1
    return font(kind, size)


def text(d, xy, s, f, fill, anchor='ls'):
    d.text(xy, s, font=f, fill=fill, anchor=anchor)


def render(q, out):
    im = Image.new('RGB', (W, H), '#fdf1e2')
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((60, 60, W - 60, H - 60), 48, fill='#ffffff')
    # 【PR】楽天ROOM の帯（文字幅に合わせる）
    fb = font('bold', 38)
    t = '【PR】楽天ROOM'
    bw = int(tw(d, t, fb)) + 64
    d.rounded_rectangle((110, 110, 110 + bw, 180), 35, fill=ACC)
    text(d, (142, 147), t, fb, '#ffffff', 'lm')
    text(d, (W - 110, 155), '※価格は投稿時点のものです', font('medium', 28), SUB, 'rs')
    text(d, (110, 280), q['title'], fit(d, q['title'], 'display', 60, W - 220, 40), INK)
    items = q['items']
    top, bottom = 330, 1130
    rh = (bottom - top) / len(items)
    for i, it in enumerate(items):
        y0 = top + i * rh
        if i:
            d.line((110, y0, W - 110, y0), fill=LINE, width=3)
        text(d, (110, y0 + rh / 2 + 20), str(i + 1), font('display', 56), ACC)
        fh, fn = font('bold', 40), font('medium', 29)
        hl = wrap(d, it.get('hook') or it['name'], fh, W - 310, 2)
        nl = wrap(d, it['name'], fn, W - 310, 2) if it.get('hook') else []
        h = len(hl) * 52 + len(nl) * 40 + 70
        y = y0 + (rh - h) / 2 + 40
        for l in hl:
            text(d, (190, y), l, fh, INK)
            y += 52
        for l in nl:
            text(d, (190, y - 6), l, fn, MUTED)
            y += 40
        fp = font('display', 50)
        price = str(it.get('price', ''))
        text(d, (190, y + 22), price, fp, ACC)
        quip = it.get('quip') or ''
        if quip:
            px = 190 + tw(d, price, fp) + 28
            mx = W - 110 - px
            fq = fit(d, '← ' + quip, 'medium', 30, mx, 20)
            if tw(d, '← ' + quip, fq) <= mx:
                text(d, (px, y + 18), '← ' + quip, fq, SUB)
    text(d, (110, 1240), q['footer'], fit(d, q['footer'], 'medium', 34, FOOT_W, 22), MUTED)
    draw_saifu(im)
    im.save(out, optimize=True)


FOOT_W = 700  # 下の一言の最大幅（右下の財布欠席くんに重ならない）

# ───────── 財布欠席くん（ルイのオリジナル）─────────
# いつも同じ形・色・大きさ・位置（横幅の約14%、カードの右下の隅）。供養投稿だけ札が「見送り」になり、線香が付く
SAIFU_W, SAIFU_H = 150, 140
SAIFU_XY = (W - 60 - 18 - SAIFU_W, H - 60 - 12 - SAIFU_H)
S_BODY, S_EDGE, S_FLAP, S_IN = '#a0632e', '#5b3415', '#8a5226', '#f4e6d3'


def draw_saifu(im, variant='kesseki'):
    return  # 11/11 マスター指示：財布欠席くんは旧ROOMのものなので使わない
    k = 4  # 4倍で描いて縮小（線をなめらかに）
    c = Image.new('RGBA', (SAIFU_W * k, SAIFU_H * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(c)

    def P(*xy):
        return [v * k for v in xy]
    miokuri = variant == 'miokuri'
    # 線香（供養のときだけ）：細い棒と煙の曲線1本
    if miokuri:
        d.rectangle(P(30, 92, 33, 132), fill='#6b4f2a')
        d.ellipse(P(28.5, 89, 34.5, 95), fill='#d9481c')
        pts = [(31.5 + 4 * __import__('math').sin(t / 3.0), 88 - t) for t in range(0, 30)]
        d.line([(x * k, y * k) for x, y in pts], fill='#9a9a9a', width=2 * k, joint='curve')
    # 腕と札
    sx0, sx1 = (2, 74) if miokuri else (6, 62)
    d.line(P(66, 96, (sx0 + sx1) / 2 + 6, 50), fill=S_EDGE, width=3 * k)
    d.rounded_rectangle(P(sx0, 16, sx1, 52), radius=4 * k, fill='#ffffff', outline=S_EDGE, width=3 * k)
    label = '見送り' if miokuri else '欠席'
    f = font('bold', (18 if miokuri else 21) * k)
    d.text(((sx0 + sx1) / 2 * k, 34 * k), label, font=f, fill='#221a2b', anchor='mm')
    # 財布のふた（少し開いて、中は空っぽ＝薄い色だけ）
    d.polygon(P(66, 70, 144, 70, 137, 50, 73, 50), fill=S_FLAP, outline=S_EDGE)
    d.line(P(66, 70, 73, 50, 137, 50, 144, 70), fill=S_EDGE, width=3 * k)
    d.polygon(P(70, 70, 140, 70, 135, 58, 75, 58), fill=S_IN)
    # 体（角の丸い長方形・ふちに濃い茶色の線）
    d.rounded_rectangle(P(62, 68, 148, 134), radius=12 * k, fill=S_BODY, outline=S_EDGE, width=3 * k)
    # 目（白目に黒い点）と、への字の口
    for ex in (90, 120):
        d.ellipse(P(ex - 8, 86, ex + 8, 102), fill='#ffffff', outline=S_EDGE, width=2 * k)
        d.ellipse(P(ex - 3.5, 91, ex + 3.5, 98), fill='#111111')
    d.line(P(97, 120, 105, 113, 113, 120), fill=S_EDGE, width=3 * k, joint='curve')
    c = c.resize((SAIFU_W, SAIFU_H), Image.LANCZOS)
    im.paste(c, SAIFU_XY, c)


def render_single(q, out):
    """商品1件の形（朝の会話・発見型・逆レビュー・供養など）。"""
    im = Image.new('RGB', (W, H), '#fdf1e2')
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((60, 60, W - 60, H - 60), 48, fill='#ffffff')
    fb = font('bold', 38)
    t = '【PR】楽天ROOM'
    bw = int(tw(d, t, fb)) + 64
    d.rounded_rectangle((110, 110, 110 + bw, 180), 35, fill=ACC)
    text(d, (142, 147), t, fb, '#ffffff', 'lm')
    text(d, (W - 110, 155), '※価格は投稿時点のものです', font('medium', 28), SUB, 'rs')
    text(d, (110, 290), q['title'], fit(d, q['title'], 'display', 72, W - 220, 40), INK)
    d.line((110, 330, W - 110, 330), fill=LINE, width=3)
    it = q['items'][0]
    y = 420
    fh = font('bold', 50)
    for l in wrap(d, it.get('hook') or it['name'], fh, W - 220, 3):
        text(d, (110, y), l, fh, INK)
        y += 66
    fn = font('medium', 30)
    if it.get('hook'):
        for l in wrap(d, it['name'], fn, W - 220, 2):
            text(d, (110, y + 4), l, fn, MUTED)
            y += 42
    y += 96
    price = str(it.get('price', ''))
    text(d, (110, y), price, fit(d, price, 'display', 84, W - 220, 50), ACC)
    y += 70
    if it.get('quip'):
        fq = fit(d, it['quip'], 'medium', 36, W - 220, 24)
        text(d, (110, y), it['quip'], fq, SUB)
        y += 40
    pts = [p for p in it.get('points', []) if p][:3]
    if q.get('serif'):  # N9：商品が吹き出しで喋る（ルイのオリジナルの配色。しっぽは左上の商品の文へ向ける）
        y += 50
        fs = font('bold', 44)
        lines = wrap(d, q['serif'], fs, W - 340, 3)
        bh = 70 + 62 * len(lines)
        x0, x1 = 110, W - 110
        d.polygon([(170, y + 4), (230, y + 4), (150, y - 40)], fill=ACC)
        d.rounded_rectangle((x0, y, x1, y + bh), 44, fill='#fff7ee', outline=ACC, width=6)
        d.polygon([(176, y + 7), (224, y + 7), (157, y - 28)], fill='#fff7ee')
        for i, l in enumerate(lines):
            text(d, (x0 + 50, y + 78 + 62 * i), l, fs, INK)
        pts = []
    if pts:
        y += 30
        box_h = 40 + 62 * len(pts)
        d.rounded_rectangle((110, y, W - 110, y + box_h), 28, fill='#fbf3ea')
        fp = font('bold', 38)
        for i, p in enumerate(pts):
            s = '・' + p
            text(d, (150, y + 70 + 62 * i), s, fit(d, s, 'bold', 38, W - 300, 24), INK)
    text(d, (110, 1240), q['footer'], fit(d, q['footer'], 'medium', 34, FOOT_W, 22), MUTED)
    draw_saifu(im, 'miokuri' if q.get('form') == 'kuyou' else 'kesseki')
    im.save(out, optimize=True)


def _cover(img, w, h):
    iw, ih = img.size
    r = w / h
    if iw / ih > r:
        nw = int(ih * r); img = img.crop(((iw - nw) // 2, 0, (iw - nw) // 2 + nw, ih))
    else:
        nh = int(iw / r); img = img.crop((0, (ih - nh) // 2, iw, (ih - nh) // 2 + nh))
    return img.resize((w, h), Image.LANCZOS)


def _scene_photo(q, it):
    """場面の写真を選ぶ：マスターのMUSE写真 → 財布欠席くんの場面写真 → 買い物かごの場面。"""
    import scenes
    if q.get('photo'):
        return Image.open(os.path.join(HERE, '..', q['photo'])).convert('RGB')
    base = os.path.join(HERE, '..', 'assets', 'scenes')
    sc = q.get('scene') or scenes.pick(it, q)
    name = sc if scenes.season_chara() == 'saifu' else 'ghost_' + sc
    for n in ():  # 11/11 マスター指示：旧ROOMのキャラの場面写真（財布欠席くん・おばけ）は使わない
        f = os.path.join(base, str(n) + '.jpg')
        if os.path.exists(f):
            return Image.open(f).convert('RGB')
    return Image.new('RGB', (860, 500), '#e9e2d8')


def second(q):
    """2枚目：写真を2枚目（別の女性）にし、見出しを推しポイントのひと言に変える。"""
    q2 = json.loads(json.dumps(q))
    q2['photo'] = q['photo2']
    it = q2['items'][0]
    pts = it.get('points') if isinstance(it.get('points'), list) else []
    alt = it.get('quip') or (pts[0] if pts else None)
    if alt:
        it['hook'] = alt
    q2.pop('photo_line', None)  # 2枚目は推しポイントのひと言をキャッチコピーにする
    return q2


def render_scene(q, out):
    """レイ風（2026-11-03 マスター指示）：写真が主役・文字は少なく・広告のデザイン。
    上の約3分の2を写真が端まで占め、下に短い一言と価格だけ。実在の人が使った写真のふりはしない。"""
    it = q['items'][0]
    im = Image.new('RGB', (W, H), '#ffffff')
    from PIL import ImageFilter
    PHH = 880
    ph = _scene_photo(q, it)
    if ph.size[1] / ph.size[0] > 1.1:  # 縦長の写真は画面いっぱいに
        PHH = H
        im.paste(_cover(ph, W, H), (0, 0))
    else:
        # 写真は切らずに横幅いっぱい。上下はぼかした同じ写真で埋める（吹き出しや絵が欠けない）
        im.paste(_cover(ph, W, PHH).filter(ImageFilter.GaussianBlur(28)), (0, 0))
        fh2 = 720  # 少しだけ拡大（左右を数%だけ切る）して写真を大きく
        fw = int(ph.size[0] * fh2 / ph.size[1])
        big = ph.resize((fw, fh2), Image.LANCZOS)
        if fw > W:
            big = big.crop(((fw - W) // 2, 0, (fw - W) // 2 + W, fh2)); fw = W
        im.paste(big, ((W - fw) // 2, 130))
        PHH = 130 + fh2 + 40
        im.paste(Image.new('RGB', (W, H - PHH), '#ffffff'), (0, PHH))
    # 写真の下を白へなじませる
    if PHH < H:
        g = Image.new('L', (1, 160))
        for y in range(160):
            g.putpixel((0, y), int(255 * (y / 159) ** 1.6))
        im.paste(Image.new('RGB', (W, 160), '#ffffff'), (0, PHH - 160), g.resize((W, 160)))
    else:
        g = Image.new('L', (1, 620))
        for y in range(620):
            g.putpixel((0, y), int(235 * (y / 619) ** 1.3))
        im.paste(Image.new('RGB', (W, 620), '#ffffff'), (0, H - 620), g.resize((W, 620)))
    d = ImageDraw.Draw(im, 'RGBA')
    # 左上：PR表記（ひと目でわかる形）／右上：イメージの注意
    fb = font('bold', 34)
    t = '【PR】楽天ROOM'
    bw = int(tw(d, t, fb)) + 52
    d.rounded_rectangle((48, 48, 48 + bw, 108), 30, fill=ACC)
    text(d, (74, 78), t, fb, '#ffffff', 'lm')
    fc = font('medium', 24)
    cap = '※画像はイメージです。実際の商品とは異なります'
    if q.get('photo'):  # 人物入りのAI画像：実在の人が使った写真に見せない
        cap = '※AIで作ったイメージです。実在の人物・実際の商品とは異なります'
        fc = fit(d, cap, 'medium', 24, W - 48 - 36 - 48 - bw - 40, 16)
    cw = tw(d, cap, fc)
    d.rounded_rectangle((W - 48 - cw - 36, 56, W - 48, 100), 22, fill=(0, 0, 0, 120))
    text(d, (W - 66, 78), cap, fc, '#ffffff', 'rm')
    # 下：短い一言（1〜2行）→ 価格 → 小さく商品名 → 案内
    y = (PHH + 70) if PHH < H else (H - 380)
    fh = font('display', 62)
    # キャッチコピー（11/12 マスター指示：画像には必ずキャッチコピーを入れる）
    hook = q.get('photo_line') or it.get('hook') or q.get('title') or it['name']
    hl = wrap(d, hook, fh, W - 150, 2)
    if len(hl) == 2:
        fh = font('display', 54); hl = wrap(d, hook, fh, W - 150, 2)
        y -= 20
    for l in hl:
        text(d, (60, y), l, fh, INK)
        y += 76
    y += 50
    price = str(it.get('price', ''))
    fp = fit(d, price, 'display', 84, 560, 50)
    text(d, (60, y), price, fp, ACC)
    y += 46
    fn = font('medium', 28)
    text(d, (62, y), wrap(d, it['name'], fn, W - 340, 1)[0], fn, MUTED)
    text(d, (62, H - 56), q['footer'], fit(d, q['footer'], 'medium', 30, FOOT_W, 20), MUTED)
    draw_saifu(im, 'kesseki')
    im.save(out, optimize=True)

if __name__ == '__main__':
    q = json.load(open(sys.argv[1], encoding='utf-8'))
    if q.get('full_image'):  # マスターのデザインをそのまま投稿画像にする（訂正済みのもの）
        Image.open(os.path.join(HERE, '..', q['full_image'])).convert('RGB').resize((W, H), Image.LANCZOS).save(sys.argv[2])
    elif q.get('kind') == 'single':
        # 場面イラストつきが基本。吹き出し（N9）と供養は専用の形のまま
        (render_single if (q.get('serif') or q.get('form') == 'kuyou' or q.get('scene') == 'none') else render_scene)(q, sys.argv[2])
    else:
        render(q, sys.argv[2])
    print(sys.argv[2])
