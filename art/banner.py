"""banner.py — пиксельная заставка README: осьминог трясёт два дерева, листья-задачи падают,
пойманные летят в корзину с галочкой.

Рисуется кодом, без сервисов: python art/banner.py → art/banner.gif (800×400, 40 кадров).
Нужен Pillow. В README показывать с width="800" — пиксели целые, без размытия.

Оглавление:
  1. Настройки и палитра
  2. Пиксельные приёмы — контур, диски, кривые, шрифты
  3. Небо, луна, холмы, земля
  4. Деревья
  5. Листья и светлячки
  6. Осьминог и корзина
  7. Надписи
  8. Кадр и запуск
"""
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw

# ═══ 1. Настройки и палитра ═══════════════════════════════════════════
W, H, SCALE = 200, 100, 4          # логические пиксели; GIF = 800×400
FRAMES, FRAME_MS = 40, 70          # петля 2,8 с; тряска — 2 удара за петлю
GROUND = 88                        # верх травы

INK = (26, 15, 46)                 # контур всего
SKY = [(11, 16, 38), (27, 31, 74), (58, 42, 107), (107, 58, 122)]
STAR = [(255, 244, 214), (170, 180, 255)]
MOON, MOON_SHADE = (244, 233, 193), (214, 200, 160)
MOON_GLOW = [(36, 40, 92), (58, 56, 124)]
HILL, HILL_TOP, PINE = (36, 32, 74), (52, 46, 98), (30, 26, 62)
GRASS, GRASS_LIGHT, DIRT = (63, 143, 74), (108, 196, 106), (31, 59, 44)
TRUNK, TRUNK_DARK = (107, 66, 38), (74, 44, 24)
CANOPY = [(31, 107, 58), (47, 154, 76), (111, 211, 107)]
LEAVES = [(255, 211, 77), (255, 138, 61), (123, 224, 123), (255, 238, 140)]
FIREFLY, FIREFLY_HALO = (230, 255, 140), (110, 150, 70)
BODY, BODY_DARK, BODY_LIGHT = (180, 76, 214), (122, 42, 158), (229, 140, 255)
SUCKER, CHEEK, WHITE = (236, 160, 240), (255, 122, 168), (255, 255, 255)
BASKET, BASKET_DARK, BASKET_RIM = (160, 104, 52), (112, 70, 34), (206, 146, 80)
CHECK, CHECK_GLOW = (123, 224, 123), (210, 255, 190)
TITLE = [(255, 230, 109), (255, 196, 70), (255, 159, 28)]
SHINE, SUBTITLE = (255, 252, 230), (185, 168, 230)

TREES = [(36, -1), (164, 1)]       # центр дерева по x, сторона (-1 левое)
BASKET_X, BASKET_TOP = 100, 79     # центр корзины, верх кромки

# ═══ 2. Пиксельные приёмы — контур, диски, кривые, шрифты ══════════════
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


BIG = {                                             # 5×7 — заголовок
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "C": [".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    "U": ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
}
SMALL = {                                           # 3×5 — подпись
    "A": [".#.", "#.#", "###", "#.#", "#.#"], "B": ["##.", "#.#", "##.", "#.#", "##."],
    "D": ["##.", "#.#", "#.#", "#.#", "##."], "E": ["###", "#..", "##.", "#..", "###"],
    "H": ["#.#", "#.#", "###", "#.#", "#.#"], "I": ["###", ".#.", ".#.", ".#.", "###"],
    "K": ["#.#", "#.#", "##.", "#.#", "#.#"], "L": ["#..", "#..", "#..", "#..", "###"],
    "N": ["##.", "#.#", "#.#", "#.#", "#.#"], "O": [".#.", "#.#", "#.#", "#.#", ".#."],
    "P": ["##.", "#.#", "##.", "#..", "#.."], "R": ["##.", "#.#", "##.", "#.#", "#.#"],
    "S": [".##", "#..", ".#.", "..#", "##."], "T": ["###", ".#.", ".#.", ".#.", ".#."],
    "·": ["...", "...", ".#.", "...", "..."], " ": ["...", "...", "...", "...", "..."],
}


def glyph_pixels(text, font, cell, gap):
    """(x, y, row) каждого закрашенного пикселя строки; ширина строки."""
    w = len(font[text[0]][0])
    pts = [(((n * (w + gap)) + col) * cell + dx, row * cell + dy, row)
           for n, ch in enumerate(text) for row, line in enumerate(font[ch])
           for col, mark in enumerate(line) if mark == "#"
           for dx in range(cell) for dy in range(cell)]
    return pts, (len(text) * (w + gap) - gap) * cell

# ═══ 3. Небо, луна, холмы, земля ═══════════════════════════════════════
BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]
STARS = [(random.Random(7 + i).randrange(W), random.Random(70 + i).randrange(GROUND - 30), i % 3)
         for i in range(46)]
MOON_XY, MOON_R = (16, 12), 6


def sky(img, f):
    """Градиент полосами с растровым переходом, луна с ореолом, звёзды мигают."""
    px = img.load()
    for y in range(GROUND):
        t = y / (GROUND - 1) * (len(SKY) - 1)
        band = min(int(t), len(SKY) - 2)
        for x in range(W):
            px[x, y] = SKY[band + 1] if (t - band) * 16 > BAYER[y % 4][x % 4] else SKY[band]
    d = ImageDraw.Draw(img)
    for r, color in zip((MOON_R + 4, MOON_R + 2), MOON_GLOW):
        disc(d, *MOON_XY, r, color)
    for i, (x, y, kind) in enumerate(STARS):
        if abs(x - MOON_XY[0]) < 12 and abs(y - MOON_XY[1]) < 12:
            continue
        if (f // 4 + i) % 5:                        # каждая пятая фаза — погасла
            px[x, y] = STAR[kind % 2]
            if kind == 0 and (f // 10 + i) % 2:     # крупные иногда с лучиками
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    if 0 <= x + dx < W and 0 <= y + dy < H:
                        px[x + dx, y + dy] = STAR[1]
    disc(d, *MOON_XY, MOON_R, MOON)
    for x, y in ((14, 10), (15, 10), (18, 14), (13, 14), (17, 9)):
        d.point((x, y), fill=MOON_SHADE)


def ground(img):
    d = ImageDraw.Draw(img)
    hills = [(x, GROUND - 10 - round(6 * math.sin(x / 17) + 4 * math.sin(x / 7 + 1))) for x in range(W)]
    for x, top in hills:
        d.line([(x, top), (x, GROUND)], fill=HILL)
        d.point((x, top), fill=HILL_TOP)
    for x in (70, 76, 124, 131, 190, 8):            # ёлочки на холмах — глубина
        top = hills[x][1]
        for k in range(5):
            d.line([(x - k // 2, top - 5 + k), (x + k // 2, top - 5 + k)], fill=PINE)
    d.rectangle([0, GROUND, W, H], fill=DIRT)
    d.line([(0, GROUND), (W, GROUND)], fill=GRASS)
    d.line([(0, GROUND + 1), (W, GROUND + 1)], fill=GRASS)
    rnd = random.Random(3)
    for x in range(0, W, 3):
        d.point((x + rnd.randrange(2), GROUND - 1), fill=GRASS_LIGHT)

# ═══ 4. Деревья ════════════════════════════════════════════════════════
def sway(f):
    """Тряска: два удара за петлю, крона ходит сильнее ствола."""
    return round(wave(f, FRAMES / 2, 2.2))


def trunk_shift(f, y):
    """Сдвиг ствола на высоте y: верх ходит, корень стоит."""
    return round(sway(f) * (GROUND - y) / (GROUND - 50) * 0.6)


def canopy_blobs(cx):
    rnd = random.Random(cx)
    base = [(cx + rnd.uniform(-18, 18), 36 + rnd.uniform(-12, 12), rnd.uniform(8, 13)) for _ in range(9)]
    base += [(cx, 36, 19)]
    mid = [(x - 2, y - 3, r * 0.7) for x, y, r in base]
    light = [(x - 4, y - 6, r * 0.32) for x, y, r in base if rnd.random() < 0.7]
    return base, mid, light


BLOBS = {cx: canopy_blobs(cx) for cx, _ in TREES}


def tree(f, cx):
    layer = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(layer)
    for y in range(50, GROUND + 1):
        off = trunk_shift(f, y)
        d.line([(cx - 4 + off, y), (cx + 3 + off, y)], fill=TRUNK)
        d.line([(cx - 4 + off, y), (cx - 3 + off, y)], fill=TRUNK_DARK)
    for blobs, color in zip(BLOBS[cx], CANOPY):
        for x, y, r in blobs:
            disc(d, x + sway(f), y, r, color)
    return outline(layer)

# ═══ 5. Листья и светлячки ═════════════════════════════════════════════
def make_leaves():
    rnd, leaves = random.Random(11), []
    for i in range(26):
        cx, _ = TREES[i % 2]
        leaves.append(dict(
            x=cx + rnd.uniform(-20, 20), y=rnd.uniform(44, 54), period=rnd.choice([FRAMES, FRAMES // 2]),
            phase=rnd.randrange(FRAMES), amp=rnd.uniform(1.5, 4), color=rnd.choice(LEAVES),
            big=rnd.random() < 0.4))
    return leaves


LEAF_LIST = make_leaves()
CAUGHT = [dict(x=x, y=50, phase=k * FRAMES // 4, color=LEAVES[k]) for k, x in enumerate((54, 146, 50, 150))]
CATCH_FRAMES = FRAMES // 2                          # полёт пойманного листа до корзины


def leaf(d, x, y, color, big):
    w = 2 if big else 1
    d.rectangle([x, y, x + w, y + 1], fill=color)
    d.point((x + w, y + 1), fill=INK)               # тень-кромка — лист читается на небе


def leaves(img, f):
    d = ImageDraw.Draw(img)
    for lf in LEAF_LIST:
        p = ((f + lf["phase"]) % lf["period"]) / lf["period"]
        y = lf["y"] + p * (GROUND + 2 - lf["y"])
        if y <= GROUND + 1:
            leaf(d, round(lf["x"] + wave(p, 1, lf["amp"]) + sway(f) * (1 - p)), round(y), lf["color"], lf["big"])


def caught(img, f):
    """Пойманные листья: дугой из кроны в корзину. Возвращает, вспыхнула ли корзина."""
    d, flash = ImageDraw.Draw(img), False
    for lf in CAUGHT:
        t = (f - lf["phase"]) % FRAMES
        if t < CATCH_FRAMES:
            p = t / CATCH_FRAMES
            x = lf["x"] + (BASKET_X - lf["x"]) * p
            y = lf["y"] - 8 * math.sin(math.pi * p) + (BASKET_TOP - 2 - lf["y"]) * p * p
            leaf(d, round(x), round(y), lf["color"], True)
        elif t < CATCH_FRAMES + 4:
            flash = True
            sparkle(d, t - CATCH_FRAMES)
    return flash


def sparkle(d, age):
    r = 2 + age
    cx, cy = BASKET_X, BASKET_TOP - 4
    for dx, dy in ((r, 0), (-r, 0), (0, r), (0, -r)):
        d.point((cx + dx, cy + dy), fill=SHINE if age < 2 else LEAVES[3])
    d.point((cx, cy), fill=WHITE)


FIREFLIES = [(random.Random(40 + i).uniform(14, 186), random.Random(60 + i).uniform(58, 84), i / 8)
             for i in range(8)]


def fireflies(img, f):
    d = ImageDraw.Draw(img)
    for i, (x0, y0, ph) in enumerate(FIREFLIES):
        if (f + i * 5) % 10 >= 7:
            continue
        x, y = round(x0 + wave(f, FRAMES, 6, ph)), round(y0 + wave(f, FRAMES / 2, 3, ph))
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            d.point((x + dx, y + dy), fill=FIREFLY_HALO)
        d.point((x, y), fill=FIREFLY)

# ═══ 6. Осьминог и корзина ═════════════════════════════════════════════
CX, CY = 100, 46                                    # центр головы


def tentacles(f, bob):
    """8 щупалец: 4 держат стволы, 2 держат корзину, 2 вьются по земле.
    Каждое — (начало, опора кривой, конец, сдвиг волны, закрутить ли кончик)."""
    out = []
    for cx, side in TREES:
        for k, (ay, ty) in enumerate(((54, 64), (62, 78))):
            start, end = (CX + side * 12, ay + bob), (cx - side * 5 + trunk_shift(f, ty), ty)
            out.append((start, ((start[0] + end[0]) / 2, min(start[1], end[1]) - 10 + k * 8), end, 5 + k, False))
    for i, (gx, side) in enumerate(((66, -1), (134, 1))):
        start, end = (CX + side * 9, 66 + bob), (gx + round(wave(f, FRAMES, 2, i / 2)), GROUND + 2)
        out.append((start, ((start[0] + end[0]) / 2 + side * 6, GROUND - 2), end, 3 + i, True))
    return out


def holders(bob):
    """Два щупальца держат корзину за края кромки."""
    return [((CX + side * 5, 66 + bob), (CX + side * 15, 74), (BASKET_X + side * 10, BASKET_TOP), 9, False)
            for side in (-1, 1)]


def draw_tentacle(d, f, start, ctrl, end, seed, curl):
    pts = bezier(start, ctrl, end, 28)
    if curl:                                        # кончик закручен колечком вверх
        ex, ey = end
        turn = 1 if ex > start[0] else -1
        pts += [(ex + turn * 3.2 * math.sin(a), ey - 3.2 + 3.2 * math.cos(a)) for a in
                (i * 0.55 for i in range(1, 11))]
    n = len(pts)
    body = [(x, y + wave(f, FRAMES / 2, 0.9 * i / (n - 1), seed / 7), 2.8 - 2.0 * i / (n - 1))
            for i, (x, y) in enumerate(pts)]
    for x, y, r in body:
        disc(d, x, y + 1, r, BODY_DARK)
    for x, y, r in body:
        disc(d, x, y, r, BODY)
    for x, y, r in body[3:-6:3]:                    # присоски — ровным рядом по нижней кромке
        d.point((round(x), round(y + r)), fill=SUCKER)


def basket(d):
    for row, y in enumerate(range(BASKET_TOP + 1, GROUND + 1)):
        half = 11 - row // 3
        d.line([(BASKET_X - half, y), (BASKET_X + half - 1, y)], fill=BASKET if row % 2 else BASKET_DARK)
    d.line([(BASKET_X - 12, BASKET_TOP), (BASKET_X + 11, BASKET_TOP)], fill=BASKET_RIM)


def basket_front(d, flash):
    """Горка листьев над кромкой и галочка на боку — вспыхивает, когда лист пойман."""
    for i, x in enumerate(range(BASKET_X - 8, BASKET_X + 8, 2)):
        d.rectangle([x, BASKET_TOP - 2 + i % 2, x + 1, BASKET_TOP - 1], fill=LEAVES[i % len(LEAVES)])
    color = CHECK_GLOW if flash else CHECK
    for x, y in ((-4, 4), (-3, 5), (-2, 6), (-1, 5), (0, 4), (1, 3), (2, 2), (3, 1)):
        d.point((BASKET_X + x, BASKET_TOP + y), fill=color)


def octopus(f, flash):
    layer = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(layer)
    bob = round(wave(f, FRAMES / 2, 1, 0.25))
    for t in tentacles(f, bob):
        draw_tentacle(d, f, *t)
    cy = CY + bob
    d.ellipse([CX - 15, cy - 12, CX + 15, cy + 20], fill=BODY_DARK)
    d.ellipse([CX - 15, cy - 14, CX + 15, cy + 18], fill=BODY)
    d.ellipse([CX - 10, cy - 11, CX - 1, cy - 4], fill=BODY_LIGHT)
    d.rectangle([CX - 8, cy - 10, CX - 7, cy - 9], fill=WHITE)
    basket(d)
    for t in holders(bob):
        draw_tentacle(d, f, *t)
    layer = outline(layer)
    d = ImageDraw.Draw(layer)
    basket_front(d, flash)
    face(d, f, cy)
    return layer


def face(d, f, cy):
    look = round(wave(f, FRAMES, 1.2))              # оглядывается: влево — вправо
    for ex in (CX - 7, CX + 7):
        if f in (30, 31):                           # моргнул
            d.line([(ex - 2, cy + 2), (ex + 2, cy + 2)], fill=INK)
            continue
        d.ellipse([ex - 3, cy - 2, ex + 3, cy + 5], fill=INK)
        d.ellipse([ex - 2, cy - 1, ex + 2, cy + 4], fill=WHITE)
        d.rectangle([ex + look - 1, cy + 1, ex + look, cy + 3], fill=INK)
        d.point((ex + look - 1, cy + 1), fill=WHITE)
    for x in (CX - 12, CX + 10):
        d.line([(x, cy + 7), (x + 2, cy + 7)], fill=CHEEK)
    for x, y in ((-3, 8), (-2, 9), (-1, 9), (0, 9), (1, 9), (2, 9), (3, 8)):
        d.point((CX + x, cy + y), fill=INK)

# ═══ 7. Надписи ════════════════════════════════════════════════════════
TITLE_PTS, TITLE_W = glyph_pixels("OCTOPUS", BIG, cell=2, gap=1)
TITLE_LEFT, TITLE_TOP = (W - TITLE_W) // 2, 3
SUB_PTS, SUB_W = glyph_pixels("TASK TREE · BOTH ENDS · ALL IN PARALLEL", SMALL, cell=1, gap=1)
SUB_LEFT, SUB_TOP = (W - SUB_W) // 2, GROUND + 5


def title(f):
    """Заголовок с градиентом и бликом, который пробегает раз за петлю."""
    layer = Image.new("RGBA", (W, H))
    px = layer.load()
    shine = -12 + (TITLE_W + 24) * (f % FRAMES) / (FRAMES * 0.45)
    for x, y, row in TITLE_PTS:
        lit = 0 <= x + y - shine < 4
        px[TITLE_LEFT + x, TITLE_TOP + y] = (SHINE if lit else TITLE[min(row * 3 // 7, 2)]) + (255,)
    shifted = Image.new("RGBA", (W, H))
    shifted.paste(layer, (1, 1))
    out = Image.new("RGBA", (W, H))
    out.paste(INK + (255,), mask=shifted)
    out.alpha_composite(outline(layer))
    return out


def subtitle(img):
    px = img.load()
    for x, y, _ in SUB_PTS:
        px[SUB_LEFT + x + 1, SUB_TOP + y + 1] = INK
        px[SUB_LEFT + x, SUB_TOP + y] = SUBTITLE

# ═══ 8. Кадр и запуск ══════════════════════════════════════════════════
def frame(f):
    img = Image.new("RGBA", (W, H))
    sky(img, f)
    ground(img)
    for cx, _ in TREES:
        img.alpha_composite(tree(f, cx))
    leaves(img, f)
    flash = caught(img, f)
    img.alpha_composite(octopus(f, flash))
    fireflies(img, f)
    img.alpha_composite(title(f))
    subtitle(img)
    return img.convert("RGB").resize((W * SCALE, H * SCALE), Image.NEAREST)


def main(out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = [frame(f) for f in range(FRAMES)]
    frames[0].save(out_dir / "banner.gif", save_all=True, append_images=frames[1:],
                   duration=FRAME_MS, loop=0, optimize=True)
    print(f"banner.gif: {FRAMES} frames, {W * SCALE}x{H * SCALE}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent)
