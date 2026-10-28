#!/usr/bin/env python3
"""商品が活きる場面のイラスト。主役はハロウィン時期（10/15〜10/31）だけ「物欲おばけ」、それ以外は「財布欠席くん」。
誰が見ても絵だとわかるタッチで描く。実物の商品写真のふりはしない。
pick(it, q) で場面を選び、draw(im, box, scene, line) で box の中に描く。"""
import hashlib, math
from PIL import Image, ImageDraw

INK = (34, 26, 43)
WH = (252, 250, 244)
K = 2  # 2倍で描いて縮小（線をなめらかに）

# 場面ごとの背景色と、吹き出しのひと言（毎回ちがう言葉になるよう日付と商品で選ぶ）
SCENES = {
    'battery': {'bg': (214, 232, 244), 'words': ['バッテリー', '充電器', '充電', 'mAh', 'モバイル'],
                'lines': ['残り30%…\nコンセントどこ…', '充電1%で\n家を出た朝', '電池マークが\n赤くなる恐怖']},
    'winter': {'bg': (222, 230, 246), 'words': ['ヒーター', '暖房', '加湿', '毛布', 'こたつ', 'ブランケット', 'あったか', '湯たんぽ', '電気'],
               'lines': ['布団から\n出られない…', '朝の床が\n冷たすぎる', '寒さに\n負けそう…']},
    'refill': {'bg': (226, 240, 222), 'words': ['詰め替え', '詰替', 'つめかえ', '洗剤', 'シャンプー', 'ティッシュ', 'トイレット', 'ハンドソープ', 'まとめ買い'],
               'lines': ['また切れてる…\n買い置きどこ', 'ボトル買い直し、\nもう卒業', '気づいたら\n空っぽ']},
    'oral': {'bg': (222, 240, 240), 'words': ['歯', 'オーラル', 'デンタル', 'マウス'],
             'lines': ['歯医者さんに\nほめられたい', '朝のお口、\nシャキッと', 'みがき残し、\n許さない']},
    'iphone': {'bg': (236, 230, 246), 'words': ['iPhone', 'アイフォン', 'Apple', 'AirPods', 'スマホケース', '保護フィルム', 'ガラスフィルム', 'Lightning', 'USB-C', 'スマホ', 'MagSafe'],
               'lines': ['スマホ、今日も\n落としかけた', 'このスマホと\n長く付き合いたい', '画面バキバキは\nもうイヤだ']},
    'cart': {'bg': (246, 232, 214), 'words': [],
             'lines': ['カートに入れて\n…消して…入れて', '財布と相談中\n（劣勢）', '今夜もカートに\n出没中']},
}
ORDER = ['battery', 'winter', 'refill', 'oral', 'iphone']


def pick(it, q):
    s = ' '.join(str(x or '') for x in (it.get('name'), it.get('hook'), q.get('topic')))
    for k in ORDER:
        if any(w in s for w in SCENES[k]['words']):
            return k
    return 'cart'


def line_for(scene, q):
    if q.get('scene_line'):
        return q['scene_line']
    ls = SCENES[scene]['lines']
    h = int(hashlib.md5((q.get('id', '') + scene).encode()).hexdigest(), 16)
    return ls[h % len(ls)]


# ───────── 部品 ─────────
def ghost(d, x, y, s, mood='normal', hat=False):
    """物欲おばけ。x,y は頭のてっぺんの中心、s は横幅の半分。"""
    body = []
    for i in range(181):
        a = math.radians(180 + i)
        body.append((x + s * math.cos(a), y + s + s * math.sin(a)))
    body += [(x + s, y + s), (x + s * 1.12, y + s * 2.5)]
    n = 7
    for i in range(n):
        xx = x + s * 1.12 - (i + 0.5) * (s * 2.24 / n)
        body.append((xx, y + s * (2.72 if i % 2 == 0 else 2.45)))
    body.append((x - s * 1.12, y + s * 2.5))
    d.polygon([(a + 6 * K, b + 6 * K) for a, b in body], fill=(0, 0, 0, 60))
    d.polygon(body, fill=WH, outline=INK)
    d.line(body + [body[0]], fill=INK, width=5 * K, joint='curve')
    ey = y + s * 0.85
    for ex in (x - s * 0.38, x + s * 0.38):
        if mood == 'happy':
            d.arc((ex - s * 0.18, ey - s * 0.12, ex + s * 0.18, ey + s * 0.2), 200, 340, fill=INK, width=5 * K)
        else:
            d.ellipse((ex - s * 0.16, ey - s * 0.22, ex + s * 0.16, ey + s * 0.22), fill=INK)
            d.ellipse((ex - s * 0.07, ey - s * 0.15, ex + s * 0.02, ey - s * 0.05), fill=WH)
    d.ellipse((x - s * 0.72, ey + s * 0.22, x - s * 0.44, ey + s * 0.38), fill=(250, 170, 170))
    d.ellipse((x + s * 0.44, ey + s * 0.22, x + s * 0.72, ey + s * 0.38), fill=(250, 170, 170))
    my = ey + s * 0.45
    if mood == 'happy':
        d.chord((x - s * 0.2, my - s * 0.12, x + s * 0.2, my + s * 0.22), 0, 180, fill=INK)
    elif mood == 'worry':
        d.arc((x - s * 0.18, my, x + s * 0.18, my + s * 0.24), 200, 340, fill=INK, width=5 * K)
        for i, (sx, sy) in enumerate([(x + s * 0.95, y + s * 0.3), (x + s * 1.15, y + s * 0.65)]):
            r = s * (0.13 - i * 0.03)
            d.polygon([(sx, sy - r * 1.8), (sx + r, sy), (sx - r, sy)], fill=(110, 180, 240), outline=INK)
            d.ellipse((sx - r, sy - r, sx + r, sy + r), fill=(110, 180, 240), outline=INK, width=2 * K)
    elif mood == 'cold':
        d.line([(x - s * 0.2 + i * s * 0.08, my + s * (0.05 if i % 2 else 0.15)) for i in range(6)], fill=INK, width=4 * K)
    else:
        d.ellipse((x - s * 0.12, my, x + s * 0.12, my + s * 0.22), fill=INK)
    return body


def season_chara(now=None):
    from datetime import datetime, timezone, timedelta
    now = now or datetime.now(timezone(timedelta(hours=9)))
    return 'ghost' if (now.month == 10 and now.day >= 15) else 'saifu'


CHARA = 'saifu'
S_BODY, S_EDGE, S_FLAP, S_IN = (160, 99, 46), (91, 52, 21), (138, 82, 38), (244, 230, 211)


def saifu(d, x, y, s, mood='normal'):
    """財布欠席くん（ふたが少し開いた財布）。おばけと同じ場所・大きさに収まる。顔はおばけより 0.65s 下。"""
    e = 5 * K
    d.rounded_rectangle((x - s * 1.05 + 6 * K, y + s * 0.95 + 6 * K, x + s * 1.05 + 6 * K, y + s * 2.6 + 6 * K), s * 0.22, fill=(0, 0, 0, 60))
    d.polygon([(x - s * 1.0, y + s * 1.0), (x + s * 1.0, y + s * 1.0), (x + s * 0.85, y + s * 0.5), (x - s * 0.85, y + s * 0.5)], fill=S_FLAP)
    d.line([(x - s * 1.0, y + s * 1.0), (x - s * 0.85, y + s * 0.5), (x + s * 0.85, y + s * 0.5), (x + s * 1.0, y + s * 1.0)], fill=S_EDGE, width=e, joint='curve')
    d.polygon([(x - s * 0.9, y + s * 1.0), (x + s * 0.9, y + s * 1.0), (x + s * 0.78, y + s * 0.75), (x - s * 0.78, y + s * 0.75)], fill=S_IN)
    d.rounded_rectangle((x - s * 1.05, y + s * 0.95, x + s * 1.05, y + s * 2.6), s * 0.22, fill=S_BODY, outline=S_EDGE, width=e)
    ey = y + s * 1.5
    for ex in (x - s * 0.38, x + s * 0.38):
        if mood == 'happy':
            d.arc((ex - s * 0.18, ey - s * 0.12, ex + s * 0.18, ey + s * 0.2), 200, 340, fill=S_EDGE, width=e)
        else:
            d.ellipse((ex - s * 0.19, ey - s * 0.19, ex + s * 0.19, ey + s * 0.19), fill=WH, outline=S_EDGE, width=3 * K)
            d.ellipse((ex - s * 0.08, ey - s * 0.08, ex + s * 0.08, ey + s * 0.08), fill=(17, 17, 17))
    d.ellipse((x - s * 0.75, ey + s * 0.2, x - s * 0.47, ey + s * 0.36), fill=(232, 140, 120))
    d.ellipse((x + s * 0.47, ey + s * 0.2, x + s * 0.75, ey + s * 0.36), fill=(232, 140, 120))
    my = ey + s * 0.45
    if mood == 'happy':
        d.chord((x - s * 0.2, my - s * 0.12, x + s * 0.2, my + s * 0.22), 0, 180, fill=S_EDGE)
    elif mood == 'worry':
        d.line([(x - s * 0.18, my + s * 0.16), (x, my + s * 0.04), (x + s * 0.18, my + s * 0.16)], fill=S_EDGE, width=e, joint='curve')
        for i, (sx, sy) in enumerate([(x + s * 1.2, y + s * 1.0), (x + s * 1.35, y + s * 1.35)]):
            r = s * (0.13 - i * 0.03)
            d.polygon([(sx, sy - r * 1.8), (sx + r, sy), (sx - r, sy)], fill=(110, 180, 240), outline=INK)
            d.ellipse((sx - r, sy - r, sx + r, sy + r), fill=(110, 180, 240), outline=INK, width=2 * K)
    elif mood == 'cold':
        d.line([(x - s * 0.2 + i * s * 0.08, my + s * (0.05 if i % 2 else 0.15)) for i in range(6)], fill=S_EDGE, width=4 * K)
    else:
        d.ellipse((x - s * 0.1, my, x + s * 0.1, my + s * 0.18), fill=S_EDGE)


def chara(d, x, y, s, mood='normal'):
    """季節の主役を描き、顔の位置のずれ（s単位）を返す。"""
    if CHARA == 'ghost':
        ghost(d, x, y, s, mood)
        return 0.0
    saifu(d, x, y, s, mood)
    return 0.65


GS, GY = 0.1, 0.34  # おばけの大きさ（横幅比）と頭の高さ（高さ比）


def arm(d, a, b, r):
    d.line([a, b], fill=INK, width=int(r * 1.2))
    d.line([a, b], fill=WH, width=int(r * 1.2) - 8 * K)
    hand(d, b[0], b[1], r)


def hand(d, x, y, r):
    d.ellipse((x - r, y - r, x + r, y + r), fill=WH, outline=INK, width=4 * K)


def bubble(d, box, tail, text, f):
    x0, y0, x1, y1 = box
    d.rounded_rectangle((x0 + 5 * K, y0 + 5 * K, x1 + 5 * K, y1 + 5 * K), 34 * K, fill=(0, 0, 0, 50))
    d.polygon([(tail[0], tail[1]), (tail[2], tail[3]), (tail[4], tail[5])], fill=WH, outline=INK)
    d.line([(tail[0], tail[1]), (tail[2], tail[3])], fill=INK, width=4 * K)
    d.line([(tail[2], tail[3]), (tail[4], tail[5])], fill=INK, width=4 * K)
    d.rounded_rectangle(box, 34 * K, fill=WH, outline=INK, width=4 * K)
    d.polygon([(tail[0] + 3 * K, tail[1] - 6 * K if tail[3] > y1 else tail[1] + 6 * K), (tail[2], tail[3]), (tail[4] - 3 * K, tail[5] - 6 * K if tail[3] > y1 else tail[5] + 6 * K)], fill=WH)
    lines = text.split('\n')
    lh = f.size * 1.3
    cy = (y0 + y1) / 2 - lh * (len(lines) - 1) / 2
    for i, l in enumerate(lines):
        d.text(((x0 + x1) / 2, cy + i * lh), l, font=f, fill=INK, anchor='mm')


def sparkle(d, x, y, r, c=(255, 205, 60)):
    d.polygon([(x, y - r), (x + r * 0.25, y - r * 0.25), (x + r, y), (x + r * 0.25, y + r * 0.25), (x, y + r), (x - r * 0.25, y + r * 0.25), (x - r, y), (x - r * 0.25, y - r * 0.25)], fill=c, outline=INK)


def phone(d, x, y, w, h, pct=None, crack=False):
    d.rounded_rectangle((x, y, x + w, y + h), w * 0.16, fill=(40, 40, 50), outline=INK, width=4 * K)
    d.rounded_rectangle((x + w * 0.08, y + h * 0.06, x + w * 0.92, y + h * 0.94), w * 0.1, fill=(250, 250, 255))
    if pct is not None:
        bx0, by0, bx1, by1 = x + w * 0.22, y + h * 0.36, x + w * 0.72, y + h * 0.6
        d.rounded_rectangle((bx0, by0, bx1, by1), 6 * K, outline=INK, width=4 * K)
        d.rectangle((bx1, by0 + (by1 - by0) * 0.3, bx1 + w * 0.06, by0 + (by1 - by0) * 0.7), fill=INK)
        d.rectangle((bx0 + 5 * K, by0 + 5 * K, bx0 + 5 * K + (bx1 - bx0 - 10 * K) * pct, by1 - 5 * K), fill=(225, 50, 45))
    if crack:
        d.line([(x + w * 0.3, y + h * 0.1), (x + w * 0.45, y + h * 0.3), (x + w * 0.35, y + h * 0.45), (x + w * 0.6, y + h * 0.7)], fill=INK, width=3 * K)


# ───────── 場面 ─────────
def s_battery(d, W, H, f):
    # 床
    d.rectangle((0, H * 0.82, W, H), fill=(190, 210, 228))
    gx = W * 0.27
    chara(d, gx, H * GY, W * GS, 'worry')
    phone(d, W * 0.39, H * 0.5, W * 0.085, W * 0.15, pct=0.3)
    arm(d, (gx + W * 0.09, H * 0.66), (W * 0.39, H * 0.66), W * 0.025)
    for i, (qx, qy) in enumerate([(W * 0.07, H * 0.5), (W * 0.04, H * 0.68)]):
        d.text((qx, qy), '?', font=f['big'], fill=INK, anchor='mm')
    # バッテリー（救世主）
    bx, by, bw, bh = W * 0.66, H * 0.38, W * 0.17, W * 0.24
    for i in range(10):
        a = i * math.pi / 5
        d.line((bx + bw / 2 + bw * 0.6 * math.cos(a), by + bh / 2 + bw * 0.6 * math.sin(a), bx + bw / 2 + bw * 0.85 * math.cos(a), by + bh / 2 + bw * 0.85 * math.sin(a)), fill=(255, 200, 60), width=7 * K)
    d.rounded_rectangle((bx, by, bx + bw, by + bh), bw * 0.18, fill=(60, 70, 90), outline=INK, width=5 * K)
    d.polygon([(bx + bw * 0.55, by + bh * 0.15), (bx + bw * 0.28, by + bh * 0.55), (bx + bw * 0.48, by + bh * 0.55), (bx + bw * 0.4, by + bh * 0.85), (bx + bw * 0.72, by + bh * 0.42), (bx + bw * 0.52, by + bh * 0.42)], fill=(255, 210, 60), outline=INK)
    d.rounded_rectangle((bx - bw * 0.1, by - H * 0.15, bx + bw * 1.1, by - H * 0.05), 12 * K, fill=(225, 80, 40), outline=INK, width=4 * K)
    d.text((bx + bw / 2, by - H * 0.1), '救世主', font=f['tag'], fill=WH, anchor='mm')
    sparkle(d, W * 0.93, H * 0.3, W * 0.03); sparkle(d, W * 0.6, H * 0.22, W * 0.02)
    return gx


def s_winter(d, W, H, f):
    d.rectangle((0, H * 0.82, W, H), fill=(196, 206, 228))
    for i in range(26):
        x, y = (i * 137) % int(W), (i * 89) % int(H * 0.7)
        d.ellipse((x - 5 * K, y - 5 * K, x + 5 * K, y + 5 * K), fill=WH)
    gx, gy, s = W * 0.27, H * GY, W * GS
    gy += chara(d, gx, gy, s, 'cold') * s  # 以降の小物は顔の位置に合わせる
    d.rounded_rectangle((gx - s * 1.05, gy + s * 1.55, gx + s * 1.05, gy + s * 1.85), 10 * K, fill=(220, 60, 60), outline=INK, width=4 * K)
    d.rectangle((gx + s * 0.4, gy + s * 1.7, gx + s * 0.7, gy + s * 2.3), fill=(220, 60, 60), outline=INK, width=4 * K)
    for i in range(3):
        d.text((gx - s * 1.35 - i * 8 * K, gy + s * (0.8 + i * 0.5)), '))', font=f['tag'], fill=(80, 120, 200), anchor='mm')
    # ヒーター
    hx, hy, hw, hh = W * 0.63, H * 0.38, W * 0.25, H * 0.42
    for i in range(3):
        xx = hx + hw * (0.25 + i * 0.25)
        d.line([(xx + 8 * K * math.sin(t / 2.5), hy - H * 0.04 - t * K * 2.2) for t in range(0, 30)], fill=(240, 130, 50), width=5 * K)
    d.rounded_rectangle((hx, hy, hx + hw, hy + hh), 22 * K, fill=(245, 240, 230), outline=INK, width=5 * K)
    d.rounded_rectangle((hx + hw * 0.12, hy + hh * 0.12, hx + hw * 0.88, hy + hh * 0.72), 14 * K, fill=(250, 140, 50), outline=INK, width=4 * K)
    for i in range(4):
        yy = hy + hh * (0.2 + i * 0.13)
        d.line((hx + hw * 0.2, yy, hx + hw * 0.8, yy), fill=(255, 220, 120), width=6 * K)
    d.ellipse((hx + hw * 0.4, hy + hh * 0.8, hx + hw * 0.6, hy + hh * 0.92), fill=(200, 60, 50), outline=INK, width=3 * K)
    return gx


def s_refill(d, W, H, f):
    d.rectangle((0, H * 0.82, W, H), fill=(196, 222, 190))
    d.rectangle((W * 0.02, H * 0.74, W * 0.4, H * 0.77), fill=(150, 110, 70), outline=INK, width=3 * K)
    for i in range(3):
        x = W * (0.06 + i * 0.12)
        d.rounded_rectangle((x, H * 0.52, x + W * 0.07, H * 0.74), 8 * K, fill=(235, 240, 245), outline=INK, width=4 * K)
        d.rectangle((x + W * 0.02, H * 0.47, x + W * 0.05, H * 0.52), fill=(120, 170, 220), outline=INK, width=3 * K)
        d.text((x + W * 0.035, H * 0.63), '空', font=f['tag'], fill=(150, 150, 160), anchor='mm')
    gx = W * 0.62
    chara(d, gx, H * GY, W * GS, 'happy')
    px, py, pw, ph = W * 0.76, H * 0.46, W * 0.15, H * 0.33
    d.polygon([(px, py + ph * 0.1), (px + pw * 0.3, py), (px + pw, py), (px + pw, py + ph), (px, py + ph)], fill=(110, 190, 220), outline=INK)
    d.line([(px, py + ph * 0.1), (px + pw * 0.3, py), (px + pw, py), (px + pw, py + ph), (px, py + ph), (px, py + ph * 0.1)], fill=INK, width=5 * K)
    d.rounded_rectangle((px + pw * 0.1, py + ph * 0.35, px + pw * 0.9, py + ph * 0.6), 8 * K, fill=WH, outline=INK, width=3 * K)
    d.text((px + pw / 2, py + ph * 0.475), '詰め替え', font=f['small'], fill=INK, anchor='mm')
    arm(d, (gx + W * 0.09, H * 0.66), (px, py + ph * 0.55), W * 0.025)
    sparkle(d, W * 0.95, H * 0.35, W * 0.025); sparkle(d, W * 0.45, H * 0.4, W * 0.02)
    return gx


def s_oral(d, W, H, f):
    d.rectangle((0, H * 0.82, W, H), fill=(190, 222, 222))
    d.rounded_rectangle((W * 0.62, H * 0.06, W * 0.95, H * 0.62), 30 * K, fill=(235, 245, 250), outline=INK, width=5 * K)
    d.rounded_rectangle((W * 0.64, H * 0.09, W * 0.93, H * 0.59), 24 * K, fill=(200, 230, 245))
    gx, gy, s = W * 0.3, H * GY, W * GS
    gy += chara(d, gx, gy, s, 'happy') * s
    for i in range(7):
        bx, by, r = gx + s * (0.2 + (i % 3) * 0.25), gy + s * (1.45 + (i // 3) * 0.2), s * (0.12 - (i % 2) * 0.03)
        d.ellipse((bx - r, by - r, bx + r, by + r), fill=WH, outline=INK, width=2 * K)
    tx, ty = gx + s * 0.9, gy + s * 1.5
    d.line((tx, ty, tx + s * 1.6, ty + s * 0.9), fill=(90, 170, 230), width=16 * K)
    d.line((tx, ty, tx + s * 1.6, ty + s * 0.9), fill=INK, width=3 * K)
    d.rounded_rectangle((tx - s * 0.32, ty - s * 0.32, tx + s * 0.02, ty + s * 0.05), 6 * K, fill=WH, outline=INK, width=3 * K)
    hand(d, tx + s * 1.3, ty + s * 0.75, W * 0.025)
    sparkle(d, gx - s * 1.5, gy + s * 0.8, W * 0.035, (255, 255, 255)); sparkle(d, gx - s * 1.3, gy + s * 1.8, W * 0.02, (255, 255, 255))
    return gx


def s_iphone(d, W, H, f):
    d.rectangle((0, H * 0.82, W, H), fill=(214, 206, 232))
    gx = W * 0.27
    chara(d, gx, H * GY, W * GS, 'happy')
    X, Y, PW = W * 0.46, H * 0.14, W * 0.17
    phone(d, X, Y, PW, PW * 1.9)
    d.rounded_rectangle((X - W * 0.015, Y - W * 0.015, X + PW + W * 0.015, Y + PW * 1.9 + W * 0.015), 30 * K, outline=(160, 110, 220), width=10 * K)
    for i, c in enumerate([(255, 120, 120), (120, 200, 255), (140, 220, 140)]):
        d.rounded_rectangle((X + PW * (0.18 + i * 0.24), Y + PW * 0.25, X + PW * (0.36 + i * 0.24), Y + PW * 0.43), 6 * K, fill=c)
    d.text((X + PW / 2, Y + PW * 1.15), '♥', font=f['big'], fill=(240, 90, 120), anchor='mm')
    arm(d, (gx + W * 0.09, H * 0.66), (X, H * 0.66), W * 0.025)
    sparkle(d, W * 0.86, H * 0.2, W * 0.03); sparkle(d, W * 0.8, H * 0.62, W * 0.02)
    return gx


def s_cart(d, W, H, f):
    d.rectangle((0, H * 0.82, W, H), fill=(232, 210, 184))
    gx = W * 0.27
    chara(d, gx, H * GY, W * GS, 'normal')
    cx, cy = W * 0.45, H * 0.46
    d.line((cx, cy, cx + W * 0.04, cy + H * 0.06), fill=INK, width=8 * K)
    pts = [(cx + W * 0.03, cy + H * 0.06), (cx + W * 0.36, cy + H * 0.06), (cx + W * 0.32, cy + H * 0.27), (cx + W * 0.07, cy + H * 0.27)]
    d.rounded_rectangle((cx + W * 0.1, cy - H * 0.08, cx + W * 0.22, cy + H * 0.1), 8 * K, fill=(225, 120, 50), outline=INK, width=4 * K)
    d.rounded_rectangle((cx + W * 0.2, cy - H * 0.14, cx + W * 0.31, cy + H * 0.1), 8 * K, fill=(90, 150, 220), outline=INK, width=4 * K)
    d.text((cx + W * 0.255, cy - H * 0.02), 'NEW', font=f['small'], fill=WH, anchor='mm')
    d.polygon(pts, fill=(205, 205, 212), outline=INK)
    d.line(pts + [pts[0]], fill=INK, width=5 * K)
    for t in range(1, 6):
        d.line((pts[0][0] + t * W * 0.055, pts[0][1], pts[3][0] + t * W * 0.042, pts[3][1]), fill=INK, width=3 * K)
    d.line((pts[3][0], pts[3][1], pts[3][0] + W * 0.01, cy + H * 0.33, pts[2][0], cy + H * 0.33), fill=INK, width=6 * K)
    for wx in (pts[3][0] + W * 0.04, pts[2][0] - W * 0.02):
        d.ellipse((wx - W * 0.02, cy + H * 0.31, wx + W * 0.02, cy + H * 0.31 + W * 0.04), fill=INK)
    arm(d, (gx + W * 0.09, cy + H * 0.05), (cx, cy), W * 0.025)
    return gx


DRAW = {'battery': s_battery, 'winter': s_winter, 'refill': s_refill, 'oral': s_oral, 'iphone': s_iphone, 'cart': s_cart}


def draw(im, box, scene, line, fontfn, who=None):
    global CHARA
    CHARA = who or season_chara()
    """im の box（x0,y0,x1,y1）に場面を描く。fontfn(kind, size) は render.py の font。"""
    x0, y0, x1, y1 = [int(v) for v in box]
    W, H = (x1 - x0) * K, (y1 - y0) * K
    c = Image.new('RGBA', (W, H), SCENES[scene]['bg'] + (255,))
    d = ImageDraw.Draw(c)
    f = {'big': fontfn('display', int(W * 0.07)), 'tag': fontfn('bold', int(W * 0.035)), 'small': fontfn('bold', int(W * 0.026))}
    gx = DRAW[scene](d, W, H, f)
    fb = fontfn('bold', int(W * 0.036))
    bw = W * 0.36
    bx0 = min(max(gx - bw / 2, W * 0.03), W * 0.97 - bw)
    bb = (bx0, H * 0.04, bx0 + bw, H * 0.27)
    tx = gx + W * 0.03
    bubble(d, bb, (tx - W * 0.035, H * 0.27, tx + W * 0.02, H * GY + H * 0.02, tx + W * 0.015, H * 0.27), line, fb)
    # 角を丸めて貼る
    m = Image.new('L', (W, H), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, W - 1, H - 1), 36 * K, fill=255)
    c.putalpha(m)
    c = c.resize((x1 - x0, y1 - y0), Image.LANCZOS)
    im.paste(c, (x0, y0), c)
