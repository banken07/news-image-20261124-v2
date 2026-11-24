#!/usr/bin/env python3
"""One 1024x1024 broadsheet summing up Tuesday 24 November 2026 world news.

Pure Python 3 stdlib. Reads its own glyph outlines (glyphs.json, generated
in-session from system Liberation Serif TTFs) and writes exactly one PNG to
MAKEFUN_OUTPUT_DIR (fallback /output). Deterministic: no clock, no random,
no network, no dict-order dependence.
"""
import json
import math
import os
import struct
import sys
import zlib

W = 1024
H = 1024
MARGIN = 16
COL_W = W - 2 * MARGIN  # 992

# ---- palette ----
CREAM = (247, 242, 231)
INK = (26, 26, 26)
GREY = (96, 96, 96)
LGREY = (110, 110, 110)
DARK = (28, 28, 36)
NAVY = (22, 50, 74)
LAND = (232, 220, 192)
GOLD = (232, 192, 112)
SALMON = (216, 144, 128)
LBLUE = (144, 176, 224)
LGREEN = (144, 208, 160)
LAVENDER = (200, 176, 224)
PINK = (240, 160, 168)
GREEN = (30, 122, 52)
ORANGE = (178, 106, 0)
RED = (168, 40, 32)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RULE = (40, 40, 40)
CARD_LINE = (90, 80, 70)

REGION_COLOR = {
    "EUROPE": (24, 74, 135),
    "MIDDLE EAST": (168, 40, 32),
    "ASIA-PACIFIC": (184, 80, 24),
    "AMERICAS": (104, 64, 136),
    "AFRICA": (40, 120, 56),
    "OCEANIA": (8, 120, 120),
    "WORLD": (64, 64, 72),
}
REGION_SHORT = {
    "EUROPE": "EUROPE",
    "MIDDLE EAST": "MIDDLE EAST",
    "ASIA-PACIFIC": "ASIA-PACIFIC",
    "AMERICAS": "AMERICAS",
    "AFRICA": "AFRICA",
    "OCEANIA": "OCEANIA",
    "WORLD": "WORLD",
}
BADGE_COLOR = {"CONFIRMED": GREEN, "REPORTED": ORANGE, "CLAIM": RED}
STAT_COLORS = [GOLD, SALMON, LBLUE, LGREEN, LAVENDER, PINK]

# ---- canvas ----
PIX = bytearray(W * H * 3)


def fill_rect(x0, y0, x1, y1, color):
    x0 = max(0, int(x0))
    y0 = max(0, int(y0))
    x1 = min(W, int(x1))
    y1 = min(H, int(y1))
    if x1 <= x0 or y1 <= y0:
        return
    r, g, b = color
    for y in range(y0, y1):
        base = (y * W + x0) * 3
        n = (x1 - x0)
        PIX[base:base + n * 3] = bytes((r, g, b)) * n


def set_px(x, y, color):
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        PIX[i] = color[0]
        PIX[i + 1] = color[1]
        PIX[i + 2] = color[2]


def fill_poly(points, color):
    """Even-odd scanline fill for a polygon given as [(x, y), ...]."""
    if len(points) < 3:
        return
    ys = [p[1] for p in points]
    y0 = max(0, int(math.floor(min(ys))))
    y1 = min(H - 1, int(math.ceil(max(ys))))
    n = len(points)
    for y in range(y0, y1 + 1):
        yc = y + 0.5
        xs = []
        for i in range(n):
            x1, y1p = points[i]
            x2, y2p = points[(i + 1) % n]
            if (y1p <= yc < y2p) or (y2p <= yc < y1p):
                if y2p != y1p:
                    t = (yc - y1p) / (y2p - y1p)
                    xs.append(x1 + t * (x2 - x1))
        if not xs:
            continue
        xs.sort()
        for j in range(0, len(xs) - 1, 2):
            xa = max(0, int(math.ceil(xs[j])))
            xb = min(W - 1, int(math.floor(xs[j + 1])))
            for x in range(xa, xb + 1):
                set_px(x, y, color)


def fill_polys(polys, color):
    """Even-odd scanline fill across several contours at once.

    All contours of one glyph are filled in a single pass, so inner
    contours (the counters of O, o, 0, a, e, D, 8, ...) stay hollow.
    Filling each contour separately would paint every counter solid
    (v2 bug: masthead read "N●vember 2●26", heads "F●REIGNER T●").
    """
    polys = [p for p in polys if len(p) >= 3]
    if not polys:
        return
    ys = [p[1] for poly in polys for p in poly]
    y0 = max(0, int(math.floor(min(ys))))
    y1 = min(H - 1, int(math.ceil(max(ys))))
    for y in range(y0, y1 + 1):
        yc = y + 0.5
        xs = []
        for points in polys:
            n = len(points)
            for i in range(n):
                x1, y1p = points[i]
                x2, y2p = points[(i + 1) % n]
                if (y1p <= yc < y2p) or (y2p <= yc < y1p):
                    if y2p != y1p:
                        t = (yc - y1p) / (y2p - y1p)
                        xs.append(x1 + t * (x2 - x1))
        if not xs:
            continue
        xs.sort()
        for j in range(0, len(xs) - 1, 2):
            xa = max(0, int(math.ceil(xs[j])))
            xb = min(W - 1, int(math.floor(xs[j + 1])))
            for x in range(xa, xb + 1):
                set_px(x, y, color)


def fill_circle(cx, cy, r, color):
    r = int(r)
    for y in range(int(cy) - r, int(cy) + r + 1):
        dy = y - cy
        dx = int(math.sqrt(max(0, r * r - dy * dy)))
        for x in range(int(cx) - dx, int(cx) + dx + 1):
            set_px(x, y, color)


def draw_line(x0, y0, x1, y1, color, width=1):
    dx = x1 - x0
    dy = y1 - y0
    steps = int(max(abs(dx), abs(dy))) + 1
    if steps <= 0:
        return
    w2 = width // 2
    for i in range(steps + 1):
        t = i / steps
        x = int(round(x0 + dx * t))
        y = int(round(y0 + dy * t))
        for wy in range(-w2, w2 + 1):
            for wx in range(-w2, w2 + 1):
                set_px(x + wx, y + wy, color)


def draw_rect_outline(x0, y0, x1, y1, color, width=1):
    fill_rect(x0, y0, x1, y0 + width, color)
    fill_rect(x0, y1 - width, x1, y1, color)
    fill_rect(x0, y0, x0 + width, y1, color)
    fill_rect(x1 - width, y0, x1, y1, color)


# ---- glyphs / text ----
_HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_HERE, "glyphs.json"), "r") as _fh:
    _GLYPHS = json.load(_fh)
UPM = _GLYPHS["upm"]
_FACES = _GLYPHS["faces"]


def text_width(s, size, face="regular"):
    scale = size / UPM
    w = 0.0
    glyphs = _FACES[face]
    for ch in s:
        g = glyphs.get(ch)
        if g is None:
            continue
        w += g["adv"] * scale
    return w


def draw_text(x, y_baseline, s, size, face="regular", color=INK):
    """Draw text with baseline at y_baseline. Returns width drawn."""
    scale = size / UPM
    glyphs = _FACES[face]
    cx = float(x)
    for ch in s:
        g = glyphs.get(ch)
        if g is None:
            continue
        adv = g["adv"] * scale
        # One even-odd pass over ALL contours of the glyph, so inner
        # contours (counters of O, o, 0, a, e, D, 8 ...) stay hollow.
        polys = []
        for contour in g["c"]:
            pts = []
            for (px, py) in contour:
                pts.append((cx + px * scale, y_baseline - py * scale))
            polys.append(pts)
        fill_polys(polys, color)
        cx += adv
    return cx - x


def draw_text_centered(cx, y_baseline, s, size, face="regular", color=INK):
    w = text_width(s, size, face)
    draw_text(cx - w / 2.0, y_baseline, s, size, face, color)
    return w


def draw_text_right(x_right, y_baseline, s, size, face="regular", color=INK):
    w = text_width(s, size, face)
    draw_text(x_right - w, y_baseline, s, size, face, color)
    return w


def wrap_text(s, size, face, max_w):
    """Greedy word wrap. Returns list of lines."""
    words = s.split(" ")
    lines = []
    cur = ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if text_width(trial, size, face) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_wrapped(x, y_baseline, s, size, face, color, max_w, leading, max_lines=None):
    lines = wrap_text(s, size, face, max_w)
    if max_lines is not None:
        lines = lines[:max_lines]
    y = y_baseline
    for line in lines:
        draw_text(x, y, line, size, face, color)
        y += leading
    return lines


# ---- PNG output ----
def write_png(path):
    raw = bytearray()
    stride = W * 3
    for y in range(H):
        raw.append(0)
        raw += PIX[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 6)

    def chunk(ctype, data):
        out = struct.pack(">I", len(data)) + ctype + data
        out += struct.pack(">I", zlib.crc32(ctype + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(png)
    return len(png)


# ---- content (single source of truth: STORY-LIST.md, Tuesday 24 Nov 2026) ----
MASTHEAD = "Tuesday 24 November 2026"
KICKER = "THE WORLD IN ONE DAY"
PRESS_TIME = "PRESS TIME 23:00 UTC"
SUBHEAD = "26 STORIES \u00b7 7 REGIONS \u00b7 ALL FROM THIS ONE DAY"
REGIONS = [("EUROPE", 3), ("MIDDLE EAST", 5), ("ASIA-PACIFIC", 10),
           ("AMERICAS", 4), ("AFRICA", 2), ("OCEANIA", 1), ("WORLD", 1)]

TIMELINE = [
    ("MON 21:00", "NVIDIA +31.5%"),
    ("MON NIGHT", "POLAND DRONE"),
    ("01:32", "QUAKE NEPAL M5.3"),
    ("TUE AM", "SHENZHOU CREW"),
    ("06:00", "ASIA +3.9% / +6.3%"),
    ("23:00", "WIRES READ"),
]

# leads: (num, region, head, deck, subdeck, sources, badge, art)
LEADS = [
    (1, "ASIA-PACIFIC", "ASIA ROARS BACK ON HUANG'S RETURN",
     "Nikkei +3.9%, Kospi +6.3%, Taiex +9.0% \u2014 a record points gain.",
     "Nvidia board reinstated Huang Mon; shares +31.5% Mon (+$952bn, best day since 2003).",
     "Yonhap / Nikkei Indexes / AP", "CONFIRMED", "rally"),
    (2, "EUROPE", "RUSSIAN DRONE OVER POLAND",
     "8 minutes in Polish air; NATO sends AWACS after Fri missiles.",
     "Entered Mon night, not shot down \u2014 civilian risk. Fri: 3 Kh-101 missiles fell in Poland.",
     "Guardian / Reuters", "REPORTED", "drone"),
    (3, "ASIA-PACIFIC", "FIRST FOREIGNER TO FLY TO TIANGONG",
     "Pakistan's Zeeshan Ali joins Shenzhou-24; launch Wed 00:18 UTC.",
     "Crew named Tue at Jiuquan; Ali, 40, first Pakistani in orbit; returns on Shenzhou-23.",
     "Xinhua / AP / Nature", "CONFIRMED", "rocket"),
]

# small: (num, region, head, deck, sources, badge, art)
SMALL = [
    (4, "MIDDLE EAST", "GAZA MENINGITIS ALERT",
     "272 cases in Oct, 8x usual; strikes kill 7.",
     "Al Jazeera / Wafa", "CONFIRMED", "cross"),
    (5, "ASIA-PACIFIC", "CIKANDE FIRE: 26 DEAD",
     "Toll rises Tue; DNA IDs to take weeks.",
     "AP / Xinhua", "CONFIRMED", "flame"),
    (6, "ASIA-PACIFIC", "6,803 ROHINGYA TO GO BACK",
     "Anwar announces Dec return; UK sanctions 5 generals.",
     "AP / Al Jazeera", "CONFIRMED", "boat"),
    (7, "EUROPE", "ZELENSKY SEEKS FOUR-WAY TALKS",
     "Zaporizhzhia strike kills 2; 355 drones at Moscow.",
     "France 24 / Al Jazeera", "CONFIRMED", "flags"),
    (8, "MIDDLE EAST", "HORMUZ: BRENT UNMOVED",
     "IRGC claims 3 tankers hit mines; oil holds ~$86.71.",
     "Reuters / CNBC", "CLAIM", "tanker"),
    (9, "AMERICAS", "DEMOCRATS FLIP 47 SEATS",
     "Final counts: could reach 49; Senate 56\u201344.",
     "NPR", "CONFIRMED", "ballot"),
    (10, "ASIA-PACIFIC", "NEPAL PM IN INDIA; \u20ac1.4BN PLEDGED",
     "Shah's first visit; rail, hydropower, fuel deals.",
     "Euronews / DW", "CONFIRMED", "mountain"),
    (11, "MIDDLE EAST", "QATAR SEEKS TO REVIVE TALKS",
     "PM meets Rubio; Tehran sets 7 conditions.",
     "Al Jazeera / Middle East Eye", "CONFIRMED", "talks"),
    (12, "EUROPE", "ESTONIA TO SHUT RUSSIA BORDER",
     "All crossings close Dec 1 after arson attempt.",
     "Meduza", "CONFIRMED", "fence"),
    (13, "MIDDLE EAST", "YEMEN STRIKES KILL ABOUT 25",
     "Buses and trucks hit in Lahj; Saudis blamed.",
     "Middle East Eye", "REPORTED", "blast"),
]

# also-list: (num, region, title, desc, source) — 3 columns of 5/5/3
ALSO = [
    (14, "ASIA-PACIFIC", "Korea shelter alert",
     "Russian jets near Ulleung; Seoul scrambles jets.", "Guardian / Yonhap"),
    (15, "MIDDLE EAST", "Iraq takes Kurdish oilfields",
     "Baghdad orders federal control of exports, crossings, fields.", "The National"),
    (16, "AFRICA", "Congo plane missing",
     "Rebels claim shootdown near Minembwe; pilot, officer aboard.", "BBC"),
    (17, "AFRICA", "Sudan drones hit UN building",
     "Khartoum structures damaged; WFP: 19.5M at famine risk.", "RFI"),
    (18, "ASIA-PACIFIC", "Nepal quake at dawn",
     "M5.3 shakes Taplejung; felt in India, Bhutan, Bangladesh, China; no casualties.",
     "NCS / USGS / Xinhua"),
    (19, "AMERICAS", "Colombia car bomb",
     "21 injured in Villavicencio; first urban drone attack in Cucuta.", "Al Jazeera"),
    (20, "AMERICAS", "Mexico tries 'Chapo Isidro'",
     "No extradition; US drone helped capture him.", "Al Jazeera"),
    (21, "ASIA-PACIFIC", "Indonesia charges ex-police chief",
     "Listyo Sigit named treason suspect over wiretaps.", "Japan Times"),
    (22, "ASIA-PACIFIC", "Hasina plans return Dec 16",
     "Dhaka says it will arrest her; India asked to extradite.", "BBC"),
    (23, "ASIA-PACIFIC", "China extends mineral-curb pause",
     "Gallium, germanium, antimony curbs paused 2 more months.", "SCMP"),
    (24, "AMERICAS", "Brazil real past 6/USD",
     "Growth forecast cut to 1.8%; inflation 4.5%.", "MercoPress"),
    (25, "WORLD", "Guterres urges AI safety pact",
     "Framework talks within a year; arms meeting ends with no deal.", "UN News"),
    (26, "OCEANIA", "Australia: sue tech firms",
     "Online safety deal; fines up to 5% of global revenue.", "Guardian"),
]
ALSO_COLS = [ALSO[0:5], ALSO[5:10], ALSO[10:13]]

# stat strip: (value, label, story number, color)
STATS = [
    ("+9.0%", "TAIEX RECORD JUMP", 1, GOLD),
    ("+31.5%", "NVIDIA ON MONDAY", 1, SALMON),
    ("26", "CIKANDE FIRE TOLL", 5, LBLUE),
    ("6,803", "ROHINGYA TO RETURN", 6, LGREEN),
    ("272", "MENINGITIS CASES", 4, LAVENDER),
    ("355", "DRONES AT MOSCOW", 7, PINK),
]

# DATE CHECK left-out items: (text, date) — 3 columns of 6/6/5
DATECHECK = [
    ("COP31 ends with no deal", "Sun 23 Nov"),
    ("Merkury sunk off Benghazi", "Sun 22 Nov"),
    ("EU 22nd sanctions package", "Mon 23 Nov"),
    ("Sputnik-S satellite; Rutte vows space defence", "Mon 23 Nov"),
    ("CrowdStrike buys Zscaler, $44bn", "Mon 23 Nov"),
    ("Ahmadi flogged 74 lashes", "Mon 23 Nov"),
    ("Megaspeed blacklisted", "Mon 23 Nov"),
    ("Women's World Cup 2031 hosts named", "Mon 23 Nov"),
    ("Oregon/Virginia sue Musk over Grok", "Mon 23 Nov"),
    ("Belgium strike halts flights", "Mon 23 Nov"),
    ("Zanzibar hotel fire", "Sat 22 Nov"),
    ("Tamagotchi turns 30", "Mon 23 Nov"),
    ("ICE arrests father and daughter, Seattle", "Sat 22 Nov"),
    ("Commanders beat Bengals 22\u201320", "Mon 23 Nov"),
    ("Brentford beat Everton 4\u20130", "Mon 23 Nov"),
    ("US loses measles-free status", "Tue 17 Nov"),
    ("Iran courts order US to pay $290bn", "Mon 23 Nov"),
]
DATECHECK_COLS = [DATECHECK[0:6], DATECHECK[6:12], DATECHECK[12:17]]
DATECHECK_ALSO = ("Also covered in the image: Nvidia +31.5% \u2014 Mon 23 Nov \u00b7 "
                  "Fri missiles \u2014 20 Nov \u00b7 Hormuz claim \u2014 Mon 23 Nov")

FOOTER_SOURCES = ("Sources: Yonhap \u00b7 Nikkei Indexes \u00b7 AP \u00b7 Guardian \u00b7 Reuters \u00b7 "
                  "Xinhua \u00b7 Al Jazeera \u00b7 Wafa \u00b7 NPR \u00b7 Euronews \u00b7 DW \u00b7 "
                  "France 24 \u00b7 CNBC \u00b7 Meduza \u00b7 MEE \u00b7 BBC \u00b7 RFI \u00b7 "
                  "SCMP \u00b7 MercoPress \u00b7 UN News \u00b7 NCS \u00b7 USGS")


# ---- small shared widgets ----
def draw_badge(x_right, y_top, badge):
    """Badge chip, right-aligned at x_right, top at y_top. Returns width."""
    color = BADGE_COLOR[badge]
    w = int(text_width(badge, 9, "bold")) + 10
    h = 14
    fill_rect(x_right - w, y_top, x_right, y_top + h, color)
    draw_text(x_right - w + 5, y_top + 11, badge, 9, "bold", WHITE)
    return w


def draw_num_disc(cx, cy, num, r=9, bg=BLACK, fg=WHITE, size=11):
    fill_circle(cx, cy, r, bg)
    draw_circle_ring(cx, cy, r, WHITE)
    s = str(num)
    w = text_width(s, size, "bold")
    draw_text(cx - w / 2.0, cy + size * 0.35, s, size, "bold", fg)


def draw_circle_ring(cx, cy, r, color):
    for a in range(0, 360, 2):
        t = math.radians(a)
        set_px(int(cx + r * math.cos(t)), int(cy + r * math.sin(t)), color)


def draw_flag(x, y, w, h, colors):
    """Tiny vertical-stripe flag (2-3 stripes)."""
    n = len(colors)
    for i, c in enumerate(colors):
        fill_rect(x + i * w // n, y, x + (i + 1) * w // n, y + h, c)
    draw_rect_outline(x, y, x + w, y + h, INK, 1)


# ---- flat-vector illustrations ----
def art_rally(x, y, w, h):
    fill_rect(x, y, x + w, y + h, (243, 230, 207))
    # rising bars, left to right
    n = 5
    bw = w // (n * 2)
    for i in range(n):
        bh = int(h * (0.30 + 0.14 * i))
        bx = x + 8 + i * (2 * bw) + 4
        fill_rect(bx, y + h - 10 - bh, bx + bw, y + h - 10, (198, 90, 30))
    # rising arrow (stops clear of the badge, top right)
    pts = [(x + 10, y + h - 18), (x + w * 0.35, y + h * 0.55),
           (x + w * 0.55, y + h * 0.68), (x + w * 0.78, y + 26)]
    for a, b in zip(pts, pts[1:]):
        draw_line(a[0], a[1], b[0], b[1], INK, 3)
    ex, ey = pts[-1]
    fill_poly([(ex, ey), (ex - 12, ey - 2), (ex - 2, ey + 12)], INK)
    fill_circle(x + w - 16, y + 18, 4, RED)


def art_drone(x, y, w, h):
    fill_rect(x, y, x + w, y + h, (223, 232, 240))
    cx, cy = x + w // 2, y + h // 2 + 4
    # arms + rotors
    for (dx, dy) in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
        rx, ry = cx + dx * w * 0.28, cy + dy * h * 0.26
        draw_line(cx, cy, rx, ry, INK, 3)
        fill_circle(rx, ry, 9, (24, 74, 135))
        draw_circle_ring(rx, ry, 9, WHITE)
        fill_circle(rx, ry, 3, WHITE)
    # body
    fill_poly([(cx - 26, cy - 8), (cx + 26, cy - 8), (cx + 18, cy + 8),
               (cx - 18, cy + 8)], INK)
    fill_circle(cx, cy, 7, RED)
    # ground hint
    draw_line(x + 8, y + h - 8, x + w - 8, y + h - 8, (120, 130, 140), 2)


def art_rocket(x, y, w, h):
    fill_rect(x, y, x + w, y + h, (246, 227, 211))
    cx = x + w // 2
    # stars
    for (sx, sy) in [(x + 16, y + 14), (x + w - 18, y + 22), (x + 26, y + h - 20),
                      (x + w - 26, y + h - 26)]:
        fill_circle(sx, sy, 2, (198, 90, 30))
    # flame
    fill_poly([(cx - 12, y + h - 30), (cx + 12, y + h - 30), (cx, y + h - 6)],
              (240, 180, 40))
    fill_poly([(cx - 6, y + h - 30), (cx + 6, y + h - 30), (cx, y + h - 12)], RED)
    # fins
    fill_poly([(cx - 14, y + h - 52), (cx - 26, y + h - 28), (cx - 12, y + h - 30)],
              (168, 40, 32))
    fill_poly([(cx + 14, y + h - 52), (cx + 26, y + h - 28), (cx + 12, y + h - 30)],
              (168, 40, 32))
    # body
    fill_poly([(cx - 14, y + 14), (cx + 14, y + 14), (cx + 14, y + h - 30),
               (cx - 14, y + h - 30)], (198, 90, 30))
    fill_poly([(cx - 14, y + 14), (cx + 14, y + 14), (cx, y + 2)], RED)
    fill_circle(cx, y + 34, 7, WHITE)
    draw_circle_ring(cx, y + 34, 7, INK)


def art_cross(x, y, w, h):
    fill_rect(x, y, x + w, y + h, (246, 224, 220))
    cx, cy = x + w // 2, y + h // 2
    fill_rect(cx - 7, cy - 16, cx + 7, cy + 16, RED)
    fill_rect(cx - 16, cy - 7, cx + 16, cy + 7, RED)
    for (sx, sy) in [(x + 14, y + 10), (x + w - 14, y + 12), (x + w - 16, y + h - 10)]:
        fill_circle(sx, sy, 3, RED)


def art_flame(x, y, w, h):
    fill_rect(x, y, x + w, y + h, (251, 238, 214))
    cx = x + w // 2
    fill_poly([(cx, y + 6), (cx + 16, y + h * 0.45), (cx + 8, y + h - 8),
               (cx - 8, y + h - 8), (cx - 16, y + h * 0.45)], (230, 120, 30))
    fill_poly([(cx, y + h * 0.35), (cx + 9, y + h * 0.62), (cx + 5, y + h - 8),
               (cx - 5, y + h - 8), (cx - 9, y + h * 0.62)], (245, 200, 60))
    fill_poly([(cx, y + h * 0.55), (cx + 5, y + h * 0.75), (cx, y + h - 8),
               (cx - 5, y + h * 0.75)], RED)
    draw_line(x + 8, y + h - 4, x + w - 8, y + h - 4, INK, 2)


def art_boat(x, y, w, h):
    fill_rect(x, y, x + w, y + h, (220, 233, 242))
    cx, cy = x + w // 2, y + h // 2
    # waves
    for wy in (y + h - 12, y + h - 6):
        for wx in range(x + 6, x + w - 6, 18):
            draw_line(wx, wy, wx + 10, wy, (24, 74, 135), 2)
    # mast + sail
    draw_line(cx + 6, cy - 16, cx + 6, cy + 8, INK, 2)
    fill_poly([(cx + 8, cy - 16), (cx + 8, cy + 6), (cx + 26, cy + 6)], WHITE)
    draw_rect_outline(cx + 8, cy - 16, cx + 26, cy + 6, INK, 1)
    # hull
    fill_poly([(cx - 34, cy + 8), (cx + 34, cy + 8), (cx + 26, cy + 18),
               (cx - 26, cy + 18)], (120, 70, 40))
    fill_circle(cx - 12, cy + 2, 3, INK)
    fill_circle(cx + 2, cy + 2, 3, INK)


def art_flags(x, y, w, h):
    fill_rect(x, y, x + w, y + h, (233, 236, 242))
    # four small flags in a row, kept clear of the badge (top right)
    cols = [(24, 74, 135), (220, 180, 40), (168, 40, 32), (40, 120, 56)]
    span = w - 28 - 70
    for i, c in enumerate(cols):
        fx = x + 10 + i * span // 4
        draw_line(fx, y + 8, fx, y + h - 12, INK, 2)
        fill_rect(fx, y + 8, fx + 16, y + 20, c)
        draw_rect_outline(fx, y + 8, fx + 16, y + 20, INK, 1)
    draw_line(x + 10, y + h - 10, x + w - 10, y + h - 10, INK, 2)


def art_tanker(x, y, w, h):
    fill_rect(x, y, x + w, y + h, (229, 224, 213))
    # hull + containers
    fill_poly([(x + 12, y + h - 22), (x + w - 12, y + h - 22),
               (x + w - 22, y + h - 8), (x + 22, y + h - 8)], INK)
    for i, c in enumerate([(168, 40, 32), (24, 74, 135), (198, 90, 30)]):
        bx = x + 22 + i * 18
        fill_rect(bx, y + h - 34, bx + 15, y + h - 22, c)
    # funnel + smoke
    fill_rect(x + w - 34, y + h - 40, x + w - 26, y + h - 22, (120, 70, 40))
    fill_circle(x + w - 30, y + h - 46, 4, GREY)
    # oil drop
    fill_poly([(x + 16, y + 12), (x + 22, y + 20), (x + 10, y + 20)], INK)
    fill_circle(x + 16, y + 22, 5, INK)


def art_ballot(x, y, w, h):
    fill_rect(x, y, x + w, y + h, (230, 235, 242))
    cx, cy = x + w // 2, y + h // 2
    # ballot box
    fill_rect(cx - 26, cy - 2, cx + 26, cy + 16, (24, 74, 135))
    fill_rect(cx - 20, cy - 16, cx + 20, cy - 2, WHITE)
    draw_rect_outline(cx - 20, cy - 16, cx + 20, cy - 2, INK, 1)
    draw_rect_outline(cx - 26, cy - 2, cx + 26, cy + 16, INK, 1)
    # big check
    draw_line(cx - 22, cy - 2, cx - 8, cy + 12, GREEN, 5)
    draw_line(cx - 8, cy + 12, cx + 24, cy - 18, GREEN, 5)


def art_mountain(x, y, w, h):
    fill_rect(x, y, x + w, y + h, (223, 233, 240))
    # sun
    fill_circle(x + w - 18, y + 10, 6, (240, 180, 40))
    # mountains
    fill_poly([(x + 4, y + h - 6), (x + w * 0.35, y + 8), (x + w * 0.62, y + h - 6)],
              (90, 110, 140))
    fill_poly([(x + w * 0.35, y + 8), (x + w * 0.28, y + 18), (x + w * 0.42, y + 18)],
              WHITE)
    fill_poly([(x + w * 0.45, y + h - 6), (x + w * 0.75, y + 2), (x + w - 4, y + h - 6)],
              (60, 80, 110))
    fill_poly([(x + w * 0.75, y + 2), (x + w * 0.69, y + 12), (x + w * 0.81, y + 12)],
              WHITE)
    draw_line(x + 4, y + h - 4, x + w - 4, y + h - 4, INK, 2)


def art_talks(x, y, w, h):
    fill_rect(x, y, x + w, y + h, (242, 230, 230))
    cx, cy = x + w // 2, y + h // 2
    # two crossed flags
    draw_line(cx - 20, cy + 12, cx + 8, cy - 14, INK, 2)
    draw_line(cx + 20, cy + 12, cx - 8, cy - 14, INK, 2)
    fill_rect(cx + 8, cy - 14, cx + 26, cy - 2, (128, 20, 40))
    fill_rect(cx - 26, cy - 14, cx - 8, cy - 2, (24, 74, 135))
    # table
    draw_line(x + 12, cy + 14, x + w - 12, cy + 14, INK, 3)
    draw_line(cx - 14, cy + 14, cx - 14, cy + 20, INK, 2)
    draw_line(cx + 14, cy + 14, cx + 14, cy + 20, INK, 2)


def art_fence(x, y, w, h):
    fill_rect(x, y, x + w, y + h, (232, 228, 218))
    # striped barrier
    for i in range(6):
        c = RED if i % 2 == 0 else WHITE
        fill_rect(x + 10 + i * 12, y + 8, x + 10 + (i + 1) * 12, y + 18, c)
    draw_rect_outline(x + 10, y + 8, x + 82, y + 18, INK, 1)
    # fence bars
    for i in range(7):
        bx = x + 14 + i * 12
        fill_rect(bx, y + 22, bx + 4, y + h - 6, INK)
    draw_line(x + 10, y + 26, x + w - 10, y + 26, INK, 3)
    draw_line(x + 10, y + h - 10, x + w - 10, y + h - 10, INK, 3)


def art_blast(x, y, w, h):
    fill_rect(x, y, x + w, y + h, (251, 232, 208))
    cx, cy = x + w // 2, y + h // 2
    # starburst
    pts = []
    for i in range(16):
        ang = math.pi * i / 8.0
        r = 20 if i % 2 == 0 else 9
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    fill_poly(pts, (230, 120, 30))
    fill_circle(cx, cy, 7, RED)
    fill_circle(x + 14, y + h - 12, 5, GREY)
    fill_circle(x + w - 14, y + 10, 5, GREY)


ART = {
    "rally": art_rally, "drone": art_drone, "rocket": art_rocket,
    "cross": art_cross, "flame": art_flame, "boat": art_boat,
    "flags": art_flags, "tanker": art_tanker, "ballot": art_ballot,
    "mountain": art_mountain, "talks": art_talks, "fence": art_fence,
    "blast": art_blast,
}

# ---- world map ----
# Coarse continent outlines in (lon, lat). Stylised, recognisable.
CONTINENTS = [
    # North America
    [(-168, 66), (-156, 71), (-140, 70), (-128, 71), (-115, 73), (-100, 73),
     (-90, 74), (-82, 72), (-76, 70), (-68, 62), (-60, 55), (-55, 50),
     (-60, 45), (-68, 44), (-74, 40), (-76, 35), (-80, 32), (-81, 26),
     (-84, 30), (-90, 21), (-94, 17), (-97, 16), (-92, 15), (-87, 13),
     (-83, 10), (-79, 9), (-83, 9), (-90, 14), (-97, 16), (-105, 20),
     (-108, 23), (-112, 28), (-117, 33), (-122, 37), (-124, 42), (-124, 48),
     (-128, 52), (-135, 58), (-145, 60), (-155, 58), (-162, 55), (-168, 60)],
    # Greenland
    [(-58, 64), (-45, 60), (-32, 68), (-22, 70), (-30, 76), (-55, 76), (-60, 70)],
    # South America
    [(-80, 9), (-75, 11), (-62, 10), (-52, 5), (-50, 0), (-44, -3),
     (-35, -8), (-40, -20), (-48, -28), (-58, -35), (-65, -41), (-70, -54),
     (-73, -50), (-73, -37), (-70, -20), (-77, -12), (-81, -6), (-80, 2)],
    # Africa
    [(-17, 15), (-10, 30), (0, 36), (10, 37), (20, 32), (30, 31), (35, 28),
     (43, 12), (51, 11), (48, 0), (40, -10), (35, -20), (32, -29), (26, -34),
     (18, -35), (12, -18), (9, -1), (9, 4), (-8, 5), (-13, 8)],
    # Madagascar
    [(44, -16), (47, -15), (50, -16), (49, -22), (45, -25), (43, -20)],
    # Eurasia
    [(-10, 36), (-9, 43), (-2, 48), (-4, 50), (2, 51), (8, 57), (10, 59),
     (18, 56), (21, 55), (24, 58), (28, 60), (30, 70), (40, 68), (55, 68),
     (70, 72), (90, 75), (110, 76), (130, 72), (150, 70), (170, 67),
     (178, 65), (170, 60), (162, 56), (158, 52), (142, 50), (140, 40),
     (130, 35), (127, 35), (120, 30), (110, 20), (105, 10), (100, 8),
     (98, 15), (95, 25), (90, 22), (85, 20), (80, 15), (77, 8), (75, 12),
     (72, 20), (66, 25), (60, 25), (57, 26), (52, 28), (48, 30), (44, 29),
     (40, 32), (36, 36), (30, 36), (26, 38), (22, 37), (18, 40), (12, 44),
     (8, 44), (3, 43), (-2, 37), (-9, 37)],
    # UK
    [(-5, 50), (-3, 53), (-5, 56), (-2, 58), (0, 53)],
    # Japan
    [(130, 31), (132, 33), (135, 34), (138, 35), (140, 38), (141, 41),
     (140, 44), (138, 42), (135, 37), (132, 34)],
    # Sumatra
    [(95, 5), (100, 0), (104, -3), (106, -6), (102, -4), (97, 2)],
    # Java
    [(105, -6), (110, -7), (114, -8), (112, -8), (107, -7)],
    # Borneo
    [(109, 1), (113, 4), (117, 0), (116, -3), (110, -3)],
    # New Guinea
    [(131, -1), (136, -2), (141, -4), (141, -8), (136, -8), (131, -4)],
    # Australia
    [(113, -22), (114, -30), (115, -35), (120, -34), (129, -32), (137, -35),
     (140, -38), (146, -39), (150, -37), (153, -32), (153, -27), (146, -19),
     (142, -11), (136, -12), (132, -12), (126, -14), (122, -17), (114, -21)],
    # New Zealand
    [(167, -45), (170, -42), (174, -38), (176, -37), (174, -41), (170, -44)],
]

# pins: (story num, label, lon, lat, pin dx, pin dy, label side, label dx, label dy)
# label side: 'r' text starts at pin+dx, 'l' text ends at pin+dx, 'u' above, 'd' below
PINS = [
    (1, "SEOUL", 127, 37.5, 0, 0, "r", 7, -20),
    (2, "POLAND", 21, 52.2, -10, 0, "l", -25, -16),
    (3, "JIUQUAN", 98.5, 39.7, 4, 0, "u", 0, -26),
    (4, "GAZA", 34.5, 31.5, 0, 0, "l", -30, -2),
    (5, "CIKANDE", 106.2, -6.3, 2, 2, "d", 0, 14),
    (6, "KUALA LUMPUR", 101.7, 3.1, -2, -2, "u", 25, -14),
    (7, "KYIV", 30.5, 50.4, 4, 4, "d", 2, 2),
    (8, "HORMUZ", 56.5, 26.5, 4, -4, "u", 16, -18),
    (9, "WASHINGTON", -77, 38.9, 0, 0, "l", -7, -4),
    (10, "NEW DELHI", 77.2, 28.6, 0, 0, "r", 36, 26),
    (11, "DOHA", 51.5, 25.3, -6, -4, "d", -35, 20),
    (12, "NARVA", 28.2, 59.4, 0, -5, "u", 5, -14),
    (13, "LAHJ", 44.9, 13.0, 2, 2, "d", 10, 8),
]


def project(mx, my, mw, mh, lon, lat):
    return (mx + (lon + 180.0) / 360.0 * mw,
            my + (90.0 - lat) / 180.0 * mh)


def draw_map(mx, my, mw, mh):
    fill_rect(mx, my, mx + mw, my + mh, NAVY)
    for poly in CONTINENTS:
        pts = [project(mx, my, mw, mh, lon, lat) for (lon, lat) in poly]
        fill_poly(pts, LAND)
    # pins + labels
    for (num, label, lon, lat, pdx, pdy, side, ldx, ldy) in PINS:
        px, py = project(mx, my, mw, mh, lon, lat)
        px += pdx
        py += pdy
        # label position
        lw = text_width(label, 9, "bold")
        if side == "r":
            lx, ly = px + ldx, py + ldy
            ax, ay = px + 4, py
        elif side == "l":
            lx, ly = px + ldx - lw, py + ldy
            ax, ay = px - 4, py
        elif side == "u":
            lx, ly = px - lw / 2.0 + ldx, py + ldy
            ax, ay = px, py - 4
        else:  # 'd'
            lx, ly = px - lw / 2.0 + ldx, py + ldy
            ax, ay = px, py + 4
        # label box
        bx0, by0 = int(lx) - 2, int(ly) - 9
        bx1, by1 = int(lx + lw) + 2, int(ly) + 3
        draw_line(px, py, (bx0 + bx1) // 2, (by0 + by1) // 2, WHITE, 1)
        fill_rect(bx0, by0, bx1, by1, WHITE)
        draw_rect_outline(bx0, by0, bx1, by1, INK, 1)
        draw_text(lx, ly, label, 9, "bold", INK)
        # pin disc with number
        fill_circle(px, py, 4, RED)
        draw_circle_ring(px, py, 4, WHITE)
        s = str(num)
        sw = text_width(s, 6, "bold")
        draw_text(px - sw / 2.0, py + 2, s, 6, "bold", WHITE)


# ---- layout ----
def draw_header():
    fill_rect(0, 0, W, 3, INK)
    draw_text(MARGIN, 18, KICKER, 11, "bold", INK)
    draw_text_right(W - MARGIN, 18, PRESS_TIME, 11, "bold", INK)
    # masthead: fit to column width, start at 72px
    size = 72
    while text_width(MASTHEAD, size, "bold") > COL_W and size > 40:
        size -= 1
    draw_text(MARGIN, 78, MASTHEAD, size, "bold", INK)
    fill_rect(MARGIN, 96, W - MARGIN, 98, INK)
    # subhead + region chips on one line, centred as a group
    chip_h = 16
    chip_y = 102
    parts = []
    total = int(text_width(SUBHEAD, 13, "bold")) + 12
    for (name, n) in REGIONS:
        label = "%s %d" % (name, n)
        wch = int(text_width(label, 10, "bold")) + 12
        parts.append((label, wch, REGION_COLOR[name]))
        total += wch
    total += 6 * (len(parts) - 1)
    cx = (W - total) // 2
    draw_text(cx, chip_y + 12, SUBHEAD, 13, "bold", INK)
    cx += int(text_width(SUBHEAD, 13, "bold")) + 12
    for (label, wch, color) in parts:
        fill_rect(cx, chip_y, cx + wch, chip_y + chip_h, color)
        draw_text(cx + 6, chip_y + 12, label, 10, "bold", WHITE)
        cx += wch + 6
    # timeline black bar
    bar_y = 122
    fill_rect(MARGIN, bar_y, W - MARGIN, bar_y + 24, BLACK)
    slot_w = COL_W / len(TIMELINE)
    for i, (t, label) in enumerate(TIMELINE):
        full = t + " " + label
        size = 11
        if text_width(full, size, "bold") > slot_w - 8:
            size = 10
        tw = text_width(full, size, "bold")
        sx = MARGIN + i * slot_w + (slot_w - tw) / 2.0
        draw_text(sx, bar_y + 17, t, size, "bold", GOLD)
        draw_text(sx + text_width(t, size, "bold"), bar_y + 17,
                  " " + label, size, "bold", WHITE)


def draw_lead_card(x, y, num, region, head, deck, subdeck, sources, badge, art):
    w, h = 246, 240
    fill_rect(x, y, x + w, y + h, WHITE)
    draw_rect_outline(x, y, x + w, y + h, CARD_LINE, 1)
    ART[art](x + 1, y + 1, w - 2, 104)
    draw_num_disc(x + 15, y + 15, num, r=9, size=11)
    draw_badge(x + w - 5, y + 5, badge)
    draw_text(x + 8, y + 116, REGION_SHORT[region], 10, "bold",
              REGION_COLOR[region])
    draw_wrapped(x + 8, y + 140, head, 21, "bold", INK, w - 16, 25, 2)
    draw_wrapped(x + 8, y + 183, deck, 12, "regular", INK, w - 16, 14, 2)
    draw_wrapped(x + 8, y + 212, subdeck, 10, "regular", GREY, w - 16, 12, 2)
    draw_text(x + 8, y + 236, sources, 9, "regular", LGREY)


def draw_stat_panel(x, y):
    w, h = 230, 240
    fill_rect(x, y, x + w, y + h, DARK)
    draw_text_centered(x + w // 2, y + 22, "THE DAY IN NUMBERS", 13, "bold", GOLD)
    for i, (val, label, num, color) in enumerate(STATS):
        by = y + 56 + i * 36
        draw_text(x + 12, by, val, 28, "bold", color)
        lx = x + 12 + text_width(val, 28, "bold") + 8
        draw_text(lx, by, label, 9, "bold", WHITE)
        draw_num_disc(x + w - 14, by - 10, num, r=7, bg=color, fg=DARK, size=9)


def draw_small_card(x, y, num, region, head, deck, sources, badge, art):
    w, h = 192, 130
    fill_rect(x, y, x + w, y + h, WHITE)
    draw_rect_outline(x, y, x + w, y + h, CARD_LINE, 1)
    ART[art](x + 1, y + 1, w - 2, 50)
    draw_num_disc(x + 12, y + 13, num, r=8, size=10)
    draw_badge(x + w - 4, y + 5, badge)
    draw_wrapped(x + 8, y + 70, head, 16, "bold", INK, w - 16, 18, 2)
    draw_wrapped(x + 8, y + 104, deck, 10, "regular", INK, w - 16, 12, 2)
    draw_text(x + 8, y + 127, sources, 8, "regular", LGREY)


def draw_also_list(x0, y0):
    """3 columns; returns the bottom y of the tallest column."""
    header = "ALSO TODAY \u2014 13 MORE STORIES FROM TUESDAY"
    draw_text(x0, y0, header, 12, "bold", INK)
    draw_text_right(W - MARGIN, y0, "ALL FIRST REPORTED TUE 24 NOV", 9,
                    "bold", GREY)
    col_w = 320
    col_x = [x0, x0 + 336, x0 + 672]
    bottom = y0
    for ci, col in enumerate(ALSO_COLS):
        cx = col_x[ci]
        cy = y0 + 14
        for (num, region, title, desc, source) in col:
            # flag
            draw_flag(cx, cy, 14, 9, [REGION_COLOR[region], WHITE,
                                       REGION_COLOR[region]])
            # title + source on one line
            draw_text(cx + 20, cy + 9, title, 11, "bold", INK)
            draw_text_right(cx + col_w, cy + 9, source, 9, "regular", LGREY)
            # desc, wrapped under the title (10px, leading 11)
            lines = draw_wrapped(cx + 20, cy + 20, desc, 10, "regular", GREY,
                                 col_w - 20, 11)
            cy += 9 + 11 * len(lines) + 3
        bottom = max(bottom, cy)
    return bottom


def draw_datecheck_item(x, y, text, date, col_w, size=10, leading=11):
    """One left-out item: text wrapped, date (red) appended to the last line
    if it fits, else on its own line right-aligned. Returns height used."""
    date_w = text_width(date, size, "bold")
    lines = wrap_text(text, size, "regular", col_w)
    # room for " \u2014 date" after the last line?
    last_w = text_width(lines[-1], size, "regular")
    need = text_width(" \u2014 ", size, "regular") + date_w
    extra_line = (last_w + need > col_w)
    cy = y
    for line in lines:
        draw_text(x, cy, line, size, "regular", INK)
        cy += leading
    if not extra_line:
        draw_text(x + last_w, cy - leading, " \u2014 " + date, size, "bold", RED)
    else:
        draw_text_right(x + col_w, cy, date, size, "bold", RED)
        cy += leading
    return cy - y


def draw_datecheck(x, y, w, h):
    fill_rect(x, y, x + w, y + h, (253, 248, 240))
    draw_rect_outline(x, y, x + w, y + h, RED, 2)
    ix = x + 10
    draw_text(ix, y + 18, "DATE CHECK \u2014 WHAT IS NOT IN THIS IMAGE",
              13, "bold", RED)
    draw_text(ix, y + 33,
              "Rule: only stories first reported on Tuesday 24 November 2026 "
              "are in the main list.", 10, "regular", INK)
    draw_text(ix, y + 47, "Left out because they happened on an earlier day:",
              10, "bold", INK)
    col_w = 188
    col_x = [ix, ix + 196, ix + 392]
    max_bottom = y + 60
    for ci, col in enumerate(DATECHECK_COLS):
        cy = y + 60
        for (text, date) in col:
            used = draw_datecheck_item(col_x[ci], cy, text, date, col_w)
            cy += used + 3
        max_bottom = max(max_bottom, cy)
    draw_text(ix, max_bottom + 12, DATECHECK_ALSO, 10, "regular", GREY)
    return max_bottom + 12 + 12


def draw_footer(y):
    draw_text(MARGIN, y, FOOTER_SOURCES, 9, "regular", GREY)
    # legend, right aligned
    lx = W - MARGIN
    for (label, color) in [("CONFIRMED", GREEN), ("REPORTED", ORANGE),
                           ("CLAIM", RED)]:
        tw = text_width(label, 9, "bold")
        lx -= tw
        fill_rect(lx - 12, y - 8, lx - 3, y + 1, color)
        draw_text(lx, y, label, 9, "bold", INK)
        lx -= 22


def main():
    fill_rect(0, 0, W, H, CREAM)
    draw_header()
    # leads row
    ly = 150
    for i, lead in enumerate(LEADS):
        draw_lead_card(MARGIN + i * 254, ly, *lead)
    draw_stat_panel(MARGIN + 3 * 254, ly)
    # small cards, two rows of five
    for r in range(2):
        for c in range(5):
            s = SMALL[r * 5 + c]
            draw_small_card(MARGIN + c * 200, 394 + r * 134, *s)
    # also-list
    also_bottom = draw_also_list(MARGIN, 672)
    # bottom band: DATE CHECK + map
    band_y = int(also_bottom) + 6
    band_h = 1006 - band_y
    dc_bottom = draw_datecheck(MARGIN, band_y, 600, band_h)
    map_x = MARGIN + 616
    map_w = W - MARGIN - map_x
    draw_map(map_x, band_y, map_w, band_h)
    draw_text(map_x + 6, band_y + 12, "WHERE THE DAY HAPPENED", 10, "bold",
              WHITE)
    draw_text_right(map_x + map_w - 6, band_y + 12, "PINS = STORY NUMBERS",
                    9, "bold", WHITE)
    draw_footer(1018)
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "entry.png")
    n = write_png(path)
    import hashlib
    sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
    print("wrote %s %d bytes sha256=%s" % (path, n, sha))


if __name__ == "__main__":
    main()
