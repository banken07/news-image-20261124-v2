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
    """Rising market: candlesticks, gold trend line, AI chip."""
    fill_rect(x, y, x + w, y + h, (16, 42, 64))
    for gy in range(1, 4):
        draw_line(x + 6, y + h * gy // 4, x + w - 6, y + h * gy // 4,
                  (32, 70, 100), 1)
    # candlesticks, rising left to right
    n = 6
    cw = w // (n + 1)
    for i in range(n):
        cx0 = x + cw // 2 + i * cw
        top = y + h * (0.66 - 0.075 * i)
        bot = y + h * (0.90 - 0.02 * i)
        btop = top + h * 0.07
        bbot = bot - h * 0.05
        col = (46, 204, 113) if i % 3 != 2 else (224, 82, 60)
        draw_line(cx0 + cw // 2, int(top), cx0 + cw // 2, int(bot), col, 1)
        fill_rect(cx0 + 3, int(btop), cx0 + cw - 3, int(bbot), col)
    # gold trend line + arrowhead (ends clear of the badge, top right)
    pts = [(x + 10, y + h * 0.80), (x + w * 0.36, y + h * 0.62),
           (x + w * 0.60, y + h * 0.64), (x + w * 0.82, y + h * 0.30)]
    for a, b in zip(pts, pts[1:]):
        draw_line(int(a[0]), int(a[1]), int(b[0]), int(b[1]), GOLD, 3)
    ex, ey = int(pts[-1][0]), int(pts[-1][1])
    fill_poly([(ex, ey), (ex - 13, ey - 1), (ex - 3, ey + 13)], GOLD)
    # AI chip, bottom right
    chx, chy = x + w - 62, y + h - 32
    fill_rect(chx, chy, chx + 50, chy + 24, (10, 20, 30))
    draw_rect_outline(chx, chy, chx + 50, chy + 24, GOLD, 1)
    fill_rect(chx + 15, chy + 7, chx + 35, chy + 17, GOLD)
    for px in range(chx + 6, chx + 48, 8):
        fill_rect(px, chy - 4, px + 3, chy, GOLD)
        fill_rect(px, chy + 24, px + 3, chy + 28, GOLD)


def art_drone(x, y, w, h):
    """Night drone over Polish terrain, radar sweep + searchlights."""
    # dusk bands
    fill_rect(x, y, x + w, y + h * 0.55, (24, 32, 68))
    fill_rect(x, y + h * 0.55, x + w, y + h * 0.72, (58, 62, 110))
    fill_rect(x, y + h * 0.72, x + w, y + h * 0.80, (232, 140, 60))
    fill_rect(x, y + h * 0.80, x + w, y + h, (28, 30, 38))
    # stars
    for (sx, sy) in [(0.08, 0.10), (0.22, 0.06), (0.38, 0.14), (0.55, 0.08),
                      (0.72, 0.12), (0.88, 0.07), (0.94, 0.20), (0.15, 0.22)]:
        fill_circle(x + w * sx, y + h * sy, 2, WHITE)
    # terrain silhouette
    fill_poly([(x, y + h), (x, y + h * 0.86), (x + w * 0.25, y + h * 0.80),
               (x + w * 0.5, y + h * 0.88), (x + w * 0.75, y + h * 0.82),
               (x + w, y + h * 0.87), (x + w, y + h)], (16, 18, 26))
    # searchlight beams from the ground to the drone
    cx, cy = x + w * 0.50, y + h * 0.40
    fill_poly([(x + w * 0.18, y + h - 2), (x + w * 0.24, y + h - 2),
               (cx - 6, cy + 4), (cx - 14, cy + 4)], (240, 230, 180))
    fill_poly([(x + w * 0.88, y + h - 2), (x + w * 0.94, y + h - 2),
               (cx + 12, cy + 4), (cx + 4, cy + 4)], (240, 230, 180))
    # radar, bottom left: concentric rings + sweep + blip
    rx, ry = x + w * 0.13, y + h * 0.72
    for r in (7, 13, 19):
        draw_circle_ring(rx, ry, r, (120, 220, 140))
    draw_line(rx, ry, rx + 16, ry - 10, (120, 220, 140), 2)
    fill_circle(rx + 16, ry - 10, 3, (120, 220, 140))
    fill_circle(rx, ry, 3, (120, 220, 140))
    # drone: arms, rotors, body, red eye
    for (dx, dy) in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
        ax, ay = cx + dx * w * 0.16, cy + dy * h * 0.22
        draw_line(int(cx), int(cy), int(ax), int(ay), (200, 205, 215), 3)
        fill_circle(int(ax), int(ay), 8, (24, 74, 135))
        draw_circle_ring(int(ax), int(ay), 8, WHITE)
        fill_circle(int(ax), int(ay), 3, WHITE)
    fill_poly([(cx - 24, cy - 7), (cx + 24, cy - 7), (cx + 16, cy + 8),
               (cx - 16, cy + 8)], (190, 195, 205))
    draw_rect_outline(cx - 24, cy - 7, cx + 24, cy + 8, INK, 1)
    fill_circle(int(cx), int(cy), 6, RED)


def art_rocket(x, y, w, h):
    """Launch to Tiangong: rocket, Earth arc, station on orbit."""
    fill_rect(x, y, x + w, y + h, (8, 12, 28))
    for (sx, sy, sr) in [(0.08, 0.12, 2), (0.18, 0.05, 1), (0.30, 0.18, 2),
                          (0.45, 0.08, 1), (0.62, 0.15, 2), (0.78, 0.06, 1),
                          (0.90, 0.16, 2), (0.96, 0.30, 1), (0.05, 0.35, 1),
                          (0.70, 0.26, 1)]:
        fill_circle(x + w * sx, y + h * sy, sr, WHITE)
    # Earth arc, bottom left: a shallow cap that stays INSIDE the art rect
    # (a big off-canvas circle would paint over the card text below).
    fill_poly([(x, y + h * 0.80), (x + w * 0.08, y + h * 0.86),
               (x + w * 0.18, y + h * 0.90), (x + w * 0.30, y + h * 0.95),
               (x + w * 0.42, y + h), (x, y + h)], (40, 110, 200))
    for a, b in [((x, y + h * 0.80), (x + w * 0.08, y + h * 0.86)),
                 ((x + w * 0.08, y + h * 0.86), (x + w * 0.18, y + h * 0.90)),
                 ((x + w * 0.18, y + h * 0.90), (x + w * 0.30, y + h * 0.95)),
                 ((x + w * 0.30, y + h * 0.95), (x + w * 0.42, y + h))]:
        draw_line(int(a[0]), int(a[1]), int(b[0]), int(b[1]),
                  (150, 200, 240), 1)
    fill_circle(x + w * 0.10, y + h * 0.90, 6, (60, 160, 90))
    fill_circle(x + w * 0.24, y + h * 0.94, 5, (60, 160, 90))
    fill_circle(x + w * 0.16, y + h * 0.88, 4, WHITE)
    # orbit line + station, upper left
    draw_line(x + 8, y + h * 0.21, x + w * 0.45, y + h * 0.08,
              (200, 210, 225), 1)
    sx, sy = x + w * 0.22, y + h * 0.14
    fill_rect(sx - 4, sy - 3, sx + 4, sy + 3, WHITE)
    fill_rect(sx - 20, sy - 2, sx - 5, sy + 2, (70, 130, 200))
    fill_rect(sx + 5, sy - 2, sx + 20, sy + 2, (70, 130, 200))
    draw_rect_outline(sx - 20, sy - 2, sx + 20, sy + 2, WHITE, 1)
    # rocket, centre right
    cx = x + w * 0.55
    fill_poly([(cx - 11, y + h - 28), (cx + 11, y + h - 28), (cx, y + h - 4)],
              (240, 180, 40))
    fill_poly([(cx - 5, y + h - 28), (cx + 5, y + h - 28), (cx, y + h - 12)],
              (255, 90, 40))
    fill_poly([(cx - 13, y + h - 48), (cx - 24, y + h - 26), (cx - 11, y + h - 28)],
              (168, 40, 32))
    fill_poly([(cx + 13, y + h - 48), (cx + 24, y + h - 26), (cx + 11, y + h - 28)],
              (168, 40, 32))
    fill_poly([(cx - 13, y + 12), (cx + 13, y + 12), (cx + 13, y + h - 28),
               (cx - 13, y + h - 28)], (232, 232, 235))
    fill_poly([(cx - 13, y + 12), (cx + 13, y + 12), (cx, y + 2)], (200, 40, 40))
    fill_rect(cx - 13, y + h * 0.45, cx + 13, y + h * 0.45 + 3, (200, 40, 40))
    fill_circle(cx, y + 30, 6, (40, 110, 200))
    draw_circle_ring(cx, y + 30, 6, INK)


def art_cross(x, y, w, h):
    """Public health: shield + cross, clinic block, ECG line."""
    fill_rect(x, y, x + w, y + h, (214, 232, 244))
    # clinic block, right side
    fill_rect(x + w - 52, y + 8, x + w - 8, y + h - 14, WHITE)
    draw_rect_outline(x + w - 52, y + 8, x + w - 8, y + h - 14, (24, 74, 135), 1)
    for wy in range(int(y + 13), int(y + h - 16), 8):
        fill_rect(x + w - 46, wy, x + w - 36, wy + 4, (24, 74, 135))
        fill_rect(x + w - 30, wy, x + w - 20, wy + 4, (24, 74, 135))
    # shield, centre left
    cx, cy = x + w * 0.38, y + h * 0.48
    fill_poly([(cx - 18, cy - 15), (cx + 18, cy - 15), (cx + 18, cy + 2),
               (cx, cy + 18), (cx - 18, cy + 2)], WHITE)
    draw_line(cx - 18, cy - 15, cx + 18, cy - 15, (24, 74, 135), 1)
    draw_line(cx + 18, cy - 15, cx + 18, cy + 2, (24, 74, 135), 1)
    draw_line(cx + 18, cy + 2, cx, cy + 18, (24, 74, 135), 1)
    draw_line(cx, cy + 18, cx - 18, cy + 2, (24, 74, 135), 1)
    draw_line(cx - 18, cy + 2, cx - 18, cy - 15, (24, 74, 135), 1)
    fill_rect(cx - 4, cy - 10, cx + 4, cy + 8, RED)
    fill_rect(cx - 10, cy - 4, cx + 10, cy + 2, RED)
    # ECG line across the bottom
    pts = [(x + 6, y + h - 8), (x + w * 0.30, y + h - 8),
           (x + w * 0.36, y + h - 16), (x + w * 0.42, y + h - 2),
           (x + w * 0.48, y + h - 8), (x + w * 0.62, y + h - 8),
           (x + w * 0.67, y + h - 14), (x + w * 0.72, y + h - 8),
           (x + w - 6, y + h - 8)]
    for a, b in zip(pts, pts[1:]):
        draw_line(int(a[0]), int(a[1]), int(b[0]), int(b[1]), RED, 2)


def art_flame(x, y, w, h):
    """Cikande factory fire: structure, bright flames, dark smoke."""
    fill_rect(x, y, x + w, y + h, (74, 58, 48))
    # warm glow behind the flames
    fill_circle(x + w * 0.42, y + h * 0.55, 22, (120, 60, 20))
    # dark smoke drifting up-left from the roof (clear of disc + badge)
    for (sx, sy, sr) in [(0.36, 0.26, 6), (0.44, 0.20, 7), (0.53, 0.24, 6)]:
        fill_circle(x + w * sx, y + h * sy, sr, (38, 34, 30))
    # factory silhouette: main hall + sawtooth roof + chimney
    fill_poly([(x + 8, y + h * 0.52), (x + 26, y + h * 0.36),
               (x + 44, y + h * 0.52), (x + 62, y + h * 0.36),
               (x + 80, y + h * 0.52), (x + w - 34, y + h * 0.52),
               (x + w - 34, y + h - 4), (x + 8, y + h - 4)], (18, 18, 22))
    fill_rect(x + w - 30, y + h * 0.18, x + w - 20, y + h - 4, (18, 18, 22))
    fill_circle(x + w - 25, y + h * 0.48, 6, (38, 34, 30))
    # glowing windows
    for wx in (x + 16, x + 40, x + 64):
        fill_rect(wx, y + h * 0.66, wx + 12, y + h * 0.82, (250, 160, 30))
    # flames: three layered tongues from the roof
    fx = x + w * 0.42
    fill_poly([(fx, y + 2), (fx + 14, y + h * 0.42), (fx + 8, y + h * 0.55),
               (fx - 8, y + h * 0.55), (fx - 14, y + h * 0.42)], (240, 110, 20))
    fill_poly([(fx, y + h * 0.22), (fx + 9, y + h * 0.45), (fx + 5, y + h * 0.55),
               (fx - 5, y + h * 0.55), (fx - 9, y + h * 0.45)], (250, 180, 40))
    fill_poly([(fx, y + h * 0.38), (fx + 5, y + h * 0.50), (fx, y + h * 0.55),
               (fx - 5, y + h * 0.50)], (255, 220, 90))
    # second smaller flame, left roof
    fx2 = x + w * 0.20
    fill_poly([(fx2, y + h * 0.30), (fx2 + 9, y + h * 0.52), (fx2, y + h * 0.58),
               (fx2 - 9, y + h * 0.52)], (240, 110, 20))
    fill_poly([(fx2, y + h * 0.42), (fx2 + 5, y + h * 0.52), (fx2, y + h * 0.58),
               (fx2 - 5, y + h * 0.52)], (250, 180, 40))
    # embers
    for (ex, ey) in [(0.60, 0.20), (0.68, 0.32), (0.30, 0.18), (0.55, 0.08)]:
        fill_circle(x + w * ex, y + h * ey, 2, (255, 200, 60))
    draw_line(x + 4, y + h - 3, x + w - 4, y + h - 3, (10, 10, 12), 2)


def art_boat(x, y, w, h):
    """Rohingya return: dawn road, walking families, hills, flag."""
    fill_rect(x, y, x + w, y + h * 0.55, (250, 200, 120))
    fill_rect(x, y + h * 0.55, x + w, y + h, (226, 170, 110))
    # sun, low on the horizon (clear of the badge)
    fill_circle(x + w * 0.68, y + h * 0.58, 8, (255, 240, 180))
    draw_circle_ring(x + w * 0.68, y + h * 0.58, 11, (255, 240, 180))
    # distant hills
    fill_poly([(x, y + h * 0.62), (x + w * 0.25, y + h * 0.50),
               (x + w * 0.5, y + h * 0.62), (x + w * 0.75, y + h * 0.52),
               (x + w, y + h * 0.60), (x + w, y + h), (x, y + h)],
              (120, 110, 70))
    # road: perspective band to the horizon
    fill_poly([(x + w * 0.42, y + h * 0.62), (x + w * 0.58, y + h * 0.62),
               (x + w * 0.78, y + h), (x + w * 0.22, y + h)], (232, 214, 178))
    draw_line(x + w * 0.42, y + h * 0.62, x + w * 0.22, y + h, (180, 160, 120), 1)
    draw_line(x + w * 0.58, y + h * 0.62, x + w * 0.78, y + h, (180, 160, 120), 1)
    # walking figures, near to far
    for (fx, fy, s) in [(0.36, 0.76, 1.05), (0.50, 0.68, 0.8),
                         (0.62, 0.76, 1.2)]:
        px, py = x + w * fx, y + h * fy
        fill_circle(px, py - 9 * s, 3 * s, (40, 32, 28))
        fill_poly([(px - 4 * s, py - 6 * s), (px + 4 * s, py - 6 * s),
                   (px + 5 * s, py + 4 * s), (px - 5 * s, py + 4 * s)],
                  (40, 32, 28))
        draw_line(px - 2 * s, py + 4 * s, px - 3 * s, py + 9 * s, (40, 32, 28), 2)
        draw_line(px + 2 * s, py + 4 * s, px + 3 * s, py + 9 * s, (40, 32, 28), 2)
        # bundle on the head
        fill_circle(px, py - 13 * s, 2 * s, (120, 70, 40))
    # flag at the horizon
    draw_line(x + w * 0.82, y + h * 0.44, x + w * 0.82, y + h * 0.58,
              (40, 32, 28), 2)
    fill_rect(x + w * 0.82, y + h * 0.44, x + w * 0.82 + 12, y + h * 0.44 + 7,
              (40, 120, 56))


def art_flags(x, y, w, h):
    """Four-way talks: four flags behind a table with documents."""
    fill_rect(x, y, x + w, y + h, (238, 232, 220))
    # four flags: UA, EU, US, RU (left to right), kept clear of the badge
    flag_cols = [[(24, 74, 135), (240, 200, 40)],
                 [(24, 74, 135), (24, 74, 135)],
                 [(180, 40, 40), (255, 255, 255)],
                 [(255, 255, 255), (24, 74, 135), (180, 40, 40)]]
    for i, cols in enumerate(flag_cols):
        fx = x + 10 + i * 26
        fy = y + 10
        draw_line(fx, fy, fx, y + h - 16, INK, 2)
        fh = 11
        for j, c in enumerate(cols):
            fill_rect(fx + 1, fy + j * fh // len(cols), fx + 17,
                      fy + (j + 1) * fh // len(cols), c)
        draw_rect_outline(fx + 1, fy, fx + 17, fy + fh, INK, 1)
        if i == 1:  # EU stars
            for (dx, dy) in [(4, 3), (12, 3), (8, 8)]:
                fill_circle(fx + dx, fy + dy, 1, WHITE)
    # table
    fill_rect(x + 10, y + h - 14, x + w - 10, y + h - 8, (120, 82, 52))
    draw_line(x + 18, y + h - 8, x + 18, y + h - 3, INK, 2)
    draw_line(x + w - 18, y + h - 8, x + w - 18, y + h - 3, INK, 2)
    # documents + microphones on the table
    fill_rect(x + w // 2 - 14, y + h - 22, x + w // 2 + 14, y + h - 14, WHITE)
    draw_rect_outline(x + w // 2 - 14, y + h - 22, x + w // 2 + 14, y + h - 14,
                      INK, 1)
    draw_line(x + w // 2 - 10, y + h - 19, x + w // 2 + 10, y + h - 19, GREY, 1)
    draw_line(x + w // 2 - 10, y + h - 16, x + w // 2 + 4, y + h - 16, GREY, 1)
    for mx in (x + w * 0.28, x + w * 0.72):
        draw_line(mx, y + h - 14, mx, y + h - 22, INK, 1)
        fill_circle(mx, y + h - 23, 2, INK)


def art_tanker(x, y, w, h):
    """Hormuz strait: tanker between cliffs, calm sea, sun."""
    fill_rect(x, y, x + w, y + h * 0.42, (220, 230, 238))
    fill_rect(x, y + h * 0.42, x + w, y + h, (24, 74, 135))
    # strait cliffs left + right
    fill_poly([(x, y + h * 0.42), (x + w * 0.10, y + h * 0.30),
               (x + w * 0.16, y + h * 0.55), (x + w * 0.08, y + h),
               (x, y + h)], (90, 80, 70))
    fill_poly([(x + w, y + h * 0.42), (x + w * 0.90, y + h * 0.30),
               (x + w * 0.84, y + h * 0.55), (x + w * 0.92, y + h),
               (x + w, y + h)], (90, 80, 70))
    # waves (between the cliffs only)
    for wy in (0.50, 0.62, 0.74, 0.88):
        for wx in range(int(x + w * 0.20), int(x + w * 0.80), 16):
            draw_line(wx, y + h * wy, wx + 9, y + h * wy, (150, 190, 225), 2)
    # tanker, centre
    hx0, hx1 = x + w * 0.24, x + w * 0.78
    hy = y + h * 0.66
    fill_poly([(hx0, hy), (hx1, hy), (hx1 - 8, hy + 10), (hx0 + 8, hy + 10)],
              (16, 24, 34))
    # bridge tower
    fill_rect(hx1 - 22, hy - 14, hx1 - 10, hy, WHITE)
    draw_rect_outline(hx1 - 22, hy - 14, hx1 - 10, hy, INK, 1)
    # funnel + smoke
    fill_rect(hx1 - 34, hy - 12, hx1 - 27, hy, (168, 40, 32))
    fill_circle(hx1 - 30, hy - 16, 3, GREY)
    fill_circle(hx1 - 26, hy - 20, 4, GREY)
    # containers
    for i, c in enumerate([(168, 40, 32), (24, 74, 135), (198, 90, 30)]):
        bx = hx0 + 8 + i * 17
        fill_rect(bx, hy - 11, bx + 14, hy, c)
        draw_rect_outline(bx, hy - 11, bx + 14, hy, INK, 1)
    # sun
    fill_circle(x + w * 0.50, y + h * 0.16, 6, (240, 180, 40))


def art_ballot(x, y, w, h):
    """US Capitol dome + ballot box with a big check."""
    fill_rect(x, y, x + w, y + h, (222, 232, 242))
    cx = x + w * 0.42
    base = y + h * 0.60
    # dome: arc polygon
    pts = []
    for a in range(0, 181, 10):
        t = math.radians(a)
        pts.append((cx + 24 * math.cos(t), base - 18 * math.sin(t)))
    fill_poly(pts, (198, 206, 220))
    for a, b in zip(pts, pts[1:]):
        draw_line(int(a[0]), int(a[1]), int(b[0]), int(b[1]), INK, 2)
    # flag on the dome
    draw_line(cx, base - 18, cx, base - 26, INK, 1)
    fill_rect(cx, base - 26, cx + 10, base - 21, (180, 40, 40))
    # drum + columns + plinth
    fill_rect(cx - 30, base, cx + 30, y + h * 0.66, (198, 206, 220))
    for i in range(5):
        colx = cx - 24 + i * 12
        fill_rect(colx, y + h * 0.66, colx + 5, y + h * 0.86, WHITE)
        draw_rect_outline(colx, y + h * 0.66, colx + 5, y + h * 0.86, INK, 1)
    fill_rect(cx - 34, y + h * 0.86, cx + 34, y + h * 0.92, (200, 200, 205))
    draw_line(x + w * 0.12, y + h - 4, x + w * 0.72, y + h - 4, INK, 2)
    # ballot box + big check, right
    bx, by = x + w * 0.76, y + h * 0.68
    fill_rect(bx, by, bx + 26, by + 14, (24, 74, 135))
    fill_rect(bx + 3, by - 8, bx + 23, by, WHITE)
    draw_rect_outline(bx + 3, by - 8, bx + 23, by, INK, 1)
    draw_rect_outline(bx, by, bx + 26, by + 14, INK, 1)
    draw_line(bx - 4, by - 2, bx + 8, by + 12, GREEN, 4)
    draw_line(bx + 8, by + 12, bx + 30, by - 12, GREEN, 4)


def art_mountain(x, y, w, h):
    """Nepal-India summit: Everest backdrop, crossed flags, table."""
    fill_rect(x, y, x + w, y + h, (216, 230, 240))
    # sun (clear of the badge)
    fill_circle(x + w * 0.58, y + h * 0.16, 5, (240, 180, 40))
    # Everest backdrop
    fill_poly([(x, y + h), (x + w * 0.30, y + h * 0.28),
               (x + w * 0.55, y + h)], (90, 110, 140))
    fill_poly([(x + w * 0.30, y + h * 0.28), (x + w * 0.24, y + h * 0.40),
               (x + w * 0.36, y + h * 0.40)], WHITE)
    fill_poly([(x + w * 0.45, y + h), (x + w * 0.72, y + h * 0.16),
               (x + w, y + h)], (60, 80, 110))
    fill_poly([(x + w * 0.72, y + h * 0.16), (x + w * 0.67, y + h * 0.28),
               (x + w * 0.77, y + h * 0.28)], WHITE)
    # crossed flags, centre
    cx, cy = x + w * 0.44, y + h * 0.52
    draw_line(cx - 22, cy + 12, cx + 10, cy - 14, INK, 2)
    draw_line(cx + 22, cy + 12, cx - 10, cy - 14, INK, 2)
    # Nepal crimson (right-leaning pole's flag)
    fill_rect(cx + 10, cy - 14, cx + 28, cy - 3, (200, 30, 50))
    draw_rect_outline(cx + 10, cy - 14, cx + 28, cy - 3, INK, 1)
    # India tricolour (left-leaning pole's flag)
    for j, c in enumerate([(255, 153, 51), WHITE, (19, 136, 8)]):
        fill_rect(cx - 28, cy - 14 + j * 4, cx - 10, cy - 14 + (j + 1) * 4, c)
    draw_rect_outline(cx - 28, cy - 14, cx - 10, cy - 3, INK, 1)
    # table + document
    draw_line(x + w * 0.28, cy + 14, x + w * 0.72, cy + 14, INK, 3)
    draw_line(cx - 14, cy + 14, cx - 14, cy + 20, INK, 2)
    draw_line(cx + 14, cy + 14, cx + 14, cy + 20, INK, 2)
    fill_rect(cx - 10, cy + 8, cx + 10, cy + 13, WHITE)
    draw_rect_outline(cx - 10, cy + 8, cx + 10, cy + 13, INK, 1)


def art_talks(x, y, w, h):
    """Doha talks: West Bay skyline at dusk, long table, two flags."""
    fill_rect(x, y, x + w, y + h, (250, 214, 170))
    # crescent moon, top centre-left
    fill_circle(x + w * 0.30, y + h * 0.16, 6, (255, 244, 200))
    fill_circle(x + w * 0.30 + 3, y + h * 0.16 - 1, 5, (250, 214, 170))
    # skyline silhouettes
    towers = [(0.04, 0.55, 0.10), (0.16, 0.42, 0.09), (0.27, 0.62, 0.10),
              (0.40, 0.48, 0.09), (0.52, 0.58, 0.11), (0.65, 0.40, 0.09),
              (0.76, 0.56, 0.10), (0.88, 0.46, 0.09)]
    for (tx, th, tw) in towers:
        fill_rect(x + w * tx, y + h * th, x + w * (tx + tw), y + h * 0.86,
                  (60, 52, 66))
    # pointed tower, centre-right
    fill_poly([(x + w * 0.65, y + h * 0.40), (x + w * 0.69, y + h * 0.30),
               (x + w * 0.74, y + h * 0.40)], (60, 52, 66))
    # lit windows
    for (wx, wy) in [(0.18, 0.50), (0.20, 0.60), (0.42, 0.56), (0.67, 0.48),
                      (0.78, 0.64), (0.90, 0.54)]:
        fill_rect(x + w * wx, y + h * wy, x + w * wx + 3, y + h * wy + 3,
                  (255, 220, 120))
    # long table + chairs + document
    fill_rect(x + w * 0.20, y + h * 0.86, x + w * 0.80, y + h * 0.93,
              (90, 60, 40))
    fill_rect(x + w * 0.20, y + h * 0.70, x + w * 0.20 + 10, y + h * 0.86,
              (40, 36, 44))
    fill_rect(x + w * 0.80 - 10, y + h * 0.70, x + w * 0.80, y + h * 0.86,
              (40, 36, 44))
    fill_rect(x + w * 0.46, y + h * 0.80, x + w * 0.54, y + h * 0.86, WHITE)
    # two flags on the table: Qatar maroon + light blue
    draw_line(x + w * 0.34, y + h * 0.86, x + w * 0.34, y + h * 0.60, INK, 1)
    fill_rect(x + w * 0.34, y + h * 0.60, x + w * 0.34 + 16, y + h * 0.60 + 10,
              (128, 20, 40))
    draw_line(x + w * 0.64, y + h * 0.86, x + w * 0.64, y + h * 0.60, INK, 1)
    fill_rect(x + w * 0.64, y + h * 0.60, x + w * 0.64 + 16, y + h * 0.60 + 10,
              (24, 120, 160))


def art_fence(x, y, w, h):
    """Estonia border in winter: checkpoint, barrier, fence, snow."""
    fill_rect(x, y, x + w, y + h * 0.60, (206, 220, 232))
    fill_rect(x, y + h * 0.60, x + w, y + h, WHITE)
    # snowflakes
    for (sx, sy) in [(0.10, 0.12), (0.25, 0.06), (0.40, 0.16), (0.55, 0.08),
                      (0.70, 0.14), (0.85, 0.06), (0.94, 0.20), (0.18, 0.26)]:
        fill_circle(x + w * sx, y + h * sy, 2, (140, 160, 180))
    # pines, left
    for (px, top) in [(0.14, 0.30), (0.24, 0.38)]:
        fill_poly([(x + w * px, y + h * top), (x + w * px - 9, y + h * 0.62),
                   (x + w * px + 9, y + h * 0.62)], (30, 90, 60))
    # fence, left half: posts + rails + barbed zigzag
    for i in range(4):
        bx = x + 8 + i * 16
        fill_rect(bx, y + h * 0.44, bx + 3, y + h * 0.92, INK)
    draw_line(x + 6, y + h * 0.50, x + w * 0.38, y + h * 0.50, INK, 2)
    draw_line(x + 6, y + h * 0.72, x + w * 0.38, y + h * 0.72, INK, 2)
    pts = []
    for i in range(9):
        pts.append((x + 6 + i * 8, y + h * 0.44 - (4 if i % 2 == 0 else 0)))
    for a, b in zip(pts, pts[1:]):
        draw_line(int(a[0]), int(a[1]), int(b[0]), int(b[1]), INK, 1)
    # checkpoint booth, right
    fill_rect(x + w * 0.62, y + h * 0.34, x + w * 0.82, y + h * 0.86, WHITE)
    draw_rect_outline(x + w * 0.62, y + h * 0.34, x + w * 0.82, y + h * 0.86,
                      INK, 1)
    fill_rect(x + w * 0.66, y + h * 0.42, x + w * 0.78, y + h * 0.54,
              (24, 74, 135))
    fill_rect(x + w * 0.62, y + h * 0.28, x + w * 0.82, y + h * 0.34,
              (180, 40, 40))
    # striped barrier arm, raised from the booth pivot
    for i in range(4):
        c = RED if i % 2 == 0 else WHITE
        fill_rect(x + w * 0.62 - (i + 1) * 9, y + h * 0.56 - i * 3,
                  x + w * 0.62 - i * 9, y + h * 0.56 - i * 3 + 5, c)
    fill_rect(x + w * 0.62 - 2, y + h * 0.56, x + w * 0.62 + 1, y + h * 0.90, INK)
    # Estonian flag on a freestanding pole, centre
    draw_line(x + w * 0.52, y + h * 0.22, x + w * 0.52, y + h * 0.86, INK, 1)
    for j, c in enumerate([(24, 74, 135), INK, WHITE]):
        fill_rect(x + w * 0.52, y + h * 0.22 + j * 3, x + w * 0.52 + 12,
                  y + h * 0.22 + (j + 1) * 3, c)


def art_blast(x, y, w, h):
    """Yemen strikes: ruined building, smoke column, dust, beam."""
    fill_rect(x, y, x + w, y + h, (232, 190, 150))
    fill_rect(x, y + h * 0.62, x + w, y + h, (200, 160, 120))
    # ruined building, left-centre: jagged broken top
    fill_poly([(x + w * 0.08, y + h), (x + w * 0.08, y + h * 0.42),
               (x + w * 0.16, y + h * 0.30), (x + w * 0.22, y + h * 0.44),
               (x + w * 0.30, y + h * 0.34), (x + w * 0.38, y + h * 0.46),
               (x + w * 0.46, y + h * 0.36), (x + w * 0.46, y + h)],
              (52, 46, 44))
    # dark window holes
    for (wx, wy) in [(0.13, 0.55), (0.20, 0.62), (0.28, 0.55), (0.35, 0.66),
                      (0.42, 0.58)]:
        fill_rect(x + w * wx, y + h * wy, x + w * wx + 6, y + h * wy + 7, INK)
    # smoke column rising from the ruin (clear of the badge)
    for (sx, sy, sr) in [(0.30, 0.38, 7), (0.26, 0.28, 8), (0.22, 0.20, 8)]:
        fill_circle(x + w * sx, y + h * sy, sr, (90, 82, 76))
    # second building, right, lower
    fill_poly([(x + w * 0.58, y + h), (x + w * 0.58, y + h * 0.58),
               (x + w * 0.66, y + h * 0.50), (x + w * 0.74, y + h * 0.60),
               (x + w * 0.82, y + h * 0.52), (x + w * 0.82, y + h)],
              (70, 62, 58))
    # dust cloud at the base
    for (dx, dy, dr) in [(0.20, 0.86, 6), (0.32, 0.86, 6), (0.48, 0.86, 6),
                          (0.62, 0.86, 6)]:
        fill_circle(x + w * dx, y + h * dy, dr, (226, 200, 160))
    # rescue beam
    fill_poly([(x + w * 0.90, y + h - 1), (x + w * 0.94, y + h - 1),
               (x + w * 0.72, y + h * 0.55), (x + w * 0.68, y + h * 0.55)],
              (255, 240, 190))
    # debris
    for (dx, dy) in [(0.12, 0.95), (0.26, 0.97), (0.52, 0.95), (0.70, 0.97)]:
        fill_rect(x + w * dx, y + h * dy, x + w * dx + 5, y + h * dy + 2, INK)

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
    (1, "SEOUL", 127, 37.5, 0, 0, "d", 12, 12),
    (2, "POLAND", 21, 52.2, -2, -2, "l", -30, 6),
    (3, "JIUQUAN", 98.5, 39.7, 2, 0, "r", 30, -28),
    (4, "GAZA", 34.5, 31.5, 2, 2, "l", -16, 56),
    (5, "CIKANDE", 106.2, -6.3, -2, 2, "r", 12, 12),
    (6, "KUALA LUMPUR", 101.7, 3.1, -2, -6, "d", 32, 60),
    (7, "KYIV", 30.5, 50.4, -2, 2, "l", -12, 40),
    (8, "HORMUZ", 56.5, 26.5, 6, -2, "u", 12, -54),
    (9, "WASHINGTON", -77, 38.9, -2, 2, "l", -12, -16),
    (10, "NEW DELHI", 77.2, 28.6, 2, -2, "r", 48, 32),
    (11, "DOHA", 51.5, 25.3, -2, -2, "d", 24, 48),
    (12, "NARVA", 28.2, 59.4, 2, -2, "l", -48, -16),
    (13, "LAHJ", 44.9, 13.0, -2, 2, "d", 14, 64),
]


def project(mx, my, mw, mh, lon, lat):
    # lat range 85..-60 (v16-style stretch): +24% vertical spread, which
    # untangles the Europe / Middle East / Asia pin cluster.
    return (mx + (lon + 180.0) / 360.0 * mw,
            my + (85.0 - lat) / 145.0 * mh)


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
    w, h = 246, 236
    fill_rect(x, y, x + w, y + h, WHITE)
    draw_rect_outline(x, y, x + w, y + h, CARD_LINE, 1)
    ART[art](x + 1, y + 1, w - 2, 96)
    draw_num_disc(x + 15, y + 15, num, r=9, size=11)
    draw_badge(x + w - 5, y + 5, badge)
    draw_text(x + 8, y + 108, REGION_SHORT[region], 10, "bold",
              REGION_COLOR[region])
    draw_wrapped(x + 8, y + 132, head, 21, "bold", INK, w - 16, 24, 2)
    draw_wrapped(x + 8, y + 176, deck, 12, "regular", INK, w - 16, 14, 2)
    draw_wrapped(x + 8, y + 204, subdeck, 10, "regular", GREY, w - 16, 12, 2)
    draw_text(x + 8, y + 230, sources, 9, "regular", LGREY)


def draw_stat_panel(x, y):
    w, h = 230, 236
    fill_rect(x, y, x + w, y + h, DARK)
    draw_text_centered(x + w // 2, y + 22, "THE DAY IN NUMBERS", 13, "bold", GOLD)
    for i, (val, label, num, color) in enumerate(STATS):
        by = y + 52 + i * 35
        draw_text(x + 12, by, val, 28, "bold", color)
        lx = x + 12 + text_width(val, 28, "bold") + 8
        draw_text(lx, by, label, 9, "bold", WHITE)
        draw_num_disc(x + w - 14, by - 10, num, r=7, bg=color, fg=DARK, size=9)


def draw_small_card(x, y, num, region, head, deck, sources, badge, art):
    w, h = 192, 130
    fill_rect(x, y, x + w, y + h, WHITE)
    draw_rect_outline(x, y, x + w, y + h, CARD_LINE, 1)
    ART[art](x + 1, y + 1, w - 2, 46)
    draw_num_disc(x + 12, y + 13, num, r=8, size=10)
    draw_badge(x + w - 4, y + 5, badge)
    draw_wrapped(x + 8, y + 66, head, 16, "bold", INK, w - 16, 18, 2)
    draw_wrapped(x + 8, y + 100, deck, 10, "regular", INK, w - 16, 11, 2)
    draw_text(x + 8, y + 126, sources, 8, "regular", LGREY)


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
        cy = y0 + 12
        for (num, region, title, desc, source) in col:
            # flag
            draw_flag(cx, cy, 14, 9, [REGION_COLOR[region], WHITE,
                                       REGION_COLOR[region]])
            # title + source on one line
            draw_text(cx + 20, cy + 9, title, 11, "bold", INK)
            draw_text_right(cx + col_w, cy + 9, source, 9, "regular", LGREY)
            # desc, wrapped under the title (10px, leading 12)
            lines = draw_wrapped(cx + 20, cy + 20, desc, 10, "regular", GREY,
                                 col_w - 20, 12)
            cy += 10 + 12 * len(lines) + 5
        bottom = max(bottom, cy)
    return bottom


def draw_datecheck_item(x, y, text, date, col_w, size=10, leading=12):
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
    draw_text(ix, y + 13, "DATE CHECK \u2014 WHAT IS NOT IN THIS IMAGE",
              13, "bold", RED)
    draw_text(ix, y + 27,
              "Rule: only stories first reported on Tuesday 24 November 2026 "
              "are in the main list.", 10, "regular", INK)
    draw_text(ix, y + 39, "Left out because they happened on an earlier day:",
              10, "bold", INK)
    col_w = 188
    col_x = [ix, ix + 196, ix + 392]
    max_bottom = y + 52
    for ci, col in enumerate(DATECHECK_COLS):
        cy = y + 52
        for (text, date) in col:
            used = draw_datecheck_item(col_x[ci], cy, text, date, col_w)
            cy += used + 2
        max_bottom = max(max_bottom, cy)
    draw_text(ix, max_bottom + 10, DATECHECK_ALSO, 10, "regular", GREY)
    return max_bottom + 10 + 12


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
            draw_small_card(MARGIN + c * 200, 390 + r * 134, *s)
    # also-list
    also_bottom = draw_also_list(MARGIN, 660)
    # bottom band: DATE CHECK + map (title strip above the map)
    band_y = int(also_bottom) + 8
    band_h = 1006 - band_y
    dc_bottom = draw_datecheck(MARGIN, band_y, 600, band_h)
    map_x = MARGIN + 616
    map_w = W - MARGIN - map_x
    fill_rect(map_x, band_y, map_x + map_w, band_y + 16, NAVY)
    draw_map(map_x, band_y + 16, map_w, band_h - 16)
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
