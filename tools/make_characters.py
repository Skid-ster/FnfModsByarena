#!/usr/bin/env python3
"""
Imports hand-drawn character atlases into the mod.

Drop a Sparrow atlas (`.png` + `.xml`) into `art_src/bf/` (Boyfriend) or
`art_src/trollge/` (Trollge), list it in `SKINS` below, and this tool:

  1. renames every frame to a collision-free code (`BFsmiler sUP0000`,
     `TrollgeFinal mLEFT0000`, ...) so `addByPrefix` can never fold a miss pose
     into a sing animation -- these atlases really do ship `BF NOTE UP` next to
     `BF NOTE UP MISS`,
  2. re-anchors every animation onto a shared ground line, scaled to a shared
     body height, so poses cannot slide, float or grow between animations,
  3. re-packs everything so *all* frames share one frame size -- the character
     XML needs no offsets and every phase of a character sits at the same spot,
  4. fills the gaps: miss poses are graded from the sing poses when the atlas has
     none, a game-over frame is derived from idle, and hey/scared/hit/attack are
     aliased to the closest pose that does exist,
  5. writes `data/characters/<character>.xml` (+ `<character>_dead` for players),
     a 300x150 two-frame health icon, and `docs/<character>.png` for review.

Special extras:
  * the `trollge_final` skin also rebuilds `images/trollge_jump_scare.png` from
    its own face, so the jumpscare is the same character you are fighting,
  * the `trollge` skin also rebuilds the story-menu week art from its idle pose.

Run with:  python3 tools/make_characters.py              (everything)
           python3 tools/make_characters.py trollge      (only Trollge skins)
           python3 tools/make_characters.py bf_blue      (one character)
"""

import math
import os
import re
import sys

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, "mods", "TrollgeMod")
SRC_BF = os.path.join(ROOT, "art_src", "bf")
SRC_TROLLGE = os.path.join(ROOT, "art_src", "trollge")
CHARS = os.path.join(MOD, "data", "characters")
IMAGES = os.path.join(MOD, "images", "characters")
ICONS = os.path.join(MOD, "images", "icons")
DOCS = os.path.join(ROOT, "docs")

# Shared geometry. Every frame of every skin is normalised onto a canvas whose
# bottom is a shared ground line, so one stage position works for everybody and
# swapping characters mid-song cannot make them jump.
PLAYER_GEOM = {
    "canvas": (460, 560),
    "baseline": 539,
    "centre": 229,
    "fit_height": None,        # keep the art at its own size (383 px tall)
}
OPPONENT_GEOM = {
    "canvas": (520, 600),
    "baseline": 560,     # 21 px above the canvas bottom: the camera sits 100 px
                         # above the character midpoint, so a lower ground line
                         # would put his feet under the bottom of the screen
    "centre": 260,
    "fit_height": 520,         # scaled up from 692 px, so he towers over BF
}

ICON_W, ICON_H = 300, 150
SING_DIRS = ("UP", "DOWN", "LEFT", "RIGHT")

#: Engine animations a sing pose can come from, in import order.
SING_ANIMS = [("sing" + d, "Trollge" + d.capitalize()) for d in SING_DIRS]


# --------------------------------------------------------------------------- #
# Skins
#
# anims: (engine anim name, Sparrow prefix in the uploaded atlas, fps, loop)
#   Missing prefixes are derived (miss poses, game-over) or aliased to a pose
#   that exists -- the import prints exactly what it did.
# icon_frames: (engine anim name, frame index) for the two icon states.
# --------------------------------------------------------------------------- #

def bf_skin(**_kw):
    return _kw


SKINS = [
    # ------------------------------------------------------------- Boyfriend
    {
        "song": "trolling",
        "role": "player",
        "source": SRC_BF,
        "files": ("new_blue_boyfriend.png", "new_blue_boyfriend.xml"),
        "short": "BFblue",
        "sprite": "Boyfriend_blue",
        "character": "bf_blue",
        "dead_character": "bf_blue_dead",
        "icon": "bf_blue",
        "color": "#31B0D1",
        "icon_frames": (("idle", 0), ("singUPmiss", 0)),
        "icon_crop": (0.82, 20),
        "derive_miss": True,
        "anims": [
            ("idle", "BF idle dance", 24, True),
            ("singUP", "BF NOTE UP", 24, False),
            ("singDOWN", "BF NOTE DOWN", 24, False),
            ("singLEFT", "BF NOTE LEFT", 24, False),
            ("singRIGHT", "BF NOTE RIGHT", 24, False),
            ("singUPmiss", "BF NOTE UP MISS", 24, False),
            ("singDOWNmiss", "BF NOTE DOWN MISS", 24, False),
            ("singLEFTmiss", "BF NOTE LEFT MISS", 24, False),
            ("singRIGHTmiss", "BF NOTE RIGHT MISS", 24, False),
            ("hey", "BF HEY", 24, False),
            ("scared", "BF NOTE UP MISS", 12, True),
            ("hit", "BF NOTE DOWN", 24, False),
        ],
        "dead": ("Gameover", 24),
    },
    {
        "song": "getting_dark",
        "role": "player",
        "source": SRC_BF,
        "files": ("Smiler_Boyfriend_3.png", "Smiler_Boyfriend_3.xml"),
        "short": "BFsmiler",
        "sprite": "Boyfriend_smiler",
        "character": "bf_smiler",
        "dead_character": "bf_smiler_dead",
        "icon": "bf_smiler",
        "color": "#5C6BC0",
        "icon_frames": (("idle", 0), ("singUPmiss", 0)),
        "icon_crop": (0.82, 20),
        "derive_miss": False,
        "anims": [
            ("idle", "BF idle dance", 24, True),
            ("singUP", "BF NOTE UP", 24, False),
            ("singDOWN", "BF NOTE DOWN", 24, False),
            ("singLEFT", "BF NOTE LEFT", 24, False),
            ("singRIGHT", "BF NOTE RIGHT", 24, False),
            ("singUPmiss", "BF NOTE UP MISS", 24, False),
            ("singDOWNmiss", "BF NOTE DOWN MISS", 24, False),
            ("singLEFTmiss", "BF NOTE LEFT MISS", 24, False),
            ("singRIGHTmiss", "BF NOTE RIGHT MISS", 24, False),
            ("hey", "BF NOTE UP", 24, False),
            ("scared", "BF NOTE UP MISS", 12, True),
            ("hit", "BF NOTE DOWN", 24, False),
        ],
        "dead": ("Gameover", 24),
    },
    {
        "song": "super_scary",
        "role": "player",
        "source": SRC_BF,
        "files": ("Boyfriend_crazy2.png", "Boyfriend_crazy2.xml"),
        "short": "BFscary",
        "sprite": "Boyfriend_super_scary",
        "character": "bf_super_scary",
        "dead_character": "bf_super_scary_dead",
        "icon": "bf_super_scary",
        "color": "#C4101E",
        "icon_frames": (("idle", 0), ("singUPmiss", 0)),
        "icon_crop": (0.82, 20),
        "derive_miss": False,
        "anims": [
            ("idle", "BF idle dance", 24, True),
            ("singUP", "UP", 24, False),
            ("singDOWN", "DOWN", 24, False),
            ("singLEFT", "LEFT", 24, False),
            ("singRIGHT", "RIGHT", 24, False),
            ("singUPmiss", "BF NOTE UP MISS", 24, False),
            ("singDOWNmiss", "BF NOTE DOWN MISS", 24, False),
            ("singLEFTmiss", "BF NOTE LEFT MISS", 24, False),
            ("singRIGHTmiss", "BF NOTE RIGHT MISS", 24, False),
            ("hey", "UP", 24, False),
            ("scared", "BF NOTE UP MISS", 12, True),
            ("hit", "DOWN", 24, False),
        ],
        "dead": ("Gameover", 24),
    },
    {
        # song 3 (6/10) -- the same boy, but he is not rendering correctly
        "song": "dont_look_back",
        "role": "player",
        "source": SRC_BF,
        "files": ("new_blue_boyfriend.png", "new_blue_boyfriend.xml"),
        "short": "BFglitch",
        "sprite": "Boyfriend_glitched",
        "character": "bf_glitched",
        "dead_character": "bf_glitched_dead",
        "icon": "bf_glitched",
        "color": "#2FA86B",
        "icon_frames": (("idle", 0), ("singUPmiss", 0)),
        "icon_crop": (0.82, 20),
        "derive_miss": True,
        "tint": {"hue": -74.0, "sat": 0.72, "contrast": 1.22,
                 "gain": (0.86, 1.16, 0.92), "gamma": 0.92},
        "anims": [
            ("idle", "BF idle dance", 24, True),
            ("singUP", "BF NOTE UP", 24, False),
            ("singDOWN", "BF NOTE DOWN", 24, False),
            ("singLEFT", "BF NOTE LEFT", 24, False),
            ("singRIGHT", "BF NOTE RIGHT", 24, False),
            ("singUPmiss", "BF NOTE UP MISS", 24, False),
            ("singDOWNmiss", "BF NOTE DOWN MISS", 24, False),
            ("singLEFTmiss", "BF NOTE LEFT MISS", 24, False),
            ("singRIGHTmiss", "BF NOTE RIGHT MISS", 24, False),
            ("hey", "BF HEY", 24, False),
            ("scared", "BF NOTE UP MISS", 12, True),
            ("hit", "BF NOTE DOWN", 24, False),
        ],
        "dead": ("Gameover", 24),
    },
    {
        # song 5 (10/10) -- scorched red, all the way down
        "song": "the_incident",
        "role": "player",
        "source": SRC_BF,
        "files": ("Boyfriend_crazy2.png", "Boyfriend_crazy2.xml"),
        "short": "BFdamned",
        "sprite": "Boyfriend_damned",
        "character": "bf_damned",
        "dead_character": "bf_damned_dead",
        "icon": "bf_damned",
        "color": "#7C0A12",
        "icon_frames": (("idle", 0), ("singUPmiss", 0)),
        "icon_crop": (0.82, 20),
        "derive_miss": False,
        "tint": {"hue": -6.0, "sat": 0.58, "contrast": 1.42,
                 "gain": (0.98, 0.66, 0.62), "lift": 0.0, "gamma": 1.18},
        "anims": [
            ("idle", "BF idle dance", 24, True),
            ("singUP", "UP", 24, False),
            ("singDOWN", "DOWN", 24, False),
            ("singLEFT", "LEFT", 24, False),
            ("singRIGHT", "RIGHT", 24, False),
            ("singUPmiss", "BF NOTE UP MISS", 24, False),
            ("singDOWNmiss", "BF NOTE DOWN MISS", 24, False),
            ("singLEFTmiss", "BF NOTE LEFT MISS", 24, False),
            ("singRIGHTmiss", "BF NOTE RIGHT MISS", 24, False),
            ("hey", "UP", 24, False),
            ("scared", "BF NOTE UP MISS", 12, True),
            ("hit", "DOWN", 24, False),
        ],
        "dead": ("Gameover", 24),
    },

    # --------------------------------------------------------------- Trollge
    {
        # song 1 (2/10) -- the "normal" trollge
        "song": "trolling",
        "role": "opponent",
        "source": SRC_TROLLGE,
        "files": ("trollge.png", "trollge.xml"),
        "short": "Trollge1",
        "sprite": "Trollge_phase1",
        "character": "trollge",
        "icon": "trollge",
        "color": "#5B5B66",
        "icon_frames": (("idle", 0), ("singUPmiss", 0)),
        "icon_crop": (0.46, 0),
        "derive_miss": True,
        "storymenu": True,
        "anims": [
            ("idle", "TrollgeIdle", 6, True),
            ("singUP", "TrollgeUp", 24, False),
            ("singDOWN", "TrollgeDown", 24, False),
            ("singLEFT", "TrollgeLeft", 24, False),
            ("singRIGHT", "TrollgeRight", 24, False),
            ("scared", "TrollgeIdle", 10, True),
            ("laugh", "TrollgeIdle", 12, True),
            ("attack", "TrollgeUp", 24, False),
            ("hit", "TrollgeDown", 24, False),
            ("die", "TrollgeDown", 12, False),
        ],
    },
    {
        # song 2 (4/10) -- he is breaking up
        "song": "getting_dark",
        "role": "opponent",
        "source": SRC_TROLLGE,
        "files": ("trollgeGlitch.png", "trollgeGlitch.xml"),
        "short": "TrollgeG",
        "sprite": "Trollge_phase2",
        "character": "trollge_glitch",
        "icon": "trollge_glitch",
        "color": "#8A1023",
        "icon_frames": (("idle", 0), ("singUPmiss", 0)),
        "icon_crop": (0.46, 0),
        "derive_miss": True,
        "anims": [
            ("idle", "TrollgeIdle", 8, True),
            ("singUP", "TrollgeUp", 24, False),
            ("singDOWN", "TrollgeDown", 24, False),
            ("singLEFT", "TrollgeLeft", 24, False),
            ("singRIGHT", "TrollgeRight", 24, False),
            ("scared", "TrollgeIdle", 10, True),
            ("laugh", "TrollgeIdle", 14, True),
            ("attack", "TrollgeUp", 24, False),
            ("hit", "TrollgeDown", 24, False),
            ("die", "TrollgeDown", 12, False),
        ],
    },
    {
        # song 3 (7/10) -- barely holding together
        "song": "super_scary",
        "role": "opponent",
        "source": SRC_TROLLGE,
        "files": ("trollgeStatic1.png", "trollgeStatic1.xml"),
        "short": "TrollgeS",
        "sprite": "Trollge_phase3",
        "character": "trollge_static",
        "icon": "trollge_static",
        "color": "#C4101E",
        "icon_frames": (("idle", 0), ("singUPmiss", 0)),
        "icon_crop": (0.46, 0),
        "derive_miss": True,
        "anims": [
            ("idle", "TrollgeIdle", 10, True),
            ("singUP", "TrollgeUp", 24, False),
            ("singDOWN", "TrollgeDown", 24, False),
            ("singLEFT", "TrollgeLeft", 24, False),
            ("singRIGHT", "TrollgeRight", 24, False),
            ("scared", "TrollgeIdle", 10, True),
            ("laugh", "TrollgeIdle", 16, True),
            ("attack", "TrollgeUp", 24, False),
            ("hit", "TrollgeDown", 24, False),
            ("die", "TrollgeDown", 12, False),
        ],
    },
    {
        # song 3, 60 s -- the red-eyed final form
        "song": "super_scary",
        "role": "opponent",
        "source": SRC_TROLLGE,
        "files": ("TrollgeFinal.png", "TrollgeFinal.xml"),
        "short": "TrollgeF",
        "sprite": "Trollge_final",
        "character": "trollge_final",
        "icon": "trollge_final",
        "color": "#E01B24",
        "icon_frames": (("idle", 0), ("singUPmiss", 0)),
        "icon_crop": (0.46, 0),
        "derive_miss": True,
        "jumpscare": True,
        "anims": [
            ("idle", "TrollgeIdle", 9, True),
            ("singUP", "TrollgeUp", 24, False),
            ("singDOWN", "TrollgeDown", 24, False),
            ("singLEFT", "TrollgeLeft", 24, False),
            ("singRIGHT", "TrollgeRight", 24, False),
            ("scared", "TrollgeIdle", 10, True),
            ("laugh", "TrollgeIdle", 14, True),
            ("attack", "TrollgeUp", 24, False),
            ("hit", "TrollgeDown", 24, False),
            ("die", "TrollgeDown", 12, False),
        ],
    },
    {
        # song 3, 96 s -- he just stands there. one pose. that is the point.
        "song": "super_scary",
        "role": "opponent",
        "source": SRC_TROLLGE,
        "files": ("trollgesad.png", "trollgesad.xml"),
        "short": "TrollgeSad",
        "sprite": "Trollge_sad",
        "character": "trollge_sad",
        "icon": "trollge_sad",
        "color": "#2B3A67",
        "icon_frames": (("idle", 0), ("idle", 0)),
        "icon_crop": (0.46, 0),
        "derive_miss": False,
        "anims": [
            ("idle", "IncidentSad", 6, True),
            ("singUP", "IncidentSad", 24, False),
            ("singDOWN", "IncidentSad", 24, False),
            ("singLEFT", "IncidentSad", 24, False),
            ("singRIGHT", "IncidentSad", 24, False),
            ("scared", "IncidentSad", 8, True),
            ("laugh", "IncidentSad", 8, True),
            ("attack", "IncidentSad", 24, False),
            ("hit", "IncidentSad", 24, False),
            ("die", "IncidentSad", 12, False),
        ],
    },
]


# --------------------------------------------------------------------------- #
# Naming
# --------------------------------------------------------------------------- #

def anim_code(engine_name):
    """singUP -> sUP, singLEFTmiss -> mLEFT, idle -> idle, hey -> hey."""
    if engine_name == "idle":
        return "idle"
    if engine_name.startswith("sing") and engine_name.endswith("miss"):
        return "m" + engine_name[4:-4]
    if engine_name.startswith("sing"):
        return "s" + engine_name[4:]
    return engine_name


# --------------------------------------------------------------------------- #
# Atlas reading
# --------------------------------------------------------------------------- #

def read_atlas(png_path, xml_path):
    """-> {frame name: composed RGBA frame (its own frame size)}"""
    sheet = Image.open(png_path).convert("RGBA")
    text = open(xml_path, encoding="utf-8", errors="replace").read()

    frames = {}
    for raw in re.findall(r"<SubTexture ([^/>]+)/?>", text):
        d = dict(re.findall(r'(\w+)="([^"]*)"', raw))
        x, y = int(d["x"]), int(d["y"])
        w, h = int(d["width"]), int(d["height"])
        region = sheet.crop((x, y, x + w, y + h))

        # Adobe Animate packs some cells rotated 90 degrees clockwise and marks
        # them rotated="true" (BF NOTE UP0001, every TrollgeRight frame...).
        # Ignoring the flag ships those poses lying on their side.
        if (d.get("rotated") or "").lower() == "true":
            region = region.rotate(90, expand=True)
            w, h = region.width, region.height

        fw = int(d.get("frameWidth", w))
        fh = int(d.get("frameHeight", h))
        fx = int(d.get("frameX", 0))
        fy = int(d.get("frameY", 0))
        canvas = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
        canvas.paste(region, (-fx, -fy))
        frames[d["name"]] = canvas
    return frames


def tint_frames(frames, spec):
    """Re-colour a whole uploaded atlas, so a song can have its own cast without
    a new upload.

    spec keys (all optional): hue (degrees), sat, contrast, gain=(r,g,b),
    lift (0..1), gamma. Applied in linear RGB with the alpha channel untouched.
    """
    hue = math.radians(spec.get("hue", 0.0))
    sat = spec.get("sat", 1.0)
    contrast = spec.get("contrast", 1.0)
    gain = np.array(spec.get("gain", (1.0, 1.0, 1.0)), dtype=np.float64)
    lift = spec.get("lift", 0.0)
    gamma = spec.get("gamma", 1.0)

    cos_a, sin_a = math.cos(hue), math.sin(hue)
    rot = np.array([
        [0.213 + cos_a * 0.787 - sin_a * 0.213,
         0.715 - cos_a * 0.715 - sin_a * 0.715,
         0.072 - cos_a * 0.072 + sin_a * 0.928],
        [0.213 - cos_a * 0.213 + sin_a * 0.143,
         0.715 + cos_a * 0.285 + sin_a * 0.140,
         0.072 - cos_a * 0.072 - sin_a * 0.283],
        [0.213 - cos_a * 0.213 - sin_a * 0.787,
         0.715 - cos_a * 0.715 + sin_a * 0.715,
         0.072 + cos_a * 0.928 + sin_a * 0.072],
    ])
    lum = np.array([0.2126, 0.7152, 0.0722])
    sat_m = np.array([[lum[0] + sat * (1 - lum[0]), lum[1] * (1 - sat), lum[2] * (1 - sat)],
                      [lum[0] * (1 - sat), lum[1] + sat * (1 - lum[1]), lum[2] * (1 - sat)],
                      [lum[0] * (1 - sat), lum[1] * (1 - sat), lum[2] + sat * (1 - lum[2])]])
    matrix = rot @ sat_m

    out = {}
    for name, image in frames.items():
        arr = np.asarray(image, dtype=np.float64) / 255.0
        rgb = arr[:, :, :3]
        rgb = (rgb - 0.5) * contrast + 0.5
        rgb = rgb.reshape(-1, 3) @ matrix.T
        rgb = rgb * gain + lift
        rgb = np.clip(rgb, 0.0, 1.0) ** gamma
        arr[:, :, :3] = rgb.reshape(arr.shape[0], arr.shape[1], 3)
        out[name] = Image.fromarray((np.clip(arr, 0.0, 1.0) * 255.0).astype(np.uint8), "RGBA")
    return out


def group_anims(frames):
    """Sparrow names -> {prefix: [names in numeric order]}"""
    groups = {}
    for name in frames:
        m = re.match(r"^(.*?)(\d+)$", name)
        prefix, index = (m.group(1), int(m.group(2))) if m else (name, 0)
        groups.setdefault(prefix, []).append((index, name))
    return {p: [n for _, n in sorted(v)] for p, v in groups.items()}


def art_box(image):
    box = image.getchannel("A").getbbox()
    if box is None:
        return None
    return box


# --------------------------------------------------------------------------- #
# Grading (used when the upload has no miss / death art)
# --------------------------------------------------------------------------- #

def grade_miss(image):
    """Desaturated, darkened, blood-tinted version of a pose."""
    rgb = image.convert("RGB")
    grey = ImageEnhance.Color(rgb).enhance(0.30)
    grey = ImageEnhance.Brightness(grey).enhance(0.78)
    red = Image.new("RGB", image.size, (168, 8, 26))
    hurt = Image.blend(grey, red, 0.34)
    out = hurt.convert("RGBA")
    out.putalpha(image.getchannel("A"))
    return out


def grade_dead(image):
    """Near-black silhouette with a red cast, for the game-over screen."""
    rgb = image.convert("RGB")
    dark = ImageEnhance.Color(rgb).enhance(0.10)
    dark = ImageEnhance.Brightness(dark).enhance(0.42)
    red = Image.new("RGB", image.size, (90, 0, 8))
    out = Image.blend(dark, red, 0.28).convert("RGBA")
    out.putalpha(image.getchannel("A"))
    return out


# --------------------------------------------------------------------------- #
# Normalisation
# --------------------------------------------------------------------------- #

def scale_for(skin, groups, frames):
    """Uniform scale so the tallest pose matches the skin's fit height."""
    geom = PLAYER_GEOM if skin["role"] == "player" else OPPONENT_GEOM
    geom = dict(geom, **skin.get("geom", {}))
    fit = geom.get("fit_height")
    if not fit:
        return 1.0, geom
    tallest = 0
    for names in groups.values():
        for name in names:
            box = art_box(frames[name])
            if box:
                tallest = max(tallest, box[3] - box[1])
    if tallest == 0:
        return 1.0, geom
    return fit / float(tallest), geom


def normalise(skin, frames, groups, scale, geom):
    """Re-anchor + rescale every prefix. -> {prefix: [names in numeric order]}"""
    cw, ch = geom["canvas"]
    baseline, centre = geom["baseline"], geom["centre"]
    return cw, ch, baseline, centre, scale


def build_frames(skin, frames, groups):
    """-> ([(new frame name, image)], {engine anim: prefix})"""
    scale, geom = scale_for(skin, groups, frames)
    cw, ch = geom["canvas"]
    baseline, centre = geom["baseline"], geom["centre"]

    built = []
    anim_prefix = {}
    by_engine = {}
    seen = {}

    mirrors = skin.get("mirror") or {}
    planned = []
    for engine_name, prefix, _fps, _loop in skin["anims"]:
        if prefix not in groups:
            continue
        if engine_name in mirrors:
            continue        # rebuilt from another animation below
        if prefix in seen:
            anim_prefix[engine_name] = seen[prefix]
            continue
        new_prefix = "%s %s" % (skin["short"], anim_code(engine_name))
        seen[prefix] = new_prefix
        anim_prefix[engine_name] = new_prefix
        planned.append((prefix, new_prefix))

    for prefix, new_prefix in planned:
        names = groups[prefix]
        first = art_box(frames[names[0]])
        if first is None:
            continue
        foot = first[3] * scale
        mid = (first[0] + first[2]) / 2.0 * scale
        dx = centre - mid
        dy = baseline - foot
        made = []
        for i, name in enumerate(names):
            src = frames[name]
            if scale != 1.0:
                src = src.resize((max(1, int(src.width * scale)),
                                  max(1, int(src.height * scale))), Image.LANCZOS)
            target = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            target.alpha_composite(src, (int(round(dx)), int(round(dy))))
            out_name = "%s%04d" % (new_prefix, i)
            built.append((out_name, target))
            made.append(out_name)
        for engine_name, pfx, _fps, _loop in skin["anims"]:
            if pfx == prefix:
                by_engine[engine_name] = made

    built_map = dict(built)

    # --- animations whose uploaded frames are unusable --------------------
    # (the Trollge's right-sing cells contain a sprawled, upside-down figure,
    # if the source has no pose for that direction at all
    for target, source in mirrors.items():
        frames_in = by_engine.get(source) or []
        if not frames_in:
            continue
        new_prefix = "%s %s" % (skin["short"], anim_code(target))
        made = []
        for i, name in enumerate(frames_in):
            out_name = "%s%04d" % (new_prefix, i)
            built.append((out_name, mirror_frame(built_map[name], baseline, centre)))
            made.append(out_name)
        built_map = dict(built)
        by_engine[target] = made
        anim_prefix[target] = new_prefix
        print("     ! %s rebuilt by mirroring %s (no source frames for it)"
              % (target, source))

    # --- miss poses the upload does not have ------------------------------
    for direction in SING_DIRS:
        engine_name = "sing" + direction + "miss"
        if engine_name in by_engine or not skin.get("derive_miss"):
            continue
        source = by_engine.get("sing" + direction)
        if not source:
            continue
        new_prefix = "%s m%s" % (skin["short"], direction)
        made = []
        for i, new_name in enumerate(source):
            out_name = "%s%04d" % (new_prefix, i)
            built.append((out_name, grade_miss(built_map[new_name])))
            made.append(out_name)
        built_map = dict(built)
        by_engine[engine_name] = made
        anim_prefix[engine_name] = new_prefix
        print("     + derived %s from sing%s" % (engine_name, direction))

    # --- anything else the upload does not have --------------------------
    fallbacks = [
        ("hey", ["singUP", "idle"]),
        ("scared", ["singUPmiss", "singUP", "idle"]),
        ("hit", ["singDOWNmiss", "singDOWN", "idle"]),
        ("laugh", ["idle"]),
        ("pre-attack", ["singRIGHT", "idle"]),
        ("attack", ["singLEFT", "idle"]),
        ("dodge", ["singDOWN", "idle"]),
        ("die", ["idle"]),
    ]
    for engine_name, sources in fallbacks:
        if engine_name in by_engine:
            continue
        for source in sources:
            if source in by_engine:
                by_engine[engine_name] = by_engine[source]
                anim_prefix[engine_name] = anim_prefix[source]
                print("     = %s aliased to %s" % (engine_name, source))
                break

    # --- death frame ------------------------------------------------------
    skin["_dead_prefix"] = "%s die" % skin["short"]
    dead_prefix = skin["dead"][0] if skin.get("dead") else None
    if dead_prefix and dead_prefix in groups:
        names = groups[dead_prefix]
        box = art_box(frames[names[0]])
        dx = centre - (box[0] + box[2]) / 2.0 * scale
        dy = baseline - box[3] * scale
        for i, name in enumerate(names):
            src = frames[name]
            if scale != 1.0:
                src = src.resize((max(1, int(src.width * scale)),
                                  max(1, int(src.height * scale))), Image.LANCZOS)
            target = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            target.alpha_composite(src, (int(round(dx)), int(round(dy))))
            built.append(("%s%04d" % (skin["_dead_prefix"], i), target))
        print("     + game-over art taken from %r" % dead_prefix)
    else:
        idle = by_engine.get("idle") or []
        if idle:
            built.append(("%s0000" % skin["_dead_prefix"], grade_dead(built_map[idle[0]])))
            print("     + game-over frame derived from idle")

    return built, anim_prefix, by_engine


def mirror_frame(image, baseline, centre):
    """Horizontal mirror, re-anchored on the shared ground line."""
    flipped = image.transpose(Image.FLIP_LEFT_RIGHT)
    box = art_box(flipped)
    if box is None:
        return flipped
    target = Image.new("RGBA", image.size, (0, 0, 0, 0))
    target.alpha_composite(flipped, (int(round(centre - (box[0] + box[2]) / 2.0)),
                                     int(round(baseline - box[3]))))
    return target


def pack(frames, sprite, dest_dir):
    """Shelf-pack the normalised frames into one PNG + Sparrow XML."""
    entries = []
    for name, image in frames:
        box = art_box(image)
        if box is None:
            continue
        entries.append((name, image.crop(box), box, image.size))

    max_w = 2048
    x = y = row_h = 0
    placed = []
    for name, crop, box, size in entries:
        if x + crop.width > max_w:
            x, y, row_h = 0, y + row_h, 0
        placed.append((name, crop, box, size, x, y))
        x += crop.width
        row_h = max(row_h, crop.height)

    total_w = max(p[4] + p[1].width for p in placed)
    total_h = y + row_h
    sheet = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    for _n, crop, _b, _s, px, py in placed:
        sheet.paste(crop, (px, py))

    png_path = os.path.join(dest_dir, sprite + ".png")
    sheet.save(png_path, optimize=True)

    lines = [
        "<?xml version='1.0' encoding='utf-8'?>",
        '<TextureAtlas imagePath="%s.png">' % sprite,
    ]
    for name, crop, box, size, px, py in placed:
        lines.append(
            '    <SubTexture name="%s" x="%d" y="%d" width="%d" height="%d" '
            'frameX="%d" frameY="%d" frameWidth="%d" frameHeight="%d"/>'
            % (name, px, py, crop.width, crop.height,
               -box[0], -box[1], size[0], size[1])
        )
    lines.append("</TextureAtlas>")
    open(os.path.join(dest_dir, sprite + ".xml"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    return png_path, len(placed)


# --------------------------------------------------------------------------- #
# Icons, previews, extra art
# --------------------------------------------------------------------------- #

def head_icon(image, frac=0.82, dx=20):
    """Bust crop of a normalised frame, 150x150."""
    box = art_box(image)
    art_h = box[3] - box[1]
    size = max(1, int(art_h * frac))
    cx = (box[0] + box[2]) // 2 + dx
    top = box[1]
    tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    tile.paste(image.crop((cx - size // 2, top, cx + size // 2, top + size)), (0, 0))
    return tile.resize((150, 150), Image.LANCZOS)


def build_icon(skin, built_map, by_engine):
    tiles = []
    for engine_name, index in skin["icon_frames"]:
        names = by_engine.get(engine_name) or []
        if not names:
            continue
        tiles.append(head_icon(built_map[names[min(index, len(names) - 1)]],
                               *skin.get("icon_crop", (0.82, 20))))
    if not tiles:
        return None
    icon = Image.new("RGBA", (ICON_W, ICON_H), (0, 0, 0, 0))
    for i, tile in enumerate(tiles[:2]):
        icon.alpha_composite(tile, (i * 150, 0))
    out_dir = os.path.join(ICONS, skin["icon"])
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "icon.png")
    icon.save(path, optimize=True)
    return path


def build_preview(built_map, by_engine, skin):
    """docs/<character>.png -- pose strip for the README / pull requests."""
    picks = []
    for engine_name, index in (("idle", 1), ("singUP", 0), ("singLEFT", 0),
                               ("singRIGHT", 0), ("singDOWN", 0), ("singUPmiss", 0)):
        names = by_engine.get(engine_name) or []
        if names:
            picks.append(built_map[names[min(index, len(names) - 1)]])
    if not picks:
        return None
    canvas_w, canvas_h = picks[0].size
    scale = 0.42
    tw, th = int(canvas_w * scale), int(canvas_h * scale)
    strip = Image.new("RGBA", (tw * len(picks), th), (18, 14, 18, 255))
    for i, frame in enumerate(picks):
        strip.alpha_composite(frame.resize((tw, th), Image.LANCZOS), (i * tw, 0))
    os.makedirs(DOCS, exist_ok=True)
    path = os.path.join(DOCS, skin["character"] + ".png")
    strip.convert("RGB").save(path, optimize=True)
    return path


def build_jumpscare(skin, built_map, by_engine):
    """Full-screen scream still built from this skin's own face."""
    names = by_engine.get("idle") or []
    if not names:
        return None
    frame = built_map[names[0]]
    box = art_box(frame)
    head_h = int((box[3] - box[1]) * 0.34)
    region = frame.crop((box[0], box[1], box[2], box[1] + head_h))

    # isolate the white face mask: it is the only bright thing in the top of the
    # sprite, so this centres the scare on the face instead of on his shoulders
    grey = np.array(region.convert("L"))
    ys, xs = np.nonzero(grey > 150)
    if len(xs) > 200:
        pad = int((xs.max() - xs.min()) * 0.12)
        fx0, fy0 = max(0, xs.min() - pad), max(0, ys.min() - pad)
        fx1, fy1 = min(region.width, xs.max() + pad), min(region.height, ys.max() + pad)
        region = region.crop((fx0, fy0, fx1, fy1))
    head = region.crop(region.getchannel("A").getbbox())

    target_w, target_h = 1280, 720
    scale = max(target_w / head.width, target_h / head.height)
    big = head.resize((int(head.width * scale), int(head.height * scale)), Image.LANCZOS)
    left = (big.width - target_w) // 2
    top = (big.height - target_h) // 2
    big = big.crop((left, top, left + target_w, top + target_h))

    # colour split + red bleed + grain, same language as the backdrops
    r, g, b, a = big.split()
    shifted = Image.merge("RGBA", (r, g, b, a))
    split = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    split.alpha_composite(shifted, (0, 0))
    split.alpha_composite(Image.merge("RGBA", (r, g, b, a.point(lambda v: int(v * 0.55)))),
                          (10, 0))
    grade = ImageEnhance.Color(split.convert("RGB")).enhance(0.55)
    grade = Image.blend(grade, Image.new("RGB", (target_w, target_h), (110, 4, 10)), 0.18)
    out = grade.convert("RGBA")
    out.putalpha(big.getchannel("A"))

    vignette = Image.new("L", (target_w, target_h), 0)
    from PIL import ImageDraw
    d = ImageDraw.Draw(vignette)
    d.ellipse((-220, -220, target_w + 220, target_h + 220), fill=255)
    vignette = vignette.filter(ImageFilter.GaussianBlur(140))
    dark = Image.new("RGBA", (target_w, target_h), (8, 0, 2, 255))
    dark.putalpha(vignette.point(lambda v: 255 - v))
    out.alpha_composite(dark)

    path = os.path.join(MOD, "images", "trollge_jump_scare.png")
    out.convert("RGB").save(path, optimize=True)
    return path


def build_storymenu(skin, built_map, by_engine):
    """Story-menu week art (248x460) from this skin's idle pose."""
    names = by_engine.get("idle") or []
    if not names:
        return None
    frame = built_map[names[0]]
    box = art_box(frame)
    art = frame.crop(box)
    target_h = 460
    scale = target_h / art.height
    art = art.resize((max(1, int(art.width * scale)), target_h), Image.LANCZOS)
    canvas = Image.new("RGBA", (248, 460), (0, 0, 0, 0))
    canvas.alpha_composite(art, ((248 - art.width) // 2, 0))
    path = os.path.join(MOD, "images", "menus", "storymenu", "characters", "trollge.png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    canvas.save(path, optimize=True)
    return path


# --------------------------------------------------------------------------- #
# Character XML
# --------------------------------------------------------------------------- #

def character_xml(skin, anims, dead=False):
    if skin["role"] == "player":
        attrs = 'flipX="true" isPlayer="true"'
        if not dead:
            attrs += ' gameOverChar="%s"' % skin["dead_character"]
    else:
        attrs = 'flipX="false" isPlayer="false" holdTime="6"'

    head = [
        "<!DOCTYPE codename-engine-character>",
        '<character sprite="%s" icon="%s" color="%s" %s>'
        % (skin["sprite"], skin["icon"], skin["color"], attrs),
    ]
    body = [
        '    <anim name="%s" anim="%s" x="0" y="0" fps="%d" loop="%s"/>'
        % (name, prefix, fps, "true" if loop else "false")
        for name, prefix, fps, loop in anims
    ]
    return "\n".join(head + body + ["</character>", ""])


def build_skin(skin):
    png_src, xml_src = skin["files"]
    frames = read_atlas(os.path.join(skin["source"], png_src),
                        os.path.join(skin["source"], xml_src))
    if skin.get("tint"):
        frames = tint_frames(frames, skin["tint"])
    groups = group_anims(frames)

    built, anim_prefix, by_engine = build_frames(skin, frames, groups)
    built_map = dict(built)
    scale, geom = scale_for(skin, groups, frames)
    print("     geometry %dx%d @ baseline %d (scale %.2f)"
          % (geom["canvas"][0], geom["canvas"][1], geom["baseline"], scale))

    os.makedirs(IMAGES, exist_ok=True)
    png_path, count = pack(built, skin["sprite"], IMAGES)
    print("  -> %s (%d frames, %d anims)"
          % (os.path.relpath(png_path, ROOT), count, len(by_engine)))

    os.makedirs(CHARS, exist_ok=True)
    anims = [(name, anim_prefix[name], fps, loop)
             for name, _prefix, fps, loop in skin["anims"] if name in anim_prefix]
    char_path = os.path.join(CHARS, skin["character"] + ".xml")
    open(char_path, "w", encoding="utf-8").write(character_xml(skin, anims))
    print("  -> %s" % os.path.relpath(char_path, ROOT))

    if skin["role"] == "player":
        dead_anims = [
            ("firstDeath", skin["_dead_prefix"], skin["dead"][1], False),
            ("deathLoop", skin["_dead_prefix"], skin["dead"][1], True),
            ("deathConfirm", skin["_dead_prefix"], skin["dead"][1], False),
        ]
        dead_path = os.path.join(CHARS, skin["dead_character"] + ".xml")
        open(dead_path, "w", encoding="utf-8").write(character_xml(skin, dead_anims, dead=True))
        print("  -> %s" % os.path.relpath(dead_path, ROOT))

    preview = build_preview(built_map, by_engine, skin)
    if preview:
        print("  -> %s" % os.path.relpath(preview, ROOT))

    icon = build_icon(skin, built_map, by_engine)
    if icon:
        print("  -> %s" % os.path.relpath(icon, ROOT))

    if skin.get("jumpscare"):
        path = build_jumpscare(skin, built_map, by_engine)
        if path:
            print("  -> %s" % os.path.relpath(path, ROOT))

    if skin.get("storymenu"):
        path = build_storymenu(skin, built_map, by_engine)
        if path:
            print("  -> %s" % os.path.relpath(path, ROOT))


def build_cast(skins):
    """docs/cast.png -- every character in the mod, one strip each."""
    strips = []
    for skin in skins:
        path = os.path.join(DOCS, skin["character"] + ".png")
        if os.path.isfile(path):
            strips.append(Image.open(path).convert("RGB"))
    if not strips:
        return None
    w = max(s.width for s in strips)
    h = sum(s.height for s in strips)
    out = Image.new("RGB", (w, h), (18, 14, 18))
    y = 0
    for strip in strips:
        out.paste(strip, (0, y))
        y += strip.height
    os.makedirs(DOCS, exist_ok=True)
    path = os.path.join(DOCS, "cast.png")
    out.save(path, optimize=True)
    return path


def main(argv):
    wanted = [a for a in argv[1:] if not a.startswith("-")]
    skins = [s for s in SKINS
             if not wanted or s["song"] in wanted or s["character"] in wanted]
    if not skins:
        print("No matching skin. Known characters: "
              + ", ".join(s["character"] for s in SKINS))
        return 1
    for skin in skins:
        print("Importing %s (%s, %s)..." % (skin["character"], skin["sprite"], skin["role"]))
        build_skin(skin)
    if not wanted:
        cast = build_cast(SKINS)
        if cast:
            print("  -> %s" % os.path.relpath(cast, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
