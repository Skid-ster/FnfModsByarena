"""
Procedural Trollge renderer.

Everything about the character -- silhouette, grin, eyes, limbs -- is drawn in
code with wobbly polylines so it keeps the "scribbled in MS Paint" look of the
meme while every pose is a genuinely different drawing (real animation, not a
single image being squashed).

Public API:

    draw_trollge(w, h, **pose) -> RGBA Image

`pose` keys (all optional, defaults shown in `REST_POSE`):
    lean        body lean in degrees
    head_tilt   head rotation in degrees
    head_dx/dy  head offset in pixels
    head_scale  head size multiplier
    arm_l/arm_r (shoulder_deg, elbow_deg)
    leg_l/leg_r (hip_deg, knee_deg)
    mouth       'grin' | 'smile' | 'open' | 'scream' | 'flat'
    eyes        'normal' | 'wide' | 'scared' | 'angry' | 'dead' | 'bloodshot'
    ink         fill colour
    jitter      how messy the lines are
    seed        rng seed (gives each frame its own scribble pattern)
    static      extra white-noise specks (0..1)
    veins       draw red veins in the eyes / grin
    drips       draw blood drips from the grin
"""

import math
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter

FRAME_W = 460
FRAME_H = 560
FOOT_Y = 540.0

INK = (10, 9, 12, 255)
DEEP = (26, 20, 26, 255)
BONE = (246, 245, 237, 255)
BLOOD = (168, 12, 24, 255)

S = 1.16  # design-unit -> pixel scale

#: Rest skeleton, in "design units" measured up from the feet.
REST = {
    "ankle": 18,
    "knee": 92,
    "hip": 152,
    "shoulder": 255,
    "neck": 270,
    "head": 322,
}
HEAD_RX = 104.0
HEAD_RY = 86.0
HIP_X = 22.0
SHOULDER_X = 34.0
ELBOW_DX = 34.0
ELBOW_DY = 78.0
HAND_DX = 16.0
HAND_DY = 72.0
KNEE_X = 30.0
FOOT_X = 40.0

REST_POSE = {
    "lean": 0.0,
    "head_tilt": 0.0,
    "head_dx": 0.0,
    "head_dy": 0.0,
    "head_scale": 1.0,
    "arm_l": (8.0, 10.0),
    "arm_r": (-8.0, -10.0),
    "leg_l": (0.0, 0.0),
    "leg_r": (0.0, 0.0),
    "mouth": "grin",
    "eyes": "normal",
    "ink": INK,
    "jitter": 1.6,
    "seed": 0,
    "static": 0.0,
    "veins": False,
    "drips": False,
}


# --------------------------------------------------------------------------- #
# Geometry helpers
# --------------------------------------------------------------------------- #

def _y(design_units):
    """Design units -> pixel Y (feet at FOOT_Y)."""
    return FOOT_Y - design_units * S


def _rot(p, origin, deg):
    if not deg:
        return p
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    x, y = p[0] - origin[0], p[1] - origin[1]
    return (origin[0] + x * ca - y * sa, origin[1] + x * sa + y * ca)


def _dir(origin, target, deg):
    """Vector from `origin` towards `target`, rotated by `deg` degrees."""
    dx, dy = target[0] - origin[0], target[1] - origin[1]
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    return (origin[0] + dx * ca - dy * sa, origin[1] + dx * sa + dy * ca)


def _j(p, rnd, amt):
    return (p[0] + rnd.uniform(-amt, amt), p[1] + rnd.uniform(-amt, amt))


def _taper(draw, pts, widths, colour, rnd, jitter=1.5, seed_pts=True):
    """Filled, tapering, hand-drawn looking polyline."""
    if len(pts) < 2:
        return
    left, right = [], []
    for i, p in enumerate(pts):
        w = widths[min(i, len(widths) - 1)] / 2.0
        if i == 0:
            nxt = pts[1]
            dx, dy = nxt[0] - p[0], nxt[1] - p[1]
        elif i == len(pts) - 1:
            prv = pts[i - 1]
            dx, dy = p[0] - prv[0], p[1] - prv[1]
        else:
            dx, dy = pts[i + 1][0] - pts[i - 1][0], pts[i + 1][1] - pts[i - 1][1]
        ln = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / ln * w, dx / ln * w
        q = _j(p, rnd, jitter) if seed_pts else p
        left.append((q[0] + nx, q[1] + ny))
        right.append((q[0] - nx, q[1] - ny))
    poly = left + right[::-1]
    draw.polygon(poly, fill=colour)


def _blob(draw, cx, cy, rx, ry, colour, rnd, jitter=2.0, points=22, squash=0.0, rot=0.0):
    """Wobbly filled ellipse."""
    pts = []
    for i in range(points):
        a = 2 * math.pi * i / points
        rr = 1.0 + rnd.uniform(-jitter, jitter) / max(rx, ry)
        x = math.cos(a) * rx * rr
        y = math.sin(a) * ry * rr * (1.0 - squash * math.cos(a))
        c, s = math.cos(rot), math.sin(rot)
        pts.append((cx + x * c - y * s, cy + x * s + y * c))
    draw.polygon(pts, fill=colour)
    return pts


def _scribble(draw, pts, colour, rnd, passes=2, width=2):
    """Extra loose strokes around a shape (the 'drawn with a mouse' look)."""
    for _ in range(passes):
        line = [_j(p, rnd, 3.0) for p in pts]
        draw.line(line + [line[0]], fill=colour, width=width, joint="curve")


# --------------------------------------------------------------------------- #
# Features
# --------------------------------------------------------------------------- #

def _draw_eyes(draw, cx, cy, rx, ry, mode, colour_ink, rnd, veins=False):
    eye_r = rx * (1.12 if mode in ("wide", "scared", "bloodshot") else 1.0)
    for side in (-1, 1):
        ex = cx + side * rx * 0.78
        ey = cy
        if mode == "angry":
            ey += ry * 0.12
        wr = eye_r * (0.46 if mode == "dead" else 0.5)
        hr = eye_r * 0.5
        _blob(draw, ex, ey, wr, hr, BONE, rnd, jitter=1.1, points=18)

        if mode == "dead":
            draw.line([(ex - wr * 0.7, ey - hr * 0.7), (ex + wr * 0.7, ey + hr * 0.7)],
                      fill=colour_ink, width=max(2, int(hr * 0.45)))
            draw.line([(ex - wr * 0.7, ey + hr * 0.7), (ex + wr * 0.7, ey - hr * 0.7)],
                      fill=colour_ink, width=max(2, int(hr * 0.45)))
        else:
            pup = hr * (0.34 if mode in ("wide", "scared") else 0.44)
            pdx = side * wr * (0.16 if mode == "scared" else 0.0)
            pdy = -hr * 0.1 if mode == "scared" else hr * 0.06
            _blob(draw, ex + pdx, ey + pdy, pup, pup, colour_ink, rnd, jitter=0.4, points=14)

        if mode == "angry":
            draw.line([(ex - wr, ey - hr * 0.9), (ex + wr, ey - hr * 1.35)],
                      fill=colour_ink, width=max(2, int(hr * 0.5)))
        if mode == "scared":
            # Raised brows.
            draw.line([(ex - wr * 0.9, ey - hr * 1.5), (ex + wr * 0.9, ey - hr * 1.9)],
                      fill=colour_ink, width=max(2, int(hr * 0.3)))

        if veins or mode == "bloodshot":
            for _ in range(5):
                a0 = rnd.uniform(0, 2 * math.pi)
                r0 = hr * rnd.uniform(0.35, 0.95)
                draw.line(
                    [
                        (ex + math.cos(a0) * r0, ey + math.sin(a0) * r0),
                        (ex + math.cos(a0) * wr * 0.95, ey + math.sin(a0) * hr * 0.95),
                    ],
                    fill=BLOOD,
                    width=1,
                )


def _draw_mouth(draw, cx, cy, w, h, mode, colour_ink, rnd, drips=False):
    """A wide crescent grin: flat-ish top lip, big curved bottom lip, chunky teeth."""
    if mode == "flat":
        draw.line([(cx - w * 0.42, cy), (cx + w * 0.42, cy)], fill=BONE, width=max(3, int(h * 0.22)))
        return
    if mode == "smile":
        w, h = w * 0.80, h * 0.62

    depth_scale = {"open": 1.55, "scream": 2.05}.get(mode, 1.15)
    depth = h * depth_scale
    top = cy - h * 0.18

    steps = 26
    top_edge = []
    bottom_edge = []
    for i in range(steps + 1):
        t = i / steps
        x = cx - w / 2 + w * t
        curve = math.sin(math.pi * t)
        top_edge.append((x, top - curve * h * 0.16))
        bottom_edge.append((x, top + depth * curve))

    poly = top_edge + bottom_edge[::-1]
    draw.polygon([_j(p, rnd, 0.8) for p in poly], fill=BONE)

    # Teeth. Depth of every tooth follows the local mouth depth so nothing
    # spills outside of the grin.
    teeth = 7
    for row, up in ((0, False), (1, True)):
        if mode == "scream" and row == 1:
            continue
        for i in range(teeth):
            t = (i + 0.5) / teeth
            x = cx - w / 2 + w * t
            curve = math.sin(math.pi * t)
            local = depth * curve
            if local < h * 0.22:
                continue
            y0 = top - curve * h * 0.16
            y1 = y0 + local
            half = w / teeth * 0.44
            bite = local * (0.62 if row == 0 else 0.50)
            if row == 0:
                pts = [(x - half, y0 - 2), (x + half, y0 - 2),
                       (x + half * 0.55, y0 + bite), (x - half * 0.55, y0 + bite)]
            else:
                pts = [(x - half * 0.9, y1 + 2), (x + half * 0.9, y1 + 2),
                       (x + half * 0.5, y1 - bite), (x - half * 0.5, y1 - bite)]
            draw.polygon(pts, fill=colour_ink)

    if mode in ("open", "scream"):
        # Gullet + tongue silhouette, keeps the scream from reading as a box.
        gy = top + depth * 0.62
        _blob(draw, cx, gy, w * 0.26, depth * 0.20, (14, 5, 8, 255), rnd, jitter=0.8, points=16)

    # Lip outline.
    draw.line([_j(p, rnd, 0.6) for p in top_edge], fill=colour_ink, width=3)
    draw.line([_j(p, rnd, 0.6) for p in bottom_edge], fill=colour_ink, width=3)

    if drips:
        for _ in range(4):
            t = rnd.uniform(0.2, 0.8)
            x = cx - w / 2 + w * t
            y0 = top + depth * math.sin(math.pi * t)
            length = rnd.uniform(h * 0.8, h * 3.0)
            draw.line([(x, y0), (x + rnd.uniform(-2, 2), y0 + length)], fill=BLOOD, width=3)
            draw.ellipse([x - 3.5, y0 + length - 3.5, x + 3.5, y0 + length + 3.5], fill=BLOOD)


# --------------------------------------------------------------------------- #
# The character
# --------------------------------------------------------------------------- #

def draw_trollge(w=FRAME_W, h=FRAME_H, **pose):
    p = dict(REST_POSE)
    p.update(pose)
    rnd = random.Random(p["seed"])
    ink = p["ink"]

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx = w / 2.0
    lean = p["lean"]

    # ---- skeleton ------------------------------------------------------- #
    hip = (cx, _y(REST["hip"]))
    shoulder = (cx, _y(REST["shoulder"]))
    neck = (cx, _y(REST["neck"]))
    head_c = (cx + p["head_dx"], _y(REST["head"]) + p["head_dy"])

    pivot = (cx, _y(REST["ankle"] - 30))
    hip = _rot(hip, pivot, lean * 0.2)
    shoulder = _rot(shoulder, hip, lean * 0.8)
    neck = _rot(neck, hip, lean * 0.8)
    head_c = _rot(head_c, hip, lean * 0.8)

    leg_w = 26.0
    arm_w = 22.0

    # ---- legs ----------------------------------------------------------- #
    for side, key in ((-1, "leg_l"), (1, "leg_r")):
        hip_deg, knee_deg = p[key]
        hx = hip[0] + side * HIP_X
        knee = _dir((hx, hip[1] - 4), (hx + side * KNEE_X, _y(REST["knee"])), hip_deg)
        ankle = _dir(knee, (knee[0] + side * (FOOT_X - KNEE_X), _y(REST["ankle"])),
                     hip_deg + knee_deg)
        _taper(draw, [(hx, hip[1] - 10), knee, ankle], [leg_w, 17, 13], ink, rnd, p["jitter"])
        # Foot.
        toe = (ankle[0] + side * 16, ankle[1] + 12)
        _taper(draw, [ankle, toe], [14, 8], ink, rnd, p["jitter"])
        draw.ellipse([toe[0] - 11, toe[1] - 7, toe[0] + 11, toe[1] + 7], fill=ink)

    # ---- torso ---------------------------------------------------------- #
    sw = SHOULDER_X * 0.95
    torso = [
        _j((shoulder[0] - sw, shoulder[1] + 4), rnd, p["jitter"]),
        _j((shoulder[0], shoulder[1] - 16), rnd, p["jitter"]),
        _j((shoulder[0] + sw, shoulder[1] + 4), rnd, p["jitter"]),
        _j((hip[0] + HIP_X * 1.25, hip[1] + 4), rnd, p["jitter"]),
        _j((hip[0], hip[1] + 14), rnd, p["jitter"]),
        _j((hip[0] - HIP_X * 1.25, hip[1] + 4), rnd, p["jitter"]),
    ]
    draw.polygon(torso, fill=ink)
    # Neck wedge so the head doesn't float.
    draw.polygon(
        [
            (shoulder[0] - 21, shoulder[1] + 2),
            (shoulder[0] + 21, shoulder[1] + 2),
            (neck[0] + 26, neck[1] - 18),
            (neck[0] - 26, neck[1] - 18),
        ],
        fill=ink,
    )
    # Ribcage scratches.
    for i in range(5):
        yy = shoulder[1] + 30 + i * 17
        draw.line(
            [
                (shoulder[0] - 15 + rnd.uniform(-3, 3), yy),
                (shoulder[0] + 13 + rnd.uniform(-3, 3), yy + rnd.uniform(-5, 5)),
            ],
            fill=DEEP,
            width=2,
        )

    # ---- arms ----------------------------------------------------------- #
    for side, key in ((-1, "arm_l"), (1, "arm_r")):
        sh_deg, el_deg = p[key]
        sx = shoulder[0] + side * SHOULDER_X * 0.85
        sy = shoulder[1] + 8
        elbow = _dir((sx, sy), (sx + side * ELBOW_DX, sy + ELBOW_DY), sh_deg)
        hand = _dir(elbow, (elbow[0] + side * HAND_DX, elbow[1] + HAND_DY), sh_deg + el_deg)
        _taper(draw, [(sx, sy - 8), elbow, hand], [arm_w, 15, 8], ink, rnd, p["jitter"])

        # Hand: scribbled palm + long creepy fingers.
        palm = _blob(draw, hand[0], hand[1] + 3, 12, 10, ink, rnd, jitter=1.0, points=12)
        spread = 30 if p["mouth"] in ("scream", "open") else 20
        for f in range(4):
            a = -0.55 + (f / 3.0) * 1.1
            tip_x = hand[0] + side * math.sin(a + 0.5) * 10
            tip_y = hand[1] + 10 + math.cos(a) * (spread * 0.55)
            draw.line([_j((hand[0], hand[1] + 7), rnd, 1.2), _j((tip_x, tip_y), rnd, 1.8)],
                      fill=ink, width=5)
        _scribble(draw, palm, DEEP, rnd, passes=1, width=1)

    # ---- head ----------------------------------------------------------- #
    hs = p["head_scale"]
    hx_r = HEAD_RX * hs
    hy_r = HEAD_RY * hs

    def hpoint(dx, dy):
        return _rot((head_c[0] + dx, head_c[1] + dy), head_c, p["head_tilt"])

    head_pts = []
    steps = 30
    for i in range(steps):
        a = 2 * math.pi * i / steps
        rr = 1.0 + rnd.uniform(-p["jitter"] * 0.9, p["jitter"] * 0.9) / hx_r
        x = math.cos(a) * hx_r * rr
        y = math.sin(a) * hy_r * rr * (1.0 - 0.13 * math.cos(a))
        head_pts.append(hpoint(x, y))
    draw.polygon(head_pts, fill=ink)

    if p.get("horns"):
        for side in (-1, 1):
            draw.polygon(
                [hpoint(side * hx_r * 0.66, -hy_r * 0.52),
                 hpoint(side * hx_r * 1.40, -hy_r * 1.02),
                 hpoint(side * hx_r * 0.54, -hy_r * 0.96)],
                fill=ink,
            )

    # Slight sheen along the top of the skull (scribble, not shading).
    _scribble(draw, [hpoint(-hx_r * 0.55, -hy_r * 0.72), hpoint(0, -hy_r * 0.95),
                     hpoint(hx_r * 0.5, -hy_r * 0.7)], DEEP, rnd, passes=1, width=2)

    # Eyes + mouth are drawn unrotated around the (already rotated) centre; the
    # tilt is small enough that this reads correctly and keeps the features
    # crisp instead of resampling them.
    eye_cx = head_c[0] + math.sin(math.radians(p["head_tilt"])) * hy_r * 0.3
    eye_cy = head_c[1] + math.cos(math.radians(p["head_tilt"])) * (-hy_r * 0.22)
    _draw_eyes(draw, eye_cx, eye_cy, hx_r * 0.46, hy_r * 0.46, p["eyes"], ink, rnd, veins=p["veins"])

    mouth_cy = head_c[1] + hy_r * 0.18
    _draw_mouth(
        draw,
        head_c[0],
        mouth_cy,
        hx_r * 1.42,
        hy_r * 0.60,
        p["mouth"],
        ink,
        rnd,
        drips=p["drips"],
    )

    # ---- grain ---------------------------------------------------------- #
    if p["static"] > 0:
        noise = Image.effect_noise((w, h), 78).convert("L")
        speck = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        speck.putalpha(ImageChops.multiply(noise.point(lambda v: int(v * p["static"])), img.getchannel("A")))
        img = Image.alpha_composite(img, speck)

    return img


# --------------------------------------------------------------------------- #
# Pose library -- this is the animation set used by the atlases
# --------------------------------------------------------------------------- #

def _p(**kw):
    d = dict(kw)
    return d


POSES = [
    # (animation prefix, pose kwargs)
    ("idle", _p(seed=1)),
    ("idle", _p(seed=2, head_dy=3, lean=-1.5, arm_l=(10, 12), arm_r=(-10, -12))),
    ("singUP", _p(seed=3, head_dy=-14, head_tilt=-4, mouth="open", arm_l=(-46, -16), arm_r=(40, 14))),
    ("singDOWN", _p(seed=4, head_dy=10, head_tilt=6, mouth="grin", arm_l=(28, 22), arm_r=(-26, -20))),
    ("singLEFT", _p(seed=5, lean=-7, head_tilt=9, head_dx=-10, mouth="grin", arm_l=(76, 18), arm_r=(-14, -8))),
    ("singRIGHT", _p(seed=6, lean=7, head_tilt=-9, head_dx=10, mouth="grin", arm_l=(14, 8), arm_r=(-74, -18))),
    ("singUPmiss", _p(seed=7, head_dy=-6, head_tilt=-12, mouth="scream", eyes="scared",
                      arm_l=(-72, -22), arm_r=(66, 20), lean=3)),
    ("singDOWNmiss", _p(seed=8, head_dy=16, head_tilt=14, mouth="scream", eyes="scared",
                        arm_l=(44, 34), arm_r=(-40, -30), lean=-3)),
    ("singLEFTmiss", _p(seed=9, lean=-12, head_dx=-18, head_tilt=16, mouth="scream", eyes="scared",
                        arm_l=(98, 26), arm_r=(-30, -22))),
    ("singRIGHTmiss", _p(seed=10, lean=12, head_dx=18, head_tilt=-16, mouth="scream", eyes="scared",
                         arm_l=(30, 22), arm_r=(-96, -26))),
    ("singUP-alt", _p(seed=11, head_dy=-16, head_tilt=-6, mouth="scream", eyes="wide", veins=True,
                      arm_l=(-58, -20), arm_r=(52, 18), static=0.12)),
    ("singDOWN-alt", _p(seed=12, head_dy=12, head_tilt=8, mouth="scream", eyes="wide", veins=True,
                        arm_l=(34, 26), arm_r=(-32, -24), static=0.12)),
    ("singLEFT-alt", _p(seed=13, lean=-10, head_tilt=11, head_dx=-12, mouth="scream", eyes="wide",
                        veins=True, arm_l=(88, 22), arm_r=(-18, -10), static=0.12)),
    ("singRIGHT-alt", _p(seed=14, lean=10, head_tilt=-11, head_dx=12, mouth="scream", eyes="wide",
                         veins=True, arm_l=(18, 10), arm_r=(-86, -22), static=0.12)),
    ("scared", _p(seed=15, head_dy=-4, head_tilt=-3, mouth="scream", eyes="scared",
                  arm_l=(64, 26), arm_r=(-62, -26), lean=2, static=0.06)),
    ("hey", _p(seed=16, head_tilt=4, mouth="open", arm_l=(-40, -10), arm_r=(38, 10))),
    ("laugh", _p(seed=17, head_tilt=-8, head_dy=-6, mouth="scream", eyes="wide",
                 arm_l=(-26, 30), arm_r=(24, -28), lean=-3)),
    ("laugh", _p(seed=18, head_tilt=8, head_dy=-2, mouth="scream", eyes="wide",
                 arm_l=(30, -26), arm_r=(-28, 26), lean=3)),
    ("attack", _p(seed=19, lean=12, head_tilt=-10, head_dy=-4, mouth="scream", eyes="angry",
                  arm_l=(-84, -12), arm_r=(-78, -10), head_scale=1.06, static=0.1)),
    ("hit", _p(seed=20, lean=-8, head_tilt=12, mouth="open", eyes="dead", static=0.08)),
    ("die", _p(seed=21, lean=-16, head_tilt=22, head_dy=18, mouth="scream", eyes="dead",
               arm_l=(50, 40), arm_r=(-48, -38), static=0.1)),
]

#: The "phase 2" set: same skeleton, bloodshot eyes, drips, horns, static.
SCARY_POSES = [
    ("idle", _p(seed=101, veins=True, drips=True, static=0.06, mouth="grin", eyes="bloodshot", horns=True)),
    ("idle", _p(seed=102, veins=True, drips=True, static=0.08, mouth="open", eyes="bloodshot",
                horns=True, head_dy=3, lean=-2)),
    ("singUP", _p(seed=103, veins=True, drips=True, static=0.07, mouth="scream", eyes="bloodshot",
                  horns=True, head_dy=-16, head_tilt=-6, arm_l=(-52, -18), arm_r=(46, 16))),
    ("singDOWN", _p(seed=104, veins=True, drips=True, static=0.07, mouth="open", eyes="bloodshot",
                    horns=True, head_dy=12, head_tilt=8, arm_l=(30, 24), arm_r=(-28, -22))),
    ("singLEFT", _p(seed=105, veins=True, drips=True, static=0.07, mouth="scream", eyes="bloodshot",
                    horns=True, lean=-8, head_tilt=10, head_dx=-12, arm_l=(80, 20), arm_r=(-16, -10))),
    ("singRIGHT", _p(seed=106, veins=True, drips=True, static=0.07, mouth="scream", eyes="bloodshot",
                     horns=True, lean=8, head_tilt=-10, head_dx=12, arm_l=(16, 10), arm_r=(-78, -20))),
    ("singUPmiss", _p(seed=107, head_dy=-8, head_tilt=-14, mouth="scream", eyes="scared", drips=True,
                      arm_l=(-76, -24), arm_r=(70, 22), static=0.12, veins=True)),
    ("singDOWNmiss", _p(seed=108, head_dy=18, head_tilt=16, mouth="scream", eyes="scared", drips=True,
                        arm_l=(46, 36), arm_r=(-42, -32), static=0.12, veins=True)),
    ("singLEFTmiss", _p(seed=109, lean=-14, head_dx=-20, head_tilt=18, mouth="scream", eyes="scared",
                        drips=True, arm_l=(100, 28), arm_r=(-32, -24), static=0.12, veins=True)),
    ("singRIGHTmiss", _p(seed=110, lean=14, head_dx=20, head_tilt=-18, mouth="scream", eyes="scared",
                         drips=True, arm_l=(32, 24), arm_r=(-98, -28), static=0.12, veins=True)),
    ("scared", _p(seed=111, head_dy=-6, mouth="scream", eyes="scared", arms=None,
                  arm_l=(68, 28), arm_r=(-66, -28), static=0.14, veins=True, drips=True)),
    ("hey", _p(seed=112, head_tilt=6, mouth="scream", eyes="bloodshot", arm_l=(-44, -12), arm_r=(42, 12),
               veins=True, drips=True, static=0.08)),
    ("laugh", _p(seed=113, head_tilt=-10, head_dy=-8, mouth="scream", eyes="bloodshot",
                 arm_l=(-30, 34), arm_r=(28, -32), static=0.1, drips=True, veins=True)),
    ("laugh", _p(seed=114, head_tilt=10, head_dy=-4, mouth="scream", eyes="bloodshot",
                 arm_l=(34, -30), arm_r=(-32, 30), static=0.1, drips=True, veins=True)),
    ("attack", _p(seed=115, lean=14, head_tilt=-12, head_dy=-6, mouth="scream", eyes="angry",
                  arm_l=(-88, -14), arm_r=(-82, -12), head_scale=1.1, static=0.16, drips=True, veins=True)),
    ("hit", _p(seed=116, lean=-10, head_tilt=14, mouth="open", eyes="dead", static=0.12, drips=True)),
    ("die", _p(seed=117, lean=-18, head_tilt=24, head_dy=20, mouth="scream", eyes="dead",
               arm_l=(54, 42), arm_r=(-52, -40), static=0.14, drips=True)),
]


#: Animation prefixes -> short frame-name codes.
#: The codes are deliberately collision-free: Flixel resolves animations with
#: `addByPrefix`, so no used prefix may be a prefix of another frame name
#: (that is why "singUP" is "sUP" and "singUPmiss" is "mUP" instead of
#: "singUP" + "singUPmiss").
ANIM_CODES = {
    "idle": "idle",
    "singUP": "sUP",
    "singDOWN": "sDOWN",
    "singLEFT": "sLEFT",
    "singRIGHT": "sRIGHT",
    "singUPmiss": "mUP",
    "singDOWNmiss": "mDOWN",
    "singLEFTmiss": "mLEFT",
    "singRIGHTmiss": "mRIGHT",
    "singUP-alt": "aUP",
    "singDOWN-alt": "aDOWN",
    "singLEFT-alt": "aLEFT",
    "singRIGHT-alt": "aRIGHT",
    "scared": "scared",
    "hey": "hey",
    "laugh": "laugh",
    "attack": "attack",
    "hit": "hit",
    "die": "die",
}


def frame_name(sheet_name, anim_prefix, index):
    """Sparrow frame name, e.g. `Trollge sUP0000`."""
    return "%s %s%04d" % (sheet_name, ANIM_CODES.get(anim_prefix, anim_prefix), index)


def render_atlas(poses, path_png, path_xml, w=FRAME_W, h=FRAME_H, sheet_name="Trollge",
                 frame_prefix=None):
    """Render a list of poses into a horizontal Sparrow sheet + atlas XML."""
    frames = []
    subtextures = []
    counters = {}
    for prefix, kwargs in poses:
        frames.append(draw_trollge(w, h, **kwargs))
        idx = counters.get(prefix, 0)
        counters[prefix] = idx + 1
        subtextures.append((prefix, idx))

    sheet = Image.new("RGBA", (w * len(frames), h), (0, 0, 0, 0))
    for i, frame in enumerate(frames):
        sheet.alpha_composite(frame, (i * w, 0))
    sheet.save(path_png, optimize=True)

    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<TextureAtlas imagePath="%s">' % sheet_name]
    for i, (prefix, idx) in enumerate(subtextures):
        name = frame_name(frame_prefix or sheet_name, prefix, idx)
        lines.append(
            '\t<SubTexture name="%s" x="%d" y="0" width="%d" height="%d"/>' % (name, i * w, w, h)
        )
    lines.append("</TextureAtlas>")
    with open(path_xml, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return frames, counters
