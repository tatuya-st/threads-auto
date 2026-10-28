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


def render_scene(q, out):
    """商品1件＋場面イラスト（物欲おばけが商品の活きる場面を演じる。実物写真のふりはしない）。"""
    import scenes
    im = Image.new('RGB', (W, H), '#fdf1e2')
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((60, 60, W - 60, H - 60), 48, fill='#ffffff')
    fb = font('bold', 38)
    t = '【PR】楽天ROOM'
    bw = int(tw(d, t, fb)) + 64
    d.rounded_rectangle((110, 110, 110 + bw, 180), 35, fill=ACC)
    text(d, (142, 147), t, fb, '#ffffff', 'lm')
    text(d, (W - 110, 155), '※画像はイメージです', font('medium', 28), SUB, 'rs')
    text(d, (110, 270), q['title'], fit(d, q['title'], 'display', 60, W - 220, 40), INK)
    it = q['items'][0]
    sc = q.get('scene') or scenes.pick(it, q)
    if q.get('photo'):  # マスターがMUSEで作った写真
        scenes.draw_custom(im, (110, 305, W - 110, 805), os.path.join(HERE, '..', q['photo']), q.get('photo_line'), font)
    else:
        scenes.draw(im, (110, 305, W - 110, 805), sc, scenes.line_for(sc, q), font, q.get('chara'))
    d = ImageDraw.Draw(im)
    y = 885
    fh = font('bold', 46)
    hl = wrap(d, it.get('hook') or it['name'], fh, W - 220, 2)
    for l in hl:
        text(d, (110, y), l, fh, INK)
        y += 60
    if it.get('hook'):
        fn = font('medium', 28)
        text(d, (110, y), wrap(d, it['name'], fn, W - 220, 1)[0], fn, MUTED)
        y += 30
    y += 88
    price = str(it.get('price', ''))
    fp = fit(d, price, 'display', 76, 520, 50)
    text(d, (110, y), price, fp, ACC)
    quip = it.get('quip') or ''
    if quip:
        px = 110 + tw(d, price, fp) + 28
        mx = W - 110 - px
        fq = fit(d, '← ' + quip, 'medium', 32, mx, 20)
        if tw(d, '← ' + quip, fq) <= mx:
            text(d, (px, y - 8), '← ' + quip, fq, SUB)
    text(d, (110, 1240), q['footer'], fit(d, q['footer'], 'medium', 34, FOOT_W, 22), MUTED)
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
