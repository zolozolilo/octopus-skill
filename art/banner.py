"""banner.py — пиксельная заставка README: осьминог трясёт два дерева, листья-задачи падают.

Рисуется кодом, без сервисов: python art/banner.py → art/banner.gif (и art/banner.png — первый кадр).
Нужен Pillow.

Оглавление:
  1. Настройки и палитра
  2. Пиксельные приёмы — контур, диски, кривые
  3. Небо и земля
  4. Деревья
  5. Листья
  6. Осьминог
  7. Заголовок
  8. Кадр и запуск
"""
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw

# ═══ 1. Настройки и палитра ═══════════════════════════════════════════
W, H, SCALE = 200, 100, 5          # логические пиксели; GIF = 1000×500
FRAMES, FRAME_MS = 24, 90          # петля 2,2 с; тряска — 2 удара за петлю
GROUND = 88                        # верх травы

INK = (26, 15, 46)                 # контур всего
SKY = [(11, 16, 38), (27, 31, 74), (58, 42, 107), (107, 58, 122)]
STAR = [(255, 244, 214), (170, 180, 255)]
HILL, HILL_TOP = (36, 32, 74), (52, 46, 98)
GRASS, GRASS_LIGHT, DIRT = (63, 143, 74), (108, 196, 106), (31, 59, 44)
TRUNK, TRUNK_DARK = (107, 66, 38), (74, 44, 24)
CANOPY = [(31, 107, 58), (47, 154, 76), (111, 211, 107)]
LEAVES = [(255, 211, 77), (255, 138, 61), (123, 224, 123), (255, 238, 140)]
BODY, BODY_DARK, BODY_LIGHT = (180, 76, 214), (122, 42, 158), (229, 140, 255)
SUCKER, CHEEK, WHITE = (236, 160, 240), (255, 122, 168), (255, 255, 255)
TITLE = [(255, 230, 109), (255, 196, 70), (255, 159, 28)]

TREES = [(36, -1), (164, 1)]       # центр дерева по x, сторона (-1 левое)

# ═══ 2. Пиксельные приёмы — контур, диски, кривые ══════════════════════
def outline(layer):
    """Обвести непрозрачное 1-пиксельным контуром INK снаружи."""
    px, out = layer.load(), layer.copy()
    opx = out.load()
    for y in range(H):
        for x in range(W):
            if px[x, y][3]:
                continue
            near = ((x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
            if any(0 <= nx < W and 0 <= ny < H and px[nx, ny][3] for nx, ny in near):
                opx[x, y] = INK + (255,)
    return out


def disc(draw, cx, cy, r, color):
    draw.ellipse([round(cx - r), round(cy - r), round(cx + r), round(cy + r)], fill=color)


def bezier(p0, p1, p2, steps):
    """Точки квадратичной кривой Безье от p0 через p1 к p2."""
    pts = []
    for i in range(steps + 1):
        s = i / steps
        a, b, c = (1 - s) ** 2, 2 * (1 - s) * s, s * s
        pts.append((a * p0[0] + b * p1[0] + c * p2[0], a * p0[1] + b * p1[1] + c * p2[1]))
    return pts


def wave(f, period, amp, shift=0.0):
    return amp * math.sin(2 * math.pi * (f / period + shift))

# ═══ 3. Небо и земля ═══════════════════════════════════════════════════
BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]
STARS = [(random.Random(7 + i).randrange(W), random.Random(70 + i).randrange(GROUND - 30), i % 3)
         for i in range(46)]


def sky(img, f):
    """Градиент полосами с растровым переходом, звёзды мигают."""
    px = img.load()
    for y in range(GROUND):
        t = y / (GROUND - 1) * (len(SKY) - 1)
        band, frac = min(int(t), len(SKY) - 2), t - min(int(t), len(SKY) - 2)
        for x in range(W):
            px[x, y] = SKY[band + 1] if frac * 16 > BAYER[y % 4][x % 4] else SKY[band]
    for i, (x, y, kind) in enumerate(STARS):
        if (f // 3 + i) % 7:                        # каждая седьмая фаза — погасла
            px[x, y] = STAR[kind % 2]
            if kind == 0 and (f // 6 + i) % 2:      # крупные иногда с лучиками
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    if 0 <= x + dx < W and 0 <= y + dy < H:
                        px[x + dx, y + dy] = STAR[1]


def ground(img):
    d = ImageDraw.Draw(img)
    hills = [(x, GROUND - 10 - round(6 * math.sin(x / 17) + 4 * math.sin(x / 7 + 1))) for x in range(W)]
    for x, top in hills:
        d.line([(x, top), (x, GROUND)], fill=HILL)
        d.point((x, top), fill=HILL_TOP)
    d.rectangle([0, GROUND, W, H], fill=DIRT)
    d.line([(0, GROUND), (W, GROUND)], fill=GRASS)
    d.line([(0, GROUND + 1), (W, GROUND + 1)], fill=GRASS)
    rnd = random.Random(3)
    for x in range(0, W, 3):
        d.point((x + rnd.randrange(2), GROUND - 1), fill=GRASS_LIGHT)
        if rnd.random() < 0.3:
            d.point((x, GROUND + 3 + rnd.randrange(8)), fill=GRASS)

# ═══ 4. Деревья ════════════════════════════════════════════════════════
def sway(f):
    """Тряска: два удара за петлю, крона ходит сильнее ствола."""
    return round(wave(f, FRAMES / 2, 2.2))


def canopy_blobs(cx, side):
    rnd = random.Random(cx)
    base = [(cx + rnd.uniform(-18, 18), 34 + rnd.uniform(-14, 12), rnd.uniform(8, 13)) for _ in range(9)]
    base += [(cx, 34, 20)]
    mid = [(x - 2, y - 3, r * 0.7) for x, y, r in base]
    light = [(x - 4, y - 6, r * 0.32) for x, y, r in base if rnd.random() < 0.7]
    return base, mid, light


BLOBS = {cx: canopy_blobs(cx, side) for cx, side in TREES}


def tree(f, cx):
    layer = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(layer)
    dx = sway(f)
    for y in range(50, GROUND + 1):                 # ствол гнётся: верх ходит, корень стоит
        off = round(dx * (GROUND - y) / (GROUND - 50) * 0.6)
        d.line([(cx - 4 + off, y), (cx + 3 + off, y)], fill=TRUNK)
        d.line([(cx - 4 + off, y), (cx - 3 + off, y)], fill=TRUNK_DARK)
    base, mid, light = BLOBS[cx]
    for blobs, color in ((base, CANOPY[0]), (mid, CANOPY[1]), (light, CANOPY[2])):
        for x, y, r in blobs:
            disc(d, x + dx, y, r, color)
    return outline(layer)

# ═══ 5. Листья ═════════════════════════════════════════════════════════
def make_leaves():
    rnd, leaves = random.Random(11), []
    for i in range(30):
        cx, _ = TREES[i % 2]
        period = rnd.choice([FRAMES, FRAMES, FRAMES // 2])
        leaves.append(dict(
            x=cx + rnd.uniform(-20, 20), y=rnd.uniform(44, 54), period=period,
            phase=rnd.randrange(FRAMES), amp=rnd.uniform(1.5, 4), color=rnd.choice(LEAVES),
            big=rnd.random() < 0.4))
    return leaves


LEAF_LIST = make_leaves()


def leaves(img, f):
    d = ImageDraw.Draw(img)
    for lf in LEAF_LIST:
        p = ((f + lf["phase"]) % lf["period"]) / lf["period"]
        y = lf["y"] + p * (GROUND + 2 - lf["y"])
        x = lf["x"] + wave(p, 1, lf["amp"]) + sway(f) * (1 - p)
        if y > GROUND + 1:
            continue
        x, y = round(x), round(y)
        w = 2 if lf["big"] else 1
        d.rectangle([x, y, x + w, y + 1], fill=lf["color"])
        d.point((x + w, y + 1), fill=INK)          # тень-кромка — лист читается на небе

# ═══ 6. Осьминог ═══════════════════════════════════════════════════════
CX, CY = 100, 46                                    # центр головы


def tentacles(f, bob):
    """8 щупалец: 4 держат стволы (по 2 на дерево), 4 вьются по земле."""
    grip = []
    for cx, side in TREES:
        trunk_x = cx - side * 5
        for k, (ay, ty) in enumerate(((54, 64), (62, 78))):
            off = round(sway(f) * (GROUND - ty) / (GROUND - 50) * 0.6)
            start = (CX + side * 12, ay + bob)
            end = (trunk_x + off, ty)
            ctrl = ((start[0] + end[0]) / 2, min(start[1], end[1]) - 10 + k * 8)
            grip.append((start, ctrl, end, 5 + k))
    ground_ones = []
    for i, (gx, side) in enumerate(((66, -1), (84, -1), (116, 1), (134, 1))):
        start = (CX + side * (4 + i % 2 * 5), 66 + bob)
        end = (gx + round(wave(f, FRAMES, 2, i / 4)), GROUND + 2)
        ctrl = ((start[0] + end[0]) / 2 + side * 6, GROUND - 2)
        ground_ones.append((start, ctrl, end, 3 + i))
    return grip + ground_ones


def draw_tentacle(d, f, start, ctrl, end, seed, curl):
    pts = bezier(start, ctrl, end, 28)
    if curl:                                        # кончик закручен колечком вверх
        ex, ey = end
        turn = 1 if ex > start[0] else -1
        pts += [(ex + turn * 3.2 * math.sin(a), ey - 3.2 + 3.2 * math.cos(a)) for a in
                (i * 0.55 for i in range(1, 11))]
    n = len(pts)
    body = []
    for i, (x, y) in enumerate(pts):
        s = i / (n - 1)
        body.append((x, y + wave(f, FRAMES / 2, 0.9 * s, seed / 7), 2.8 - 2.0 * s))
    for x, y, r in body:
        disc(d, x, y + 1, r, BODY_DARK)
    for x, y, r in body:
        disc(d, x, y, r, BODY)
    for x, y, r in body[3:-6:3]:                    # присоски — ровным рядом по нижней кромке
        d.point((round(x), round(y + r)), fill=SUCKER)


def octopus(f):
    layer = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(layer)
    bob = round(wave(f, FRAMES / 2, 1, 0.25))
    for start, ctrl, end, seed in tentacles(f, bob):
        draw_tentacle(d, f, start, ctrl, end, seed, curl=end[1] > GROUND)
    cy = CY + bob
    d.ellipse([CX - 15, cy - 14 + 2, CX + 15, cy + 18 + 2], fill=BODY_DARK)
    d.ellipse([CX - 15, cy - 14, CX + 15, cy + 18], fill=BODY)
    d.ellipse([CX - 10, cy - 11, CX - 1, cy - 4], fill=BODY_LIGHT)
    d.rectangle([CX - 8, cy - 10, CX - 7, cy - 9], fill=WHITE)
    layer = outline(layer)
    face(ImageDraw.Draw(layer), f, cy)
    return layer


def face(d, f, cy):
    blink = f in (17, 18)
    for ex in (CX - 7, CX + 7):
        if blink:
            d.line([(ex - 2, cy + 2), (ex + 2, cy + 2)], fill=INK)
            continue
        d.ellipse([ex - 3, cy - 2, ex + 3, cy + 5], fill=INK)
        d.ellipse([ex - 2, cy - 1, ex + 2, cy + 4], fill=WHITE)
        look = 1 if ex < CX else -1                 # глаза сведены к середине — хитро
        d.rectangle([ex + look - 1 + (look < 0), cy + 1, ex + look + (look < 0), cy + 3], fill=INK)
        d.point((ex - 1, cy), fill=WHITE)
    for x in (CX - 12, CX + 10):
        d.line([(x, cy + 7), (x + 2, cy + 7)], fill=CHEEK)
    for x, y in ((-3, 8), (-2, 9), (-1, 9), (0, 9), (1, 9), (2, 9), (3, 8)):
        d.point((CX + x, cy + y), fill=INK)

# ═══ 7. Заголовок ══════════════════════════════════════════════════════
FONT = {
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "C": [".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    "U": ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
}


def title(text="OCTOPUS", top=3, cell=2):
    layer = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(layer)
    width = len(text) * 6 * cell - cell
    left = (W - width) // 2
    for n, ch in enumerate(text):
        for row, line in enumerate(FONT[ch]):
            color = TITLE[min(row * len(TITLE) // 7, len(TITLE) - 1)]
            for col, mark in enumerate(line):
                if mark == "#":
                    x, y = left + (n * 6 + col) * cell, top + row * cell
                    d.rectangle([x, y, x + cell - 1, y + cell - 1], fill=color)
    shifted = Image.new("RGBA", (W, H))
    shifted.paste(layer, (1, 1))
    shadow = Image.new("RGBA", (W, H))
    shadow.paste(INK + (255,), mask=shifted)
    shadow.alpha_composite(outline(layer))
    return shadow

# ═══ 8. Кадр и запуск ══════════════════════════════════════════════════
def frame(f, head):
    img = Image.new("RGBA", (W, H))
    sky(img, f)
    ground(img)
    for cx, _ in TREES:
        img.alpha_composite(tree(f, cx))
    leaves(img, f)
    img.alpha_composite(octopus(f))
    img.alpha_composite(head)
    return img.convert("RGB").resize((W * SCALE, H * SCALE), Image.NEAREST)


def main(out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    head = title()
    frames = [frame(f, head) for f in range(FRAMES)]
    frames[0].save(out_dir / "banner.png")
    frames[0].save(out_dir / "banner.gif", save_all=True, append_images=frames[1:],
                   duration=FRAME_MS, loop=0, optimize=True)
    print(f"banner.gif: {FRAMES} frames, {W * SCALE}x{H * SCALE}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent)
