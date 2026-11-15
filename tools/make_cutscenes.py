#!/usr/bin/env python3
"""
Cutscenes: the art they use and the HScript that plays them.

Codename Engine looks for cutscenes by itself, so shipping the files is enough:

    songs/<song>/cutscene.hx       PlayState.createPost -> startCutscene("", cutscene)
                                   (a ScriptedCutscene substate, before the countdown)
    songs/<song>/cutscene-end.hx   PlayState -> startCutscene("end-", endCutscene, nextSong)
    images/ui/cutscene_*.png       the letterbox bars and the dialogue frame

Both files are generated here from `tools/song_layout.py`, so the copy the player
reads and the copy the audio/chart were built from cannot drift.

Run with:  python3 tools/make_cutscenes.py
"""

import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import song_layout as L  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, "mods", "TrollgeMod")
SONGS_DIR = os.path.join(MOD, "songs")
UI_DIR = os.path.join(MOD, "images", "ui")

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

INK = (8, 6, 10)
BLOOD = (196, 16, 30)
CYAN = (63, 123, 209)
BONE = (238, 232, 236)

FRAME_W, FRAME_H = 1180, 208
BAR_W, BAR_H = 1280, 100


# --------------------------------------------------------------------------- #
# Art
# --------------------------------------------------------------------------- #

def _panel(dark):
    """The dialogue frame: a torn, half-transparent panel with a glowing edge."""
    rng = random.Random(7 if dark else 3)
    img = Image.new("RGBA", (FRAME_W, FRAME_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    accent = BLOOD if dark else CYAN
    fill = (14, 10, 14, 226) if dark else (12, 10, 18, 214)

    # Body: rounded, then a torn top edge so it reads as paper, not a UI box.
    draw.rounded_rectangle((0, 0, FRAME_W - 1, FRAME_H - 1), radius=18, fill=fill)
    for x in range(0, FRAME_W, 7):
        bite = rng.randint(0, 6)
        draw.polygon([(x, 0), (x + 7, 0), (x + 4, bite), (x + 1, bite)], fill=(0, 0, 0, 0))

    # Inner scanlines: cheap CRT texture, keeps flat fills from looking plastic.
    for y in range(6, FRAME_H - 6, 4):
        draw.line((10, y, FRAME_W - 10, y), fill=(255, 255, 255, 8))

    # Edge light: a thin bright line plus a soft bloom behind it.
    edge = Image.new("RGBA", (FRAME_W, FRAME_H), (0, 0, 0, 0))
    ed = ImageDraw.Draw(edge)
    ed.rounded_rectangle((2, 2, FRAME_W - 3, FRAME_H - 3), radius=16,
                         outline=accent + (235,), width=3)
    ed.line((22, 26, 22, FRAME_H - 26), fill=accent + (255,), width=6)
    glow = edge.filter(ImageFilter.GaussianBlur(9))
    img = Image.alpha_composite(img, glow)
    img = Image.alpha_composite(img, edge)

    # Wear: a few scratches near the corners.
    scratch = ImageDraw.Draw(img)
    for _ in range(22 if dark else 14):
        x = rng.choice([rng.randint(6, 120), rng.randint(FRAME_W - 130, FRAME_W - 8)])
        y = rng.randint(10, FRAME_H - 10)
        length = rng.randint(3, 16)
        scratch.line((x, y, x + rng.randint(-2, 2), y + length),
                     fill=(255, 255, 255, rng.randint(10, 34)), width=1)
    return img


def _bar(flip):
    """A letterbox bar with a soft inner edge, so the crop does not look pasted."""
    img = Image.new("RGBA", (BAR_W, BAR_H), (0, 0, 0, 255))
    if flip:
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
    fade = Image.new("RGBA", (BAR_W, BAR_H), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fade)
    rows = 22
    for i in range(rows):
        alpha = int(255 * (i / rows) ** 1.6)
        y = BAR_H - rows + i if not flip else i
        fd.line((0, y, BAR_W, y), fill=(0, 0, 0, 255 - alpha))
    if flip:
        # flipped image: the soft edge belongs at the bottom of the picture
        fade = fade.transpose(Image.FLIP_TOP_BOTTOM)
    return Image.alpha_composite(img, fade)


def make_art():
    os.makedirs(UI_DIR, exist_ok=True)
    wrote = []

    for name, dark in (("cutscene_frame", False), ("cutscene_frame_dark", True)):
        path = os.path.join(UI_DIR, name + ".png")
        _panel(dark).save(path)
        wrote.append(path)

    for name, flip in (("cutscene_bar_top", True), ("cutscene_bar_bottom", False)):
        path = os.path.join(UI_DIR, name + ".png")
        _bar(flip).save(path)
        wrote.append(path)

    # docs/preview: the frame over a still of the stage, so the look is reviewable.
    stage = os.path.join(MOD, "images", "stages", "trollge", "bg_scary.png")
    if os.path.isfile(stage):
        preview = Image.open(stage).convert("RGBA").resize((1280, 720))
        overlay = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
        overlay.alpha_composite(_bar(True), (0, 0))
        overlay.alpha_composite(_bar(False), (0, 720 - BAR_H))
        overlay.alpha_composite(_panel(True), (50, 430))
        preview = Image.alpha_composite(preview, overlay)
        draw = ImageDraw.Draw(preview)
        try:
            title = ImageFont.truetype(FONT_BOLD, 78)
            small = ImageFont.truetype(FONT_BOLD, 26)
            body = ImageFont.truetype(FONT_BOLD, 32)
        except OSError:
            title = small = body = ImageFont.load_default()
        draw.text((88, 40), "DON'T LOOK BACK", font=title, fill=BONE)
        draw.text((92, 132), "TROLLGE WEEK  //  3 OF 5", font=small, fill=BLOOD)
        draw.text((96, 494), "TROLLGE", font=small, fill=BLOOD)
        draw.text((96, 540), "because i'm already there.", font=body, fill=BONE)
        out = os.path.join(ROOT, "docs", "cutscene.jpeg")
        preview.convert("RGB").save(out, quality=92)
        wrote.append(out)

        # The ending preview: the veil plus the first outro line.
        veil_path = os.path.join(UI_DIR, "cutscene_veil.png")
        if os.path.isfile(veil_path):
            ending = Image.open(stage).convert("RGBA").resize((1280, 720))
            ending = Image.alpha_composite(ending, Image.open(veil_path).convert("RGBA"))
            ed = ImageDraw.Draw(ending)
            ed.text((140, 300), "GOODBYE.", font=body, fill=BONE)
            ed.text((140, 396), "the incident is over.", font=small, fill=(150, 152, 164))
            out = os.path.join(ROOT, "docs", "ending.jpeg")
            ending.convert("RGB").save(out, quality=92)
            wrote.append(out)
    return wrote


# --------------------------------------------------------------------------- #
# HScript
# --------------------------------------------------------------------------- #

#: Shared body. Only APIs the engine itself uses are touched: FlxCamera + camera
#: lists (DialogueCutscene), FlxSprite.loadGraphic (every stage script),
#: FlxTypeText.font/size/color/start (DialogueBox.hx), FlxTimer (guns' cutscene).
CUTSCENE_TEMPLATE = '''// ===========================================================================
//  GENERATED FILE -- tools/make_cutscenes.py builds it from tools/song_layout.py.
//
//  {display} -- song {number}/5 of Trollge Week.
//
//  Codename plays this on its own in Story Mode:
//      PlayState.createPost -> startCutscene("", cutscene) -> ScriptedCutscene
//  so the intro runs before the countdown. Everything is drawn on its own
//  camera, which keeps the stage visible behind it and the HUD off.
// ===========================================================================

var TAG:String = "{tag}";
var SPEAKERS:Array<String> = [{speakers}];
var LINES:Array<String> = [{lines}];
var SHAKES:Array<Float> = [{shakes}];
var FRAME:String = "{frame}";

var cam:FlxCamera = null;
var frame:FlxSprite = null;
var barTop:FlxSprite = null;
var barBot:FlxSprite = null;
var title:FlxText = null;
var tag:FlxText = null;
var speaker:FlxText = null;
var body:FlxTypeText = null;
var hint:FlxText = null;
var timers:Array<FlxTimer> = [];
var index:Int = 0;
var skipped:Bool = false;
var closing:Bool = false;

/** Look of every label: VCR, antialiased, no outline.
 *
 *  No `borderStyle` on purpose. FlxTextBorderStyle is a real enum in flixel and
 *  FlxText.regenGraphic() switches on it -- writing a raw int from HScript makes
 *  that switch throw a Null Object Reference the first time the text is drawn.
 *  The labels sit on the dark panel and the letterbox bars, so plain white reads.
 */
function crisp(t) {{
	t.font = Paths.font("vcr.ttf");
	t.antialiasing = true;
}}

function ui(spr) {{
	spr.cameras = [cam];
	spr.scrollFactor.set(0, 0);
	PlayState.instance.add(spr);
}}

function label(x:Float, y:Float, width:Float, size:Int, colour:Int):FlxText {{
	var t:FlxText = new FlxText(x, y, width, "", size);
	t.size = size;
	t.color = colour;
	crisp(t);
	ui(t);
	return t;
}}

function typeText(x:Float, y:Float, width:Float, size:Int, colour:Int):FlxTypeText {{
	var t:FlxTypeText = new FlxTypeText(x, y, width, "", size);
	t.size = size;
	t.color = colour;
	crisp(t);
	ui(t);
	return t;
}}

function later(delay:Float, fn) {{
	timers.push(new FlxTimer().start(delay, function(_) {{
		fn();
	}}));
}}

/** One line: speaker label, typewriter body, optional shake + stinger. */
function playLine(i:Int) {{
	if (i >= LINES.length) {{
		later(0.9, finish);
		return;
	}}
	index = i;
	if (SPEAKERS[i] != "")
		speaker.text = SPEAKERS[i];
	else
		speaker.text = "";

	var shake:Float = SHAKES[i];
	if (shake > 0.0) {{
		var g = PlayState.instance;
		g.camGame.shake(0.004 * shake, 0.45);
		if (g.camHUD != null) g.camHUD.shake(0.002 * shake, 0.45);
		FlxG.sound.play(Paths.sound("trollge_distortion"), 0.35);
	}}

	body.resetText(LINES[i]);
	body.start(0.018);
	var hold:Float = 1.15 + 0.032 * LINES[i].length + 0.5 * shake;
	later(hold, function() playLine(i + 1));
}}

function finish() {{
	if (closing) return;
	closing = true;
	var g = PlayState.instance;
	FlxTween.tween(barTop, {{y: -barTop.height}}, 0.45, {{ease: FlxEase.quadIn}});
	FlxTween.tween(barBot, {{y: FlxG.height}}, 0.45, {{ease: FlxEase.quadIn}});
	for (spr in [frame, title, tag, speaker, body, hint])
		if (spr != null) FlxTween.tween(spr, {{alpha: 0.0}}, 0.35);
	later(0.5, close);
}}

function skipNow() {{
	if (closing) return;
	skipped = true;
	finish();
}}

function create() {{
	var g = PlayState.instance;
	cam = new FlxCamera();
	cam.bgColor = 0;
	FlxG.cameras.add(cam, false);

	if (g.camHUD != null) g.camHUD.visible = false;

	barTop = new FlxSprite(0, -{bar_h});
	barTop.loadGraphic(Paths.image("ui/cutscene_bar_top"));
	ui(barTop);
	barBot = new FlxSprite(0, FlxG.height);
	barBot.loadGraphic(Paths.image("ui/cutscene_bar_bottom"));
	ui(barBot);
	FlxTween.tween(barTop, {{y: 0}}, 0.5, {{ease: FlxEase.quadOut}});
	FlxTween.tween(barBot, {{y: FlxG.height - {bar_h}}}, 0.5, {{ease: FlxEase.quadOut}});

	frame = new FlxSprite(50, 430);
	frame.loadGraphic(Paths.image(FRAME));
	ui(frame);
	frame.alpha = 0.0;
	FlxTween.tween(frame, {{alpha: 1.0}}, 0.4, {{startDelay: 0.15}});

	title = label(86, 34, 1120, 78, 0xFFF2EEE8);
	title.text = "{title}";
	title.alpha = 0.0;
	FlxTween.tween(title, {{alpha: 1.0}}, 0.45, {{startDelay: 0.25}});

	tag = label(92, 126, 1100, 24, {accent});
	tag.text = TAG;
	tag.alpha = 0.0;
	FlxTween.tween(tag, {{alpha: 1.0}}, 0.4, {{startDelay: 0.4}});

	speaker = label(96, 480, 1000, 26, {accent});
	body = typeText(96, 524, 1070, 34, 0xFFF1F1F5);
	hint = label(1010, 596, 200, 18, 0xFF8A93A6);
	hint.text = "ENTER TO SKIP";
	hint.alpha = 0.55;

	FlxG.sound.play(Paths.sound("{stinger}"), 0.6);
	later(0.8, function() playLine(0));
}}

function update(elapsed:Float) {{
	if (FlxG.keys.justPressed.ENTER || FlxG.keys.justPressed.SPACE
		|| FlxG.keys.justPressed.ESCAPE)
		skipNow();
}}

function destroy() {{
	var g = PlayState.instance;
	for (timer in timers) timer.cancel();
	timers = [];
	if (g != null) {{
		if (g.camHUD != null) g.camHUD.visible = true;
		for (spr in [frame, barTop, barBot, title, tag, speaker, body, hint])
			if (spr != null) g.remove(spr, true);
	}}
	if (cam != null) FlxG.cameras.remove(cam);
}}
'''

END_TEMPLATE = '''// ===========================================================================
//  GENERATED FILE -- tools/make_cutscenes.py builds it from tools/song_layout.py.
//
//  {display} -- end cutscene, played by Codename on its own:
//      PlayState -> startCutscene("end-", endCutscene, nextSong)
//  The screen fades out under the last chord, the outro lines type themselves in,
//  then `close()` hands control back to the engine (results / next song).
// ===========================================================================

var LINES:Array<String> = [{lines}];
var SHAKES:Array<Float> = [{shakes}];
var IS_FINALE:Bool = {finale};

var cam:FlxCamera = null;
var veil:FlxSprite = null;
var body:FlxTypeText = null;
var hint:FlxText = null;
var timers:Array<FlxTimer> = [];
var index:Int = 0;
var closing:Bool = false;

/** Look of every label: VCR, antialiased, no outline.
 *
 *  No `borderStyle` on purpose. FlxTextBorderStyle is a real enum in flixel and
 *  FlxText.regenGraphic() switches on it -- writing a raw int from HScript makes
 *  that switch throw a Null Object Reference the first time the text is drawn.
 *  The labels sit on the dark panel and the letterbox bars, so plain white reads.
 */
function crisp(t) {{
	t.font = Paths.font("vcr.ttf");
	t.antialiasing = true;
}}

function ui(spr) {{
	spr.cameras = [cam];
	spr.scrollFactor.set(0, 0);
	PlayState.instance.add(spr);
}}

function typeText(x:Float, y:Float, width:Float, size:Int, colour:Int):FlxTypeText {{
	var t:FlxTypeText = new FlxTypeText(x, y, width, "", size);
	t.font = Paths.font("vcr.ttf");
	t.size = size;
	t.color = colour;
	t.antialiasing = true;
	return cast ui(t);
}}

function later(delay:Float, fn) {{
	timers.push(new FlxTimer().start(delay, function(_) {{
		fn();
	}}));
}}

function playLine(i:Int) {{
	if (i >= LINES.length) {{
		later(1.4 if IS_FINALE else 0.6, finish);
		return;
	}}
	index = i;
	var shake:Float = SHAKES[i];
	if (shake > 0.0 && PlayState.instance != null)
		PlayState.instance.camGame.shake(0.005 * shake, 0.5);

	body.resetText(LINES[i]);
	body.start(0.05);
	var hold:Float = 1.5 + 0.04 * LINES[i].length + 0.6 * shake;
	later(hold, function() playLine(i + 1));
}}

function finish() {{
	if (closing) return;
	closing = true;
	FlxTween.tween(body, {{alpha: 0.0}}, 0.5);
	if (hint != null) FlxTween.tween(hint, {{alpha: 0.0}}, 0.4);
	later(0.6, close);
}}

function skipNow() {{
	if (closing) return;
	finish();
}}

function create() {{
	var g = PlayState.instance;
	cam = new FlxCamera();
	cam.bgColor = 0;
	FlxG.cameras.add(cam, false);

	if (g.camHUD != null) g.camHUD.visible = false;

	veil = new FlxSprite(0, 0);
	veil.loadGraphic(Paths.image("ui/cutscene_veil"));
	ui(veil);
	veil.alpha = 0.0;
	FlxTween.tween(veil, {{alpha: 1.0}}, 1.1, {{ease: FlxEase.quadInOut}});

	body = typeText(140, 300, 1000, 40, 0xFFF1F1F5);
	body.alpha = 0.0;
	FlxTween.tween(body, {{alpha: 1.0}}, 0.6, {{startDelay: 0.7}});

	hint = new FlxText(1010, 660, 220, "", 18);
	hint.size = 18;
	hint.color = 0xFF8A93A6;
	crisp(hint);
	hint.text = "ENTER TO SKIP";
	hint.alpha = 0.4;
	ui(hint);

	FlxG.sound.play(Paths.sound("{stinger}"), 0.7);
	later(1.0, function() playLine(0));
}}

function update(elapsed:Float) {{
	if (FlxG.keys.justPressed.ENTER || FlxG.keys.justPressed.SPACE
		|| FlxG.keys.justPressed.ESCAPE)
		skipNow();
}}

function destroy() {{
	var g = PlayState.instance;
	for (timer in timers) timer.cancel();
	timers = [];
	if (g != null) {{
		if (g.camHUD != null) g.camHUD.visible = true;
		for (spr in [veil, body, hint])
			if (spr != null) g.remove(spr, true);
	}}
	if (cam != null) FlxG.cameras.remove(cam);
}}
'''

ACCENTS = {
    "trolling": "0xFF6FA8FF",
    "getting-dark": "0xFFD2434F",
    "dont-look-back": "0xFFE24B4B",
    "super-scary": "0xFFFF3B3B",
    "the-incident": "0xFFB0121E",
}

STINGERS = {
    "trolling": "trollge_hit",
    "getting-dark": "trollge_distortion",
    "dont-look-back": "trollge_distortion",
    "super-scary": "trollge_jump_scare",
    "the-incident": "trollge_invert",
}

END_STINGERS = {
    "trolling": "trollge_theme",
    "getting-dark": "trollge_distortion",
    "dont-look-back": "trollge_invert",
    "super-scary": "trollge_jump_scare",
    "the-incident": "trollge_theme_scary",
}


def hx_string(text):
    return '"%s"' % text.replace("\\", "\\\\").replace('"', '\\"')


def emit_cutscene(song, number):
    data = song["cutscene"]
    lines = data["lines"]
    return CUTSCENE_TEMPLATE.format(
        display=song["display"],
        number=number,
        tag=data["tag"],
        speakers=", ".join(hx_string(who) for who, _text, _shake in lines),
        lines=", ".join(hx_string(text) for _who, text, _shake in lines),
        shakes=", ".join("%.1f" % shake for _who, _text, shake in lines),
        frame=data["frame"],
        title=song["display"].upper().replace('"', "'"),
        accent=ACCENTS[song["id"]],
        stinger=STINGERS[song["id"]],
        bar_h=BAR_H,
    )


def emit_end(song):
    data = song["cutscene"]
    outro = data["outro"]
    finale = song["id"] == "the-incident"
    return END_TEMPLATE.format(
        display=song["display"],
        lines=", ".join(hx_string(text) for _who, text, _shake in outro),
        shakes=", ".join("%.1f" % shake for _who, _text, shake in outro),
        finale="true" if finale else "false",
        stinger=END_STINGERS[song["id"]],
    )


def make_veil():
    """The end-cutscene veil: black, with a soft red core so the ending breathes."""
    img = Image.new("RGBA", (1280, 720), (0, 0, 0, 255))
    glow = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-260, 60, 1540, 800), fill=(120, 6, 14, 70))
    glow = glow.filter(ImageFilter.GaussianBlur(80))
    img = Image.alpha_composite(img, glow)
    path = os.path.join(UI_DIR, "cutscene_veil.png")
    img.save(path)
    return path


def main():
    wrote = make_art()
    wrote.append(make_veil())

    for number, song in enumerate(L.SONGS, start=1):
        base = os.path.join(SONGS_DIR, song["id"])
        os.makedirs(base, exist_ok=True)
        for name, text in (("cutscene.hx", emit_cutscene(song, number)),
                           ("cutscene-end.hx", emit_end(song))):
            path = os.path.join(base, name)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            wrote.append(path)
        print("  %-14s %d intro lines, %d outro lines"
              % (song["id"], len(song["cutscene"]["lines"]),
                 len(song["cutscene"]["outro"])))

    for path in wrote:
        print("  -> %s" % os.path.relpath(path, ROOT))


if __name__ == "__main__":
    main()
