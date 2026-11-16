#!/usr/bin/env python3
"""Threadsのつぶやき（会話・深夜・発表会）に載せる「場面の画像」。
11/15 マスター命令：「今後のThreadsのつぶやきは、場面の画像を載せる形で必ず出す。場面が先、主題は後からついてくる」。
- 楓が置いた場面の写真（assets/scenes_talk/<場面>*.jpg|png|webp。4:5以内）があれば、それを優先して使う。
- 無ければ京が場面のイラストを描く（誰が見ても絵だとわかるタッチ。人物・商品・実在のロゴは描かない）。
- 画像は場面だけ。主題（問いかけ）は本文が後から運ぶ。
使い方：python3 tools/talk_scene.py queue/<id>.json images/<id>.png"""
import glob, hashlib, json, math, os, re, sys
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from render import font, wrap, W, H  # noqa: E402

K = 2
INK = (40, 34, 48)

# 場面ごとの言葉（本文・トピックにこの言葉があればその場面）
SCENES = [
    ('night', r'深夜|夜ふかし|夜中|寝る前|寝れ|眠れ|おやすみ|今夜|夜の'),
    ('morning', r'朝|目覚まし|スヌーズ|布団から|起き'),
    ('winter', r'寒|冬|暖房|こたつ|毛布|加湿|乾燥|結露|ヒーター|湯たんぽ|脱衣所'),
    ('shopping', r'カート|セール|楽天|お気に入り|買い|ポイント|マラソン|ブラックフライデー|5と0|散財|財布|ROOM'),
    ('desk', r'スマホ|アプリ|充電|ケーブル|イヤホン|家計簿|パソコン|ガジェット|電池|バッテリー|忘れ'),
    ('cafe', r'コーヒー|お茶|飲み物|朝ごはん|ケトル|ごはん|ラーメン|食'),
]


def pick_scene(q):
    s = (q.get('text') or '') + ' ' + (q.get('topic') or '')
    if q.get('slot') == 'late':
        return 'night'
    for name, pat in SCENES:
        if re.search(pat, s):
            return name
    return 'cafe'


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _grad(im, top, bottom, box=None):
    x0, y0, x1, y1 = box or (0, 0, im.size[0], im.size[1])
    d = ImageDraw.Draw(im)
    for y in range(y0, y1):
        d.line((x0, y, x1, y), fill=_lerp(top, bottom, (y - y0) / max(1, y1 - y0 - 1)))


def _window(d, x, y, w, h, frame=(250, 246, 238)):
    d.rounded_rectangle((x - 18, y - 18, x + w + 18, y + h + 18), 22, fill=frame)
    return (x, y, x + w, y + h)


def _mug(d, x, y, s, body=(236, 120, 96), steam=True):
    d.rounded_rectangle((x, y, x + s, y + s * 1.1), int(s * 0.16), fill=body)
    d.ellipse((x + s * 0.82, y + s * 0.25, x + s * 1.28, y + s * 0.75), outline=body, width=int(s * 0.12))
    d.ellipse((x + s * 0.06, y - s * 0.06, x + s * 0.94, y + s * 0.14), fill=_lerp(body, (60, 30, 20), 0.55))
    if steam:
        for i in range(3):
            cx = x + s * (0.25 + 0.25 * i)
            pts = [(cx + math.sin(t / 6 + i) * s * 0.07, y - s * 0.15 - t * s * 0.02) for t in range(0, 26)]
            d.line(pts, fill=(255, 255, 255), width=int(s * 0.05), joint='curve')


def _phone(d, x, y, w, h, screen=(120, 170, 230), glow=False):
    if glow:
        for r in range(6, 0, -1):
            d.rounded_rectangle((x - r * 14, y - r * 14, x + w + r * 14, y + h + r * 14), 40 + r * 10, fill=(255, 236, 170, 14))
    d.rounded_rectangle((x, y, x + w, y + h), int(w * 0.16), fill=(40, 40, 52))
    d.rounded_rectangle((x + w * 0.07, y + w * 0.1, x + w * 0.93, y + h - w * 0.1), int(w * 0.1), fill=screen)


def _plant(d, x, y, s):
    d.rounded_rectangle((x, y, x + s, y + s * 0.9), int(s * 0.12), fill=(226, 196, 160))
    for a, l in ((-0.9, 1.3), (-0.4, 1.6), (0.1, 1.5), (0.6, 1.25)):
        cx, cy = x + s / 2, y
        ex, ey = cx + math.sin(a) * s * l, cy - math.cos(a) * s * l
        d.ellipse((ex - s * 0.28, ey - s * 0.16, ex + s * 0.28, ey + s * 0.16), fill=(120, 170, 120))
        d.line((cx, cy, ex, ey), fill=(96, 140, 96), width=int(s * 0.05))


def s_night(c, d, Wc, Hc, rnd):
    _grad(c, (38, 44, 86), (86, 76, 128))
    wx, wy, ww, wh = Wc * 0.14, Hc * 0.08, Wc * 0.72, Hc * 0.46
    d.rounded_rectangle((wx - 22, wy - 22, wx + ww + 22, wy + wh + 22), 26, fill=(70, 64, 110))
    win = Image.new('RGB', (int(ww), int(wh)))
    _grad(win, (20, 26, 64), (52, 60, 120))
    wd = ImageDraw.Draw(win)
    for i in range(40):
        sx, sy = rnd(i * 3) * ww, rnd(i * 3 + 1) * wh * 0.8
        r = 2 + rnd(i * 3 + 2) * 4
        wd.ellipse((sx - r, sy - r, sx + r, sy + r), fill=(255, 248, 220))
    mx, my, mr = ww * 0.72, wh * 0.3, ww * 0.11
    wd.ellipse((mx - mr, my - mr, mx + mr, my + mr), fill=(255, 238, 180))
    wd.ellipse((mx - mr * 0.55, my - mr * 1.1, mx + mr * 1.45, my + mr * 0.9), fill=(30, 38, 84))
    c.paste(win, (int(wx), int(wy)))
    d.line((wx + ww / 2, wy, wx + ww / 2, wy + wh), fill=(70, 64, 110), width=14)
    # 机・ランプ・スマホ
    d.rectangle((0, Hc * 0.66, Wc, Hc), fill=(120, 86, 70))
    d.rectangle((0, Hc * 0.66, Wc, Hc * 0.68), fill=(146, 108, 88))
    lx = Wc * 0.18
    for r in range(8, 0, -1):
        d.ellipse((lx - r * 34, Hc * 0.5 - r * 30, lx + r * 34, Hc * 0.5 + r * 30), fill=(255, 220, 140, 10))
    d.polygon([(lx - 90, Hc * 0.52), (lx + 90, Hc * 0.52), (lx + 55, Hc * 0.42), (lx - 55, Hc * 0.42)], fill=(255, 214, 140))
    d.rectangle((lx - 8, Hc * 0.52, lx + 8, Hc * 0.66), fill=(80, 70, 70))
    d.ellipse((lx - 60, Hc * 0.645, lx + 60, Hc * 0.675), fill=(80, 70, 70))
    _phone(d, Wc * 0.56, Hc * 0.6, Wc * 0.16, Wc * 0.3, screen=(250, 236, 190), glow=True)
    _mug(d, Wc * 0.8, Hc * 0.6, Wc * 0.1, body=(200, 210, 236), steam=False)


def s_morning(c, d, Wc, Hc, rnd):
    _grad(c, (255, 236, 214), (252, 222, 200))
    wx, wy, ww, wh = Wc * 0.2, Hc * 0.07, Wc * 0.6, Hc * 0.4
    _window(d, wx, wy, ww, wh)
    win = Image.new('RGB', (int(ww), int(wh)))
    _grad(win, (150, 200, 240), (255, 214, 170))
    wd = ImageDraw.Draw(win)
    sx, sy, sr = ww * 0.5, wh * 0.82, ww * 0.16
    for r in range(6, 0, -1):
        wd.ellipse((sx - sr * (1 + r * 0.25), sy - sr * (1 + r * 0.25), sx + sr * (1 + r * 0.25), sy + sr * (1 + r * 0.25)), fill=_lerp((255, 214, 170), (255, 240, 200), r / 8))
    wd.ellipse((sx - sr, sy - sr, sx + sr, sy + sr), fill=(255, 196, 110))
    wd.rectangle((0, wh * 0.86, ww, wh), fill=(140, 150, 190))
    c.paste(win, (int(wx), int(wy)))
    d.line((wx + ww / 2, wy, wx + ww / 2, wy + wh), fill=(250, 246, 238), width=16)
    # 光の筋
    ov = Image.new('RGBA', c.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    od.polygon([(wx, wy + wh), (wx + ww, wy + wh), (Wc * 0.95, Hc), (Wc * 0.05, Hc)], fill=(255, 245, 210, 70))
    c.paste(Image.alpha_composite(c.convert('RGBA'), ov).convert('RGB'))
    d = ImageDraw.Draw(c, 'RGBA')
    # ベッドと布団
    d.rounded_rectangle((Wc * 0.04, Hc * 0.6, Wc * 0.96, Hc * 0.98), 60, fill=(250, 250, 246))
    d.rounded_rectangle((Wc * 0.1, Hc * 0.56, Wc * 0.4, Hc * 0.66), 50, fill=(255, 255, 255), outline=(230, 224, 214), width=6)
    d.rounded_rectangle((Wc * 0.02, Hc * 0.66, Wc * 0.98, Hc * 1.02), 80, fill=(150, 186, 214))
    for i in range(5):
        y = Hc * (0.72 + i * 0.055)
        d.arc((Wc * 0.05, y - 40, Wc * 0.95, y + 40), 200, 340, fill=(130, 166, 196), width=8)
    # 目覚まし
    ax, ay, ar = Wc * 0.82, Hc * 0.52, Wc * 0.06
    d.ellipse((ax - ar, ay - ar, ax + ar, ay + ar), fill=(240, 110, 90))
    d.ellipse((ax - ar * 0.78, ay - ar * 0.78, ax + ar * 0.78, ay + ar * 0.78), fill=(255, 252, 246))
    d.line((ax, ay, ax, ay - ar * 0.55), fill=INK, width=8)
    d.line((ax, ay, ax + ar * 0.4, ay), fill=INK, width=8)
    for sgn in (-1, 1):
        d.ellipse((ax + sgn * ar * 0.75 - 18, ay - ar * 1.1 - 18, ax + sgn * ar * 0.75 + 18, ay - ar * 1.1 + 18), fill=(240, 110, 90))


def s_winter(c, d, Wc, Hc, rnd):
    _grad(c, (226, 234, 246), (240, 232, 226))
    wx, wy, ww, wh = Wc * 0.12, Hc * 0.07, Wc * 0.76, Hc * 0.44
    _window(d, wx, wy, ww, wh)
    win = Image.new('RGB', (int(ww), int(wh)))
    _grad(win, (176, 196, 222), (226, 234, 244))
    wd = ImageDraw.Draw(win)
    wd.ellipse((-ww * 0.2, wh * 0.7, ww * 0.6, wh * 1.3), fill=(250, 252, 255))
    wd.ellipse((ww * 0.4, wh * 0.75, ww * 1.2, wh * 1.35), fill=(244, 248, 255))
    for i in range(70):
        sx, sy = rnd(i * 2) * ww, rnd(i * 2 + 1) * wh
        r = 3 + rnd(i + 99) * 6
        wd.ellipse((sx - r, sy - r, sx + r, sy + r), fill=(255, 255, 255))
    c.paste(win, (int(wx), int(wy)))
    d.line((wx + ww / 2, wy, wx + ww / 2, wy + wh), fill=(250, 246, 238), width=16)
    # こたつ風のテーブルと毛布
    d.rounded_rectangle((Wc * 0.0, Hc * 0.62, Wc * 1.0, Hc * 1.05), 40, fill=(214, 112, 96))
    for i in range(7):
        x = Wc * (0.07 + i * 0.14)
        d.line((x, Hc * 0.66, x, Hc), fill=(196, 96, 82), width=10)
    d.rounded_rectangle((Wc * -0.02, Hc * 0.58, Wc * 1.02, Hc * 0.65), 18, fill=(186, 138, 96))
    _mug(d, Wc * 0.22, Hc * 0.47, Wc * 0.12, body=(250, 246, 236))
    # みかん
    for i, (mx, my) in enumerate(((0.62, 0.52), (0.72, 0.53), (0.67, 0.47))):
        r = Wc * 0.045
        d.ellipse((Wc * mx - r, Hc * my - r, Wc * mx + r, Hc * my + r), fill=(250, 160, 50))
        d.ellipse((Wc * mx - 8, Hc * my - r - 4, Wc * mx + 14, Hc * my - r + 12), fill=(110, 150, 80))


def s_shopping(c, d, Wc, Hc, rnd):
    _grad(c, (250, 232, 222), (246, 240, 230))
    # 壁の飾りライン
    for i in range(9):
        y = Hc * (0.06 + i * 0.065)
        d.line((0, y, Wc, y), fill=(246, 222, 210), width=6)
    d.rectangle((0, Hc * 0.64, Wc, Hc), fill=(222, 196, 170))
    d.rectangle((0, Hc * 0.64, Wc, Hc * 0.66), fill=(236, 214, 190))
    # 紙袋（ロゴなし）
    cols = [(236, 140, 120), (130, 170, 200), (240, 200, 110)]
    for i, (bx, bw, bh) in enumerate(((0.08, 0.26, 0.36), (0.3, 0.22, 0.3), (0.66, 0.26, 0.34))):
        x0, y1 = Wc * bx, Hc * 0.72
        y0 = y1 - Hc * bh
        d.rectangle((x0, y0, x0 + Wc * bw, y1), fill=cols[i])
        d.polygon([(x0, y0), (x0 + Wc * bw, y0), (x0 + Wc * bw - 20, y0 + 30), (x0 + 20, y0 + 30)], fill=_lerp(cols[i], (0, 0, 0), 0.12))
        d.arc((x0 + Wc * bw * 0.25, y0 - Hc * 0.08, x0 + Wc * bw * 0.75, y0 + Hc * 0.04), 180, 360, fill=_lerp(cols[i], (0, 0, 0), 0.3), width=12)
    # スマホ（カートの画面・ロゴなし）
    px, py, pw, ph = Wc * 0.4, Hc * 0.36, Wc * 0.22, Wc * 0.42
    _phone(d, px, py, pw, ph, screen=(255, 252, 246))
    cx, cy = px + pw / 2, py + ph * 0.42
    d.line((cx - 60, cy - 40, cx - 40, cy - 40, cx - 20, cy + 30, cx + 50, cy + 30, cx + 64, cy - 20, cx - 30, cy - 20), fill=(236, 120, 96), width=10, joint='curve')
    for dx in (-10, 40):
        d.ellipse((cx + dx - 10, cy + 42, cx + dx + 10, cy + 62), fill=(236, 120, 96))
    d.rounded_rectangle((px + pw * 0.18, py + ph * 0.68, px + pw * 0.82, py + ph * 0.78), 20, fill=(236, 120, 96))
    # きらきら
    for i in range(6):
        sx, sy = Wc * (0.1 + rnd(i) * 0.8), Hc * (0.05 + rnd(i + 20) * 0.25)
        r = 14 + rnd(i + 40) * 16
        d.polygon([(sx, sy - r), (sx + r * 0.3, sy - r * 0.3), (sx + r, sy), (sx + r * 0.3, sy + r * 0.3), (sx, sy + r), (sx - r * 0.3, sy + r * 0.3), (sx - r, sy), (sx - r * 0.3, sy - r * 0.3)], fill=(255, 200, 90))


def s_desk(c, d, Wc, Hc, rnd):
    _grad(c, (232, 238, 236), (244, 240, 232))
    # 机の上を上から見た形
    d.rounded_rectangle((Wc * 0.03, Hc * 0.04, Wc * 0.97, Hc * 0.98), 50, fill=(214, 182, 146))
    for i in range(10):
        y = Hc * (0.08 + i * 0.09)
        d.line((Wc * 0.05, y, Wc * 0.95, y + 10), fill=(204, 170, 134), width=4)
    # ノートとペン
    d.rounded_rectangle((Wc * 0.1, Hc * 0.12, Wc * 0.52, Hc * 0.6), 18, fill=(255, 254, 248))
    for i in range(9):
        y = Hc * (0.17 + i * 0.045)
        d.line((Wc * 0.14, y, Wc * 0.48, y), fill=(200, 216, 232), width=4)
    d.line((Wc * 0.47, Hc * 0.2, Wc * 0.62, Hc * 0.5), fill=(70, 90, 140), width=18)
    # スマホとケーブル
    _phone(d, Wc * 0.6, Hc * 0.14, Wc * 0.24, Wc * 0.46, screen=(186, 214, 240))
    d.line([(Wc * 0.72, Hc * 0.14 + Wc * 0.46), (Wc * 0.74, Hc * 0.62), (Wc * 0.6, Hc * 0.72), (Wc * 0.8, Hc * 0.86), (Wc * 0.98, Hc * 0.84)], fill=(250, 250, 250), width=12, joint='curve')
    # イヤホンケースと植物、マグ
    d.rounded_rectangle((Wc * 0.12, Hc * 0.7, Wc * 0.26, Hc * 0.8), 40, fill=(250, 250, 250))
    d.line((Wc * 0.12, Hc * 0.735, Wc * 0.26, Hc * 0.735), fill=(220, 220, 220), width=4)
    _mug(d, Wc * 0.36, Hc * 0.72, Wc * 0.11, body=(120, 170, 150), steam=False)


def s_cafe(c, d, Wc, Hc, rnd):
    _grad(c, (246, 236, 220), (240, 226, 206))
    wx, wy, ww, wh = Wc * 0.1, Hc * 0.07, Wc * 0.42, Hc * 0.42
    _window(d, wx, wy, ww, wh)
    win = Image.new('RGB', (int(ww), int(wh)))
    _grad(win, (180, 214, 236), (230, 240, 236))
    wd = ImageDraw.Draw(win)
    wd.ellipse((ww * 0.1, wh * 0.15, ww * 0.5, wh * 0.32), fill=(255, 255, 255))
    wd.ellipse((ww * 0.3, wh * 0.08, ww * 0.7, wh * 0.3), fill=(255, 255, 255))
    c.paste(win, (int(wx), int(wy)))
    # 棚
    d.rectangle((Wc * 0.6, Hc * 0.2, Wc * 0.94, Hc * 0.22), fill=(170, 120, 86))
    _plant(d, Wc * 0.66, Hc * 0.15, Wc * 0.08)
    for i, col in enumerate(((236, 140, 120), (130, 170, 200), (240, 200, 110))):
        d.rounded_rectangle((Wc * (0.8 + i * 0.045), Hc * 0.12, Wc * (0.835 + i * 0.045), Hc * 0.2), 6, fill=col)
    # テーブル
    d.rectangle((0, Hc * 0.58, Wc, Hc), fill=(186, 140, 104))
    d.rectangle((0, Hc * 0.58, Wc, Hc * 0.6), fill=(204, 160, 122))
    _mug(d, Wc * 0.2, Hc * 0.5, Wc * 0.15, body=(250, 246, 236))
    # お皿とパン
    d.ellipse((Wc * 0.5, Hc * 0.6, Wc * 0.9, Hc * 0.72), fill=(250, 250, 250))
    d.rounded_rectangle((Wc * 0.58, Hc * 0.57, Wc * 0.82, Hc * 0.66), 40, fill=(230, 176, 110))
    d.rounded_rectangle((Wc * 0.6, Hc * 0.58, Wc * 0.8, Hc * 0.63), 30, fill=(244, 206, 150))


DRAW = {'night': s_night, 'morning': s_morning, 'winter': s_winter, 'shopping': s_shopping, 'desk': s_desk, 'cafe': s_cafe}


def _photo(scene, seed):
    fs = sorted(glob.glob(os.path.join(HERE, '..', 'assets', 'scenes_talk', scene + '*')))
    fs = [f for f in fs if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
    if not fs:
        return None
    try:
        im = Image.open(fs[seed % len(fs)]).convert('RGB')
    except Exception:
        return None
    if im.size[1] / im.size[0] > 1.26:  # 4:5より縦長は使わない
        return None
    return im


class NoPhoto(Exception):
    pass


def make(q, out):
    scene = q.get('scene_talk') or pick_scene(q)
    seed = int(hashlib.md5((q.get('id', '') + scene).encode()).hexdigest(), 16)
    rnd = lambda i: (int(hashlib.md5(f'{seed}-{i}'.encode()).hexdigest()[:8], 16) / 0xffffffff)
    im = Image.new('RGB', (W, H), (252, 250, 246))
    PH = H  # 画面いっぱいに場面
    ph = None
    # 11/16 マスター命令：「つぶやきと画像が全く違う」「つぶやき画像は京がモデル」。
    # 固定画像（楓の夜の写真）と共通の場面写真はやめ、投稿ごとに楓が作る「京がモデル・本文と同じ場面」の実写風写真だけを使う。
    # 置き場所：assets/photos/ready/talk-<id>.jpg|png|webp（4:5以内）。無ければ hold で楓の写真を待つ。
    fs = sorted(glob.glob(os.path.join(HERE, '..', 'assets', 'photos', 'ready', 'talk-' + q.get('id', '') + '.*')))
    fs = [f for f in fs if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
    if fs:
        ph = Image.open(fs[0]).convert('RGB')
        if ph.size[1] / ph.size[0] > 1.26:
            ph = None
        else:
            scene = 'kyo:' + os.path.basename(fs[0])
    if ph is None:
        raise NoPhoto('京モデルの写真 assets/photos/ready/talk-' + q.get('id', '') + '.* がありません（イラスト・固定画像は禁止）')
    if ph is not None:
        r = max(W / ph.size[0], PH / ph.size[1])
        ph = ph.resize((int(ph.size[0] * r + 1), int(ph.size[1] * r + 1)), Image.LANCZOS)
        x, y = (ph.size[0] - W) // 2, (ph.size[1] - PH) // 2
        im.paste(ph.crop((x, y, x + W, y + PH)), (0, 0))
        cap = '※写真はイメージです'
    else:
        c = Image.new('RGB', (W * K, PH * K))
        DRAW[scene](c, ImageDraw.Draw(c, 'RGBA'), W * K, PH * K, rnd)
        im.paste(c.resize((W, PH), Image.LANCZOS), (0, 0))
        cap = '※イラストはイメージです'
    d = ImageDraw.Draw(im, 'RGBA')
    # 画像は場面だけ（文字は本文に任せる。本文があとで書き換えられても画像とずれない）
    fc = font('medium', 22)
    tw_ = d.textlength(cap, font=fc)
    d.rounded_rectangle((W - 40 - tw_ - 28, H - 66, W - 28, H - 28), 18, fill=(0, 0, 0, 90))
    d.text((W - 42, H - 47), cap, font=fc, fill=(255, 255, 255), anchor='rm')
    im.save(out, optimize=True)
    return scene


def attach(repo, q):
    """queue の投稿に場面の画像を付ける（images/<id>.png を作り、image:true にする）。失敗しても投稿は止めない。"""
    try:
        os.makedirs(os.path.join(repo, 'images'), exist_ok=True)
        sc = make(q, os.path.join(repo, 'images', q['id'] + '.png'))
        q['image'] = True
        q['scene_talk'] = sc
    except NoPhoto as e:
        # 画像なしでは出さない（11/15 場面画像は必須）・イラストでも出さない（11/16）。楓の写真を待つ
        q['hold'] = '楓の写真待ち（京がモデル・本文と同じ場面の実写風・4:5。assets/photos/ready/talk-' + q['id'] + '.jpg に置く。京が検品して hold を外す）'
        print('場面写真がないので hold：', e)
    except Exception as e:
        print('場面の画像を作れませんでした：', e)
    return q


if __name__ == '__main__':
    q = json.load(open(sys.argv[1], encoding='utf-8'))
    print(make(q, sys.argv[2]))
