"""skorost-sveta.py — анимация «скорость света»: осьминог на микроволновке греет кэш, в щупальцах
деревья задач, звёзды летят полосами, ток бежит по кабелю, галочки загораются по одной.

Рисуется кодом: python art/skorost-sveta.py → art/skorost-sveta.gif (512×512, 32 кадра).
Нужен Pillow. В README показывать с width="512" — пиксели целые.

Оглавление:
  1. Настройки и палитра
  2. Кисть — пиксели, фигуры, смешивание
  3. Небо и звёзды-полосы
  4. Земля, кабель и вышка
  5. Микроволновка
  6. Щупальца, деревья, летящие листья
  7. Голова
  8. Кадр и запуск
"""
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw

# ═══ 1. Настройки и палитра ═══════════════════════════════════════════
W = H = 128                        # логические пиксели
SCALE, FRAMES, FRAME_MS = 4, 32, 70

P = {
    "sky0": (12, 14, 38), "sky1": (34, 20, 64), "star": (255, 246, 196), "star2": (150, 190, 255),
    "out": (22, 16, 34),
    "oct_hi": (226, 190, 255), "oct": (186, 136, 250), "oct_sh": (150, 100, 220),
    "cup": (250, 220, 255), "cheek": (255, 150, 190), "eye": (255, 255, 255), "pupil": (40, 28, 70),
    "iris": (70, 50, 120),
    "mw_hi": (226, 232, 240), "mw": (182, 190, 204), "mw_sh": (124, 132, 150), "mw_dk": (80, 86, 104),
    "glass": (28, 34, 52), "glow": (255, 168, 64), "glow2": (255, 214, 120),
    "lcd": (18, 40, 28), "amber": (255, 176, 0), "btn_r": (236, 72, 72), "btn": (96, 104, 124),
    "leaf": (70, 186, 96), "leaf_hi": (140, 230, 120), "leaf_sh": (34, 120, 70), "trunk": (120, 78, 44),
    "box": (0, 120, 214), "folder": (250, 196, 64), "check": (120, 255, 140),
    "volt": (255, 230, 60), "volt2": (255, 255, 200), "ground": (26, 24, 52), "reflect": (60, 44, 40),
    "steel": (150, 160, 178), "steel_hi": (200, 208, 222), "insul": (120, 220, 255),
}


def wave(f, period, amp, shift=0.0):
    return amp * math.sin(2 * math.pi * (f / period + shift))

# ═══ 2. Кисть — пиксели, фигуры, смешивание ═══════════════════════════
class Brush:
    """Рисование на одном кадре: цвет — имя из P или кортеж RGB."""

    def __init__(self, img):
        self.img, self.d = img, ImageDraw.Draw(img)

    @staticmethod
    def rgb(c):
        return P[c] if isinstance(c, str) else c

    def px(self, x, y, c):
        if 0 <= x < W and 0 <= y < H:
            self.img.putpixel((int(x), int(y)), self.rgb(c))

    def rect(self, x0, y0, x1, y1, c):
        self.d.rectangle([x0, y0, x1, y1], fill=self.rgb(c))

    def disc(self, cx, cy, r, c):
        self.d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=self.rgb(c))

    def line(self, a, b, c, w=1):
        self.d.line([a, b], fill=self.rgb(c), width=w)

    def blend(self, x, y, c, a):
        if 0 <= x < W and 0 <= y < H:
            base, c = self.img.getpixel((int(x), int(y))), self.rgb(c)
            self.img.putpixel((int(x), int(y)), tuple(int(base[i] + (c[i] - base[i]) * a) for i in range(3)))

# ═══ 3. Небо и звёзды-полосы ═══════════════════════════════════════════
def sky_image():
    img = Image.new("RGB", (W, H))
    for y in range(H):
        for x in range(W):
            k = min(1, (y / H + ((x + y) % 2) * 0.03) * 1.2)
            img.putpixel((x, y), tuple(int(P["sky0"][i] + (P["sky1"][i] - P["sky0"][i]) * k) for i in range(3)))
    return img


SKY = sky_image()
rnd = random.Random(7)
WARP = [(rnd.randrange(W), rnd.randrange(70), rnd.choice([4, 8]), rnd.choice(["star", "star", "star2"]))
        for _ in range(34)]
BIG_STARS = [(14, 10), (108, 16), (60, 6), (92, 40)]


def stars(b, f):
    """Звёзды летят влево полосами (мы летим вправо); за петлю — целое число кругов."""
    for x0, y, speed, c in WARP:
        x = (x0 - speed * f) % W
        b.px(x, y, c)
        for t in range(1, speed // 2 + 1):          # хвост позади — справа
            b.blend(x + t, y, b.rgb(c), 0.6 - 0.5 * t / (speed // 2 + 1))
    for i, (x, y) in enumerate(BIG_STARS):
        if (f // 4 + i) % 4:
            for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
                b.px(x + dx, y + dy, "star")

# ═══ 4. Земля, кабель и вышка ══════════════════════════════════════════
def ground(b, f):
    b.rect(0, 110, W - 1, H - 1, "ground")
    for x in range(W):                              # кабель сети; ток бежит влево — к микроволновке
        b.px(x, 116, "volt"); b.px(x, 117, "glow"); b.px(x, 115, "glow")
        if (x + f * 2) % 8 == 0:
            b.px(x, 114, "volt2"); b.px(x, 118, "volt2"); b.px(x, 116, "volt2")
    for y in range(119, H):
        for x in range(W):
            if (x + y) % 3 == 0:
                b.px(x, y, "reflect")


def tower(b, f):
    """Вышка ЛЭП: решётка, траверсы с изоляторами, провода за кадр, розетка на ноге."""
    for a, c in (((107, 116), (114, 40)), ((127, 116), (120, 40))):
        b.line(a, c, "steel", 2)
    for y in range(48, 116, 10):
        t0, t1 = (y - 40) / 76, min(1, (y + 10 - 40) / 76)
        l0, r0, l1, r1 = 114 - 7 * t0, 120 + 7 * t0, 114 - 7 * t1, 120 + 7 * t1
        b.line((l0, y), (r0, y), "steel")
        b.line((l0, y), (r1, min(116, y + 10)), "steel")
        b.line((r0, y), (l1, min(116, y + 10)), "steel")
    for y, x_left in ((44, 100), (54, 102)):
        b.line((x_left, y), (127, y), "steel_hi", 2)
        for x in (x_left + 1, 126):
            b.line((x, y + 1), (x, y + 4), "insul")
            b.px(x, y + 5, "volt2")
    for y in (49, 59):
        for x in range(100, 128):
            b.px(x, y + int(2 * ((x - 114) / 14) ** 2), "volt")
    b.line((114, 40), (117, 34), "steel_hi"); b.line((120, 40), (117, 34), "steel_hi")
    b.px(117, 33, "btn_r" if (f // 8) % 2 == 0 else "mw_dk")     # сигнальный огонь мигает
    b.rect(107, 80, 119, 94, "out"); b.rect(108, 81, 118, 93, "star"); b.rect(109, 82, 117, 92, "mw_hi")
    b.rect(111, 85, 112, 89, "out"); b.rect(115, 85, 116, 89, "out")
    for i, (x, y) in enumerate(((110, 98), (112, 102), (114, 106), (116, 110), (118, 113))):
        b.px(x, y, "volt2" if (i - f // 2) % 5 == 0 else "volt")  # ток бежит по ноге вниз

# ═══ 5. Микроволновка ══════════════════════════════════════════════════
MX0, MY0, MX1, MY1 = 18, 72, 104, 106
SEG = {"a": (0, 0, 2, 0), "g": (0, 3, 2, 3), "d": (0, 6, 2, 6), "f": (0, 0, 0, 3), "e": (0, 3, 0, 6),
       "b": (2, 0, 2, 3), "c": (2, 3, 2, 6)}
DIGITS = {"0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc"}
CORD = [(104, 99), (108, 102), (112, 100), (113, 94), (113, 90)]


def microwave(b, f):
    b.rect(MX0 - 1, MY0 - 1, MX1 + 1, MY1 + 1, "out")
    b.rect(MX0, MY0, MX1, MY1, "mw")
    b.rect(MX0, MY0, MX1, MY0 + 1, "mw_hi"); b.rect(MX0, MY1 - 2, MX1, MY1, "mw_sh")
    b.rect(MX0, MY0, MX0 + 1, MY1, "mw_hi"); b.rect(MX1 - 1, MY0, MX1, MY1, "mw_sh")
    for lx in (24, 96):
        b.rect(lx, MY1 + 1, lx + 5, MY1 + 4, "mw_dk")
    window(b, f)
    panel(b, f)
    cord(b, f)


def window(b, f):
    """Окно светится и дышит; на вращающемся блюде — ящик и папки, галочки загораются по одной."""
    b.rect(22, 76, 76, 102, "mw_dk"); b.rect(24, 78, 74, 100, "glass")
    core = 0.62 + wave(f, FRAMES / 2, 0.1)
    for y in range(80, 99):
        for x in range(26, 73):
            dist = math.hypot((x - 49) / 24, (y - 89) / 10)
            if dist < 1 and (x + y + f // 4) % 2 == 0 or dist < core:
                b.px(x, y, "glow" if dist > core * 0.62 else "glow2")
    spin = round(wave(f, FRAMES, 1.5))
    b.rect(30 + spin, 88, 39 + spin, 97, "out"); b.rect(31 + spin, 89, 38 + spin, 96, "box")
    b.rect(31 + spin, 89, 38 + spin, 90, "star2"); b.rect(34 + spin, 92, 35 + spin, 93, "star2")
    for x0 in (43 + spin, 56 + spin):
        b.rect(x0, 88, x0 + 4, 90, "out"); b.rect(x0 + 1, 89, x0 + 3, 90, "folder")
        b.rect(x0, 90, x0 + 10, 97, "out"); b.rect(x0 + 1, 91, x0 + 9, 96, "folder")
        b.rect(x0 + 1, 91, x0 + 9, 91, "glow2")
    for k, cx in enumerate((34, 48, 61)):
        if f >= 4 + k * 8:
            check(b, cx, 83)


def check(b, cx, cy):
    pts = [(-3, 0), (-2, 1), (-1, 2), (0, 1), (1, 0), (2, -1), (3, -2), (4, -3)]
    for dx, dy in pts:
        for ox, oy in ((0, 1), (1, 0), (0, -1), (-1, 0), (1, 1)):
            b.px(cx + dx + ox, cy + dy + oy, "out")
    for dx, dy in pts:
        b.px(cx + dx, cy + dy, "check"); b.px(cx + dx, cy + dy + 1, "check")


def panel(b, f):
    """Табло считает секунды 00:01 → 00:04 — сколько галочек, столько секунд."""
    b.rect(80, 76, 100, 102, "mw_sh"); b.rect(82, 78, 98, 85, "lcd")
    for sx, ch in zip((83, 87, 92, 96), f"000{1 + min(3, f // 8)}"):
        for s in DIGITS[ch]:
            x0, y0, x1, y1 = SEG[s]
            b.line((sx + x0, 79 + y0), (sx + x1, 79 + y1), "amber")
    if f % 8 < 5:                                   # двоеточие мигает
        b.px(90, 80, "amber"); b.px(90, 83, "amber")
    for r in range(2):
        for c in range(3):
            b.rect(83 + c * 5, 88 + r * 4, 85 + c * 5, 89 + r * 4, "btn")
    b.rect(83, 97, 97, 100, "btn_r"); b.rect(83, 97, 97, 97, "cheek")


def cord(b, f):
    for w, c in ((5, "out"), (3, "glow"), (1, "volt")):
        for a, z in zip(CORD, CORD[1:]):
            b.line(a, z, c, w)
    seg = (f // 2) % (len(CORD) - 1)                # искорка бежит по проводу к микроволновке
    (ax, ay), (zx, zy) = CORD[-1 - seg], CORD[-2 - seg]
    b.px((ax + zx) // 2, (ay + zy) // 2, "volt2")
    b.rect(111, 86, 115, 90, "out"); b.rect(112, 87, 114, 89, "mw_dk")
    sparks = [(0, -3), (-2, -2), (2, -2), (-3, 0), (3, 0), (0, -5), (-4, -3), (4, -3)]
    for i, (dx, dy) in enumerate(sparks):
        if (i + f) % 3:
            b.px(113 + dx, 84 + dy, "volt2")
    if f % 6 < 3:                                   # молния над проводом вспыхивает
        pts = [(0, 0), (-2, 4), (0, 4), (-3, 9)]
        for (ax, ay), (zx, zy) in zip(pts, pts[1:]):
            b.line((101 + ax, 62 + ay), (101 + zx, 62 + zy), "volt")
        b.px(101, 62, "volt2")


STREAKS = [(26, 22, 44, (120, 220, 255)), (33, 4, 42, (255, 255, 255)), (41, 0, 36, (230, 120, 255)),
           (49, 8, 40, (150, 200, 255)), (57, 2, 30, (255, 255, 255)), (66, 0, 24, (230, 120, 255)),
           (80, 0, 16, (120, 220, 255)), (95, 0, 15, (255, 255, 255))]


def streaks(b, f):
    """След скорости за осьминогом: штрихи бегут назад."""
    for y, x0, x1, col in STREAKS:
        n = x1 - x0
        for i in range(n):
            dash = 1.0 if (i + f * 4 + y) % 12 < 8 else 0.4
            a = (0.15 + 0.8 * (i / n) ** 1.5) * dash
            b.blend(x0 + i, y, col, a)
            if i > n * 0.4:
                b.blend(x0 + i, y + 1, col, a * 0.45)

# ═══ 6. Щупальца, деревья, летящие листья ══════════════════════════════
HOLDERS = [
    [(48, 62), (38, 60), (30, 54), (24, 46)],
    [(52, 64), (44, 66), (36, 64), (30, 66)],
    [(78, 62), (88, 60), (96, 54), (102, 46)],
    [(74, 64), (82, 66), (90, 64), (96, 66)],
]
DANGLERS = [[(56, 66), (54, 70), (50, 72)], [(62, 67), (62, 71), (60, 73)],
            [(66, 67), (68, 71), (70, 73)], [(72, 66), (74, 70), (78, 72)]]
FLYING = [(36, 0), (54, 10), (62, 20), (44, 30), (70, 38)]   # y и сдвиг фазы снятых задач


def tentacle(b, pts, r0=3.2, r1=1.2, cups=True):
    path = []
    for (ax, ay), (zx, zy) in zip(pts, pts[1:]):
        n = int(math.hypot(zx - ax, zy - ay) * 2) + 1
        path += [(ax + (zx - ax) * i / n, ay + (zy - ay) * i / n) for i in range(n)]
    radii = [r0 + (r1 - r0) * j / max(1, len(path) - 1) for j in range(len(path))]
    for (x, y), r in zip(path, radii):
        b.disc(x, y, r + 1, "out")
    for (x, y), r in zip(path, radii):
        b.disc(x, y, r, "oct")
        b.disc(x - r * 0.3, y - r * 0.4, max(0.5, r * 0.45), "oct_hi")
    if cups:
        for x, y in path[4:-3:7]:
            b.px(x, y + 1, "cup")
    return path[-1]


def leaf(b, x, y, c, mark=True):
    """Лист 5×3 с обводкой; mark — белая галочка (задача снята)."""
    for dx, dy in [(-1, 0), (0, -1), (1, -1), (2, -1), (3, 0), (2, 1), (1, 1), (0, 1), (4, 0), (-2, 0)]:
        b.px(x + dx, y + dy, "out")
    for dx in range(4):
        b.px(x + dx, y, c)
    if mark:
        b.px(x + 1, y, "eye"); b.px(x + 2, y - 1, "eye")


def tree(b, cx, base_y):
    b.rect(cx - 1, base_y - 5, cx + 1, base_y, "trunk")
    for k, (w, c) in enumerate([(7, "leaf_sh"), (6, "leaf"), (4, "leaf"), (2, "leaf_hi")]):
        y = base_y - 5 - k * 3
        b.d.polygon([(cx - w, y), (cx + w, y), (cx, y - 5)], fill=P["out"])
        b.d.polygon([(cx - w + 1, y - 1), (cx + w - 1, y - 1), (cx, y - 4)], fill=P[c])
    for lx, ly in ((cx - 4, base_y - 9), (cx + 3, base_y - 13)):
        leaf(b, lx, ly, "leaf_hi")


def arms(b, f, bob):
    """Щупальца покачивают деревья; снятые задачи улетают назад вдоль следа."""
    ends = []
    for k, pts in enumerate(HOLDERS):
        lift = round(wave(f, FRAMES / 2, 1.2, k / 4))
        moved = [(x, y + bob) for x, y in pts[:1]] + pts[1:-1] + [(pts[-1][0], pts[-1][1] + lift)]
        ends.append(tentacle(b, moved))
    for k, pts in enumerate(DANGLERS):
        tip = (pts[-1][0] + round(wave(f, FRAMES / 2, 1, k / 4 + 0.5)), pts[-1][1])
        tentacle(b, [(pts[0][0], pts[0][1] + bob)] + pts[1:-1] + [tip], r0=3, r1=1.4, cups=False)
    for i in (0, 2):
        tree(b, int(ends[i][0]), int(ends[i][1]) - 1)
    for y, phase in FLYING:                         # 3 пикселя за кадр, круг 48 — петля без шва
        leaf(b, 42 - ((f * 3 + phase) % 48), y, "folder")

# ═══ 7. Голова ═════════════════════════════════════════════════════════
HX, HY = 63, 46


def head(b, f, bob):
    hy = HY + bob
    b.d.ellipse([HX - 19, hy - 19, HX + 19, hy + 19], fill=P["out"])
    b.d.ellipse([HX - 18, hy - 18, HX + 18, hy + 18], fill=P["oct"])
    b.d.ellipse([HX - 18, hy - 4, HX + 18, hy + 18], fill=P["oct_sh"])
    b.d.ellipse([HX - 17, hy - 18, HX + 17, hy + 10], fill=P["oct"])
    b.d.ellipse([HX - 13, hy - 15, HX - 3, hy - 7], fill=P["oct_hi"])
    b.rect(HX - 10, hy - 13, HX - 8, hy - 12, "cup")
    for ex in (HX - 7, HX + 7):
        if f in (26, 27):                           # моргнул
            b.line((ex - 3, hy + 3), (ex + 3, hy + 3), "pupil", 2)
            continue
        b.d.ellipse([ex - 4, hy - 2, ex + 4, hy + 7], fill=P["pupil"])
        b.d.ellipse([ex - 3, hy + 3, ex + 3, hy + 7], fill=P["iris"])
        b.rect(ex - 2, hy - 1, ex, hy + 1, "eye")
        b.px(ex + 2, hy + 4, "eye")
    for cx in (HX - 12, HX + 12):
        b.d.ellipse([cx - 3, hy + 6, cx + 3, hy + 9], fill=P["cheek"])
    for dx, dy in [(-3, 0), (-2, 1), (-1, 1), (0, 0), (1, 1), (2, 1), (3, 0)]:
        b.px(HX + dx, hy + 11 + dy, "pupil")

# ═══ 8. Кадр и запуск ══════════════════════════════════════════════════
def frame(f):
    b = Brush(SKY.copy())
    bob = round(wave(f, FRAMES / 2, 1, 0.25))
    stars(b, f)
    ground(b, f)
    tower(b, f)
    microwave(b, f)
    streaks(b, f)
    arms(b, f, bob)
    head(b, f, bob)
    return b.img


def main(out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = [frame(f) for f in range(FRAMES)]
    sheet = Image.new("RGB", (W * FRAMES, H))       # одна палитра на все кадры — цвета не мерцают
    for i, fr in enumerate(frames):
        sheet.paste(fr, (i * W, 0))
    palette = sheet.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    big = [fr.quantize(palette=palette, dither=Image.Dither.NONE).resize((W * SCALE, H * SCALE), Image.NEAREST)
           for fr in frames]
    big[0].save(out_dir / "skorost-sveta.gif", save_all=True, append_images=big[1:],
                duration=FRAME_MS, loop=0, optimize=True)
    print(f"skorost-sveta.gif: {FRAMES} frames, {W * SCALE}x{H * SCALE}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent)
