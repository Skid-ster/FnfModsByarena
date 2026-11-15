// ===========================================================================
//  GENERATED FILE -- tools/make_cutscenes.py builds it from tools/song_layout.py.
//
//  It's Getting Dark -- song 2/5 of Trollge Week.
//
//  Codename plays this on its own in Story Mode:
//      PlayState.createPost -> startCutscene("", cutscene) -> ScriptedCutscene
//  so the intro runs before the countdown. Everything is drawn on its own
//  camera, which keeps the stage visible behind it and the HUD off.
// ===========================================================================

var TAG:String = "TROLLGE WEEK  //  2 OF 5";
var SPEAKERS:Array<String> = ["TROLLGE", "BF", "TROLLGE"];
var LINES:Array<String> = ["it's getting dark.", "it's still light out??", "not for long."];
var SHAKES:Array<Float> = [1.2, 0.0, 1.6];
var FRAME:String = "ui/cutscene_frame";

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

/** Look of every label: VCR, softly outlined, antialiased. */
function crisp(t) {
	t.font = Paths.font("vcr.ttf");
	t.antialiasing = true;
	try {
		t.borderStyle = 2;            // FlxTextBorderStyle.OUTLINE
		t.borderSize = 2;
		t.borderColor = 0xFF05040A;
	} catch (e:Dynamic) {}
}

function ui(spr) {
	spr.cameras = [cam];
	spr.scrollFactor.set(0, 0);
	PlayState.instance.add(spr);
}

function label(x:Float, y:Float, width:Float, size:Int, colour:Int):FlxText {
	var t:FlxText = new FlxText(x, y, width, "", size);
	t.size = size;
	t.color = colour;
	crisp(t);
	ui(t);
	return t;
}

function typeText(x:Float, y:Float, width:Float, size:Int, colour:Int):FlxTypeText {
	var t:FlxTypeText = new FlxTypeText(x, y, width, "", size);
	t.size = size;
	t.color = colour;
	crisp(t);
	ui(t);
	return t;
}

function later(delay:Float, fn) {
	timers.push(new FlxTimer().start(delay, function(_) {
		fn();
	}));
}

/** One line: speaker label, typewriter body, optional shake + stinger. */
function playLine(i:Int) {
	if (i >= LINES.length) {
		later(0.9, finish);
		return;
	}
	index = i;
	if (SPEAKERS[i] != "")
		speaker.text = SPEAKERS[i];
	else
		speaker.text = "";

	var shake:Float = SHAKES[i];
	if (shake > 0.0) {
		var g = PlayState.instance;
		g.camGame.shake(0.004 * shake, 0.45);
		if (g.camHUD != null) g.camHUD.shake(0.002 * shake, 0.45);
		FlxG.sound.play(Paths.sound("trollge_distortion"), 0.35);
	}

	body.text = "";
	body.start(LINES[i], 0.018);
	var hold:Float = 1.15 + 0.032 * LINES[i].length + 0.5 * shake;
	later(hold, function() playLine(i + 1));
}

function finish() {
	if (closing) return;
	closing = true;
	var g = PlayState.instance;
	FlxTween.tween(barTop, {y: -barTop.height}, 0.45, {ease: FlxEase.quadIn});
	FlxTween.tween(barBot, {y: FlxG.height}, 0.45, {ease: FlxEase.quadIn});
	for (spr in [frame, title, tag, speaker, body, hint])
		if (spr != null) FlxTween.tween(spr, {alpha: 0.0}, 0.35);
	later(0.5, close);
}

function skipNow() {
	if (closing) return;
	skipped = true;
	finish();
}

function create() {
	var g = PlayState.instance;
	cam = new FlxCamera();
	cam.bgColor = 0;
	FlxG.cameras.add(cam, false);

	if (g.camHUD != null) g.camHUD.visible = false;

	barTop = new FlxSprite(0, -100);
	barTop.loadGraphic(Paths.image("ui/cutscene_bar_top"));
	ui(barTop);
	barBot = new FlxSprite(0, FlxG.height);
	barBot.loadGraphic(Paths.image("ui/cutscene_bar_bottom"));
	ui(barBot);
	FlxTween.tween(barTop, {y: 0}, 0.5, {ease: FlxEase.quadOut});
	FlxTween.tween(barBot, {y: FlxG.height - 100}, 0.5, {ease: FlxEase.quadOut});

	frame = new FlxSprite(50, 430);
	frame.loadGraphic(Paths.image(FRAME));
	ui(frame);
	frame.alpha = 0.0;
	FlxTween.tween(frame, {alpha: 1.0}, 0.4, {startDelay: 0.15});

	title = label(86, 34, 1120, 78, 0xFFF2EEE8);
	title.text = "IT'S GETTING DARK";
	title.alpha = 0.0;
	FlxTween.tween(title, {alpha: 1.0}, 0.45, {startDelay: 0.25});

	tag = label(92, 126, 1100, 24, 0xFFD2434F);
	tag.text = TAG;
	tag.alpha = 0.0;
	FlxTween.tween(tag, {alpha: 1.0}, 0.4, {startDelay: 0.4});

	speaker = label(96, 480, 1000, 26, 0xFFD2434F);
	body = typeText(96, 524, 1070, 34, 0xFFF1F1F5);
	hint = label(1010, 596, 200, 18, 0xFF8A93A6);
	hint.text = "ENTER TO SKIP";
	hint.alpha = 0.55;

	FlxG.sound.play(Paths.sound("trollge_distortion"), 0.6);
	later(0.8, function() playLine(0));
}

function update(elapsed:Float) {
	if (FlxG.keys.justPressed.ENTER || FlxG.keys.justPressed.SPACE
		|| FlxG.keys.justPressed.ESCAPE)
		skipNow();
}

function destroy() {
	var g = PlayState.instance;
	for (timer in timers) timer.cancel();
	timers = [];
	if (g != null) {
		if (g.camHUD != null) g.camHUD.visible = true;
		for (spr in [frame, barTop, barBot, title, tag, speaker, body, hint])
			if (spr != null) g.remove(spr, true);
	}
	if (cam != null) FlxG.cameras.remove(cam);
}
