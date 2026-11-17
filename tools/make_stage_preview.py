#!/usr/bin/env python3
"""Renders the stage the way the engine frames it, so positioning is verifiable.

It re-implements three things from Codename Engine / HaxeFlixel:

* character art placement -- a Sparrow frame is drawn at
  ``char.x + frame.offset`` where ``offset = -frameX`` (FlxAtlasFrames.fromSparrow),
  inside a canvas of ``frameWidth x frameHeight``;
* the camera target -- ``PlayState.getCharactersCamPos`` averages
  ``Character.__getCameraPositionInto`` over the strumline's characters, which is
  ``midpoint + (isPlayer ? -100 : 150) + cameraOffset``;
* the camera projection -- ``FlxCamera`` scales the world around the camera
  centre: ``screen = (world - scroll) * zoom + size * (1 - zoom) / 2``.

Output: docs/stage.png -- one tile per camera side, with the ground line and the
safe frame drawn in. Exits non-zero when a character is clipped, when the two
characters do not share a ground line, or when the backdrop does not cover what
the camera can see.

Run with:  python3 tools/make_stage_preview.py
"""

import os
import re
import sys
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, "mods", "TrollgeMod")
DOCS = os.path.join(ROOT, "docs")

STAGE_XML = os.path.join(MOD, "data", "stages", "trollge.xml")
IMG_CHARS = os.path.join(MOD, "images", "characters")
IMG_STAGES = os.path.join(MOD, "images", "stages", "trollge")
CHARS_XML = os.path.join(MOD, "data", "characters")

SCREEN_W, SCREEN_H = 1280, 720

#: Minimum clear space (px, at 1.0 zoom) between a character's art and the edge
#: of the visible area while the camera sits on either side. Camera shake moves
#: the frame by up to ~3 % of the width, so this is not just cosmetic.
MIN_MARGIN = 45

#: Both pairs of feet must sit within this many pixels of each other.
GROUND_TOLERANCE = 2

#: Covers the maximum tier base zoom (1.026) plus this stage's capped 0.018
#: impulse with a little headroom. External chart/engine zooms can exceed it.
MAX_TIER_ZOOM = 1.05


def read_stage():
    root = ET.parse(STAGE_XML).getroot()
    stage = {
        "zoom": float(root.get("zoom", 1.0)),
        "startCamX": float(root.get("startCamPosX", SCREEN_W / 2)),
        "startCamY": float(root.get("startCamPosY", SCREEN_H / 2)),
        "bg": None,
        "shadows": [],
        "chars": {},
    }
    for node in root:
        if node.tag == "sprite" and node.get("name") == "bg":
            stage["bg"] = {
                "x": float(node.get("x", 0)),
                "y": float(node.get("y", 0)),
                "scale": float(node.get("scale", 1.0)),
                "file": node.get("sprite", "bg"),
            }
        elif node.tag == "sprite" and node.get("sprite") == "contact_shadow":
            stage["shadows"].append({"x": float(node.get("x", 0)),
                                     "y": float(node.get("y", 0))})
        elif node.tag in ("dad", "opponent", "boyfriend", "bf"):
            key = "opponent" if node.tag in ("dad", "opponent") else "player"
            stage["chars"][key] = {
                "x": float(node.get("x", 100)),
                "y": float(node.get("y", 100)),
                "camxoffset": float(node.get("camxoffset", 0)),
                "camyoffset": float(node.get("camyoffset", 0)),
            }
    return stage


def read_character(character):
    """-> ({engine anim: [prefix, ...]}, atlas frames {name: dict})."""
    root = ET.parse(os.path.join(CHARS_XML, character + ".xml")).getroot()
    sprite = root.get("sprite")
    anims = {}
    for node in root.iter("anim"):
        # <anim name="idle" anim="Trollge1 idle"/> -- name is the engine anim,
        # anim is the Sparrow prefix the frames are packed under.
        anims.setdefault(node.get("name"), node.get("anim"))

    text = open(os.path.join(IMG_CHARS, sprite + ".xml"), encoding="utf-8").read()
    frames = {}
    for raw in re.findall(r"<SubTexture ([^/>]+)/?>", text):
        frames[re.search(r'name="([^"]*)"', raw).group(1)] = dict(
            re.findall(r'(\w+)="([^"]*)"', raw))
    return sprite, anims, frames


def draw_char(canvas, draw, char, char_xml, cam, flip, tint):
    """Composite one idle frame onto ``canvas`` through the camera."""
    sprite, anims, frames = read_character(char_xml)
    prefix = anims.get("idle") or next(iter(anims.values()))
    frame = frames[prefix + "0000"]

    fw, fh = int(frame["frameWidth"]), int(frame["frameHeight"])
    # FlxAtlasFrames.fromSparrow: offset = -frameX / -frameY.
    art = Image.open(os.path.join(IMG_CHARS, sprite + ".png")).convert("RGBA")
    box = (int(frame["x"]), int(frame["y"]),
           int(frame["x"]) + int(frame["width"]), int(frame["y"]) + int(frame["height"]))
    art = art.crop(box)
    if flip:
        art = art.transpose(Image.FLIP_LEFT_RIGHT)
    if tint:
        art = Image.blend(art, Image.new("RGBA", art.size, tint + (255,)), 0.0)

    off_x, off_y = -int(frame["frameX"]), -int(frame["frameY"])
    if flip:
        # A flipped frame mirrors inside the frame box.
        off_x = fw - off_x - art.width

    world_x = char["x"] + off_x
    world_y = char["y"] + off_y
    zoom = cam["zoom"]
    sx = (world_x - cam["scrollX"]) * zoom + SCREEN_W * (1 - zoom) / 2.0
    sy = (world_y - cam["scrollY"]) * zoom + SCREEN_H * (1 - zoom) / 2.0

    if zoom != 1.0:
        art = art.resize((max(1, int(art.width * zoom)), max(1, int(art.height * zoom))),
                         Image.LANCZOS)
    canvas.alpha_composite(art, (int(round(sx)), int(round(sy))))

    return {
        "left": sx, "top": sy, "right": sx + art.width, "bottom": sy + art.height,
        "feet": sy + art.height,
        "frameW": fw, "frameH": fh,
    }


def camera_for(stage, side):
    """-> dict(scrollX, scrollY, zoom, target) for a strumline's camera target."""
    char = stage["chars"][side]
    is_player = side == "player"
    # Character.__getCameraPositionInto: midpoint + side offset + cameraOffset.
    cw = stage["chars"][side]["frameW"]
    ch = stage["chars"][side]["frameH"]
    target_x = char["x"] + cw / 2.0 + (-100 if is_player else 150) + char["camxoffset"]
    target_y = char["y"] + ch / 2.0 - 100 + char["camyoffset"]
    return {
        "zoom": stage["zoom"],
        "scrollX": target_x - SCREEN_W / 2.0,
        "scrollY": target_y - SCREEN_H / 2.0,
        "target": (target_x, target_y),
    }


def main():
    stage = read_stage()
    problems = []

    # Frame size comes from the atlas, so it has to be read before the camera.
    for side in ("opponent", "player"):
        char_xml = "trollge" if side == "opponent" else "bf_blue"
        _sprite, _anims, frames = read_character(char_xml)
        first = frames[next(iter(frames))]
        stage["chars"][side]["frameW"] = int(first["frameWidth"])
        stage["chars"][side]["frameH"] = int(first["frameHeight"])

    tiles = []
    for side in ("opponent", "player"):
        cam = camera_for(stage, side)
        tile = Image.new("RGBA", (SCREEN_W, SCREEN_H), (8, 6, 8, 255))

        bg = stage["bg"]
        if bg:
            img = Image.open(os.path.join(IMG_STAGES, bg["file"] + ".png")).convert("RGBA")
            w = int(img.width * bg["scale"] * cam["zoom"])
            h = int(img.height * bg["scale"] * cam["zoom"])
            img = img.resize((w, h), Image.LANCZOS)
            bx = (bg["x"] - cam["scrollX"]) * cam["zoom"] + SCREEN_W * (1 - cam["zoom"]) / 2.0
            by = (bg["y"] - cam["scrollY"]) * cam["zoom"] + SCREEN_H * (1 - cam["zoom"]) / 2.0
            tile.alpha_composite(img, (int(round(bx)), int(round(by))))

        # XML places these after the background and before the characters.
        shadow = Image.open(os.path.join(IMG_STAGES, "contact_shadow.png")).convert("RGBA")
        shadow = shadow.resize((round(shadow.width * cam["zoom"]),
                                round(shadow.height * cam["zoom"])), Image.Resampling.LANCZOS)
        for pos in stage["shadows"]:
            sx = (pos["x"] - cam["scrollX"]) * cam["zoom"] + SCREEN_W * (1 - cam["zoom"]) / 2
            sy = (pos["y"] - cam["scrollY"]) * cam["zoom"] + SCREEN_H * (1 - cam["zoom"]) / 2
            tile.alpha_composite(shadow, (round(sx), round(sy)))

        boxes = {}
        for key, xml in (("opponent", "trollge"), ("player", "bf_blue")):
            boxes[key] = draw_char(tile, None, stage["chars"][key], xml, cam,
                                   flip=(key == "player"), tint=None)
        feet = {k: b["feet"] for k, b in boxes.items()}

        draw = ImageDraw.Draw(tile)
        for box in boxes.values():
            draw.rectangle([box["left"], box["top"], box["right"], box["bottom"]],
                           outline=(0, 255, 160, 200))
        draw.line([0, (feet["opponent"] + feet["player"]) / 2.0, SCREEN_W,
                   (feet["opponent"] + feet["player"]) / 2.0], fill=(255, 210, 0, 190), width=2)
        draw.rectangle([0, 0, SCREEN_W - 1, SCREEN_H - 1], outline=(255, 255, 255, 60))
        draw.text((12, 10), "%s turn  zoom %.2f  cam (%.0f, %.0f)"
                  % (side, cam["zoom"], cam["target"][0], cam["target"][1]),
                  fill=(235, 235, 235, 255))
        tiles.append(tile)

        # Every character has to stay inside the frame while this side is
        # singing -- at the stage zoom and at the tightest tier zoom.
        for zoom in (stage["zoom"], MAX_TIER_ZOOM):
            cam_z = dict(cam, zoom=zoom)
            for key, xml in (("opponent", "trollge"), ("player", "bf_blue")):
                box = draw_char(Image.new("RGBA", (1, 1)), None, stage["chars"][key],
                                xml, cam_z, flip=(key == "player"), tint=None)
                margin_left = box["left"]
                margin_right = SCREEN_W - box["right"]
                margin_top = box["top"]
                margin_bottom = SCREEN_H - box["bottom"]
                worst = min(margin_left, margin_right, margin_top, margin_bottom)
                label = "%s, %s cam, zoom %.2f" % (key, side, zoom)
                if worst < MIN_MARGIN:
                    problems.append("%s: only %.0f px of clear space (want %d)"
                                    % (label, worst, MIN_MARGIN))
                print("  %-30s margins L%4.0f R%4.0f T%4.0f B%4.0f"
                      % (label, margin_left, margin_right, margin_top, margin_bottom))

        off = abs(feet["opponent"] - feet["player"])
        if off > GROUND_TOLERANCE:
            problems.append("%s camera: feet are %.1f px apart" % (side, off))

    # The backdrop must cover everything the camera can see, on both sides.
    bg = stage["bg"]
    if bg:
        img = Image.open(os.path.join(IMG_STAGES, bg["file"] + ".png"))
        covers_x = (bg["x"], bg["x"] + img.width * bg["scale"])
        covers_y = (bg["y"], bg["y"] + img.height * bg["scale"])
        for side in ("opponent", "player"):
            cam = camera_for(stage, side)
            cam = dict(cam, zoom=MAX_TIER_ZOOM)
            half_w = SCREEN_W / (2.0 * cam["zoom"])
            half_h = SCREEN_H / (2.0 * cam["zoom"])
            vx = (cam["target"][0] - half_w, cam["target"][0] + half_w)
            vy = (cam["target"][1] - half_h, cam["target"][1] + half_h)
            if vx[0] < covers_x[0] or vx[1] > covers_x[1]:
                problems.append("%s camera sees x %.0f..%.0f, backdrop covers %.0f..%.0f"
                                % (side, vx[0], vx[1], covers_x[0], covers_x[1]))
            if vy[0] < covers_y[0] or vy[1] > covers_y[1]:
                problems.append("%s camera sees y %.0f..%.0f, backdrop covers %.0f..%.0f"
                                % (side, vy[0], vy[1], covers_y[0], covers_y[1]))

    sheet = Image.new("RGBA", (SCREEN_W * 2 + 24, SCREEN_H + 40), (12, 10, 12, 255))
    sheet.paste(tiles[0], (0, 32))
    sheet.paste(tiles[1], (SCREEN_W + 24, 32))
    ImageDraw.Draw(sheet).text((12, 9), "docs/stage.png -- engine framing, both camera sides",
                               fill=(240, 240, 240, 255))
    os.makedirs(DOCS, exist_ok=True)
    out = os.path.join(DOCS, "stage.png")
    sheet.convert("RGB").save(out, optimize=True)
    print("  -> %s" % os.path.relpath(out, ROOT))

    if problems:
        for p in problems:
            print("  ! %s" % p)
        return 1
    print("  positioning OK (all characters inside the frame with >= %d px clearance)"
          % MIN_MARGIN)
    return 0


if __name__ == "__main__":
    sys.exit(main())
