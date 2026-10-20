#!/usr/bin/env python3
"""queue/<id>.json から 1080×1350 のまとめ画像（images/<id>.png）を作る。投稿ノートの「まとめてThreadsへ」と同じデザイン。"""
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
    top, bottom = 330, 1170
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
    text(d, (110, 1240), q['footer'], fit(d, q['footer'], 'medium', 34, W - 220, 24), MUTED)
    im.save(out, optimize=True)


if __name__ == '__main__':
    q = json.load(open(sys.argv[1], encoding='utf-8'))
    render(q, sys.argv[2])
    print(sys.argv[2])
