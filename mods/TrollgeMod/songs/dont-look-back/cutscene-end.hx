// ===========================================================================
//  GENERATED FILE -- tools/make_cutscenes.py builds it from tools/song_layout.py.
//
//  Don't Look Back -- end cutscene, played by Codename on its own:
//      PlayState -> startCutscene("end-", endCutscene, nextSong)
//  The screen fades out under the last chord, the outro lines type themselves in,
//  then `close()` hands control back to the engine (results / next song).
// ===========================================================================

var LINES:Array<String> = ["you looked."];
var SHAKES:Array<Float> = [0.0];
var IS_FINALE:Bool = false;

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
function crisp(t) {
	t.font = Paths.font("vcr.ttf");
	t.antialiasing = true;
}

function ui(spr) {
	spr.cameras = [cam];
	spr.scrollFactor.set(0, 0);
	PlayState.instance.add(spr);
}

function typeText(x:Float, y:Float, width:Float, size:Int, colour:Int):FlxTypeText {
	var t:FlxTypeText = new FlxTypeText(x, y, width, "", size);
	t.font = Paths.font("vcr.ttf");
	t.size = size;
	t.color = colour;
	t.antialiasing = true;
	return cast ui(t);
}

function later(delay:Float, fn) {
	timers.push(new FlxTimer().start(delay, function(_) {
		fn();
	}));
}

function playLine(i:Int) {
	if (i >= LINES.length) {
		later(1.4 if IS_FINALE else 0.6, finish);
		return;
	}
	index = i;
	var shake:Float = SHAKES[i];
	if (shake > 0.0 && PlayState.instance != null)
		PlayState.instance.camGame.shake(0.005 * shake, 0.5);

	body.resetText(LINES[i]);
	body.start(0.05);
	var hold:Float = 1.5 + 0.04 * LINES[i].length + 0.6 * shake;
	later(hold, function() playLine(i + 1));
}

function finish() {
	if (closing) return;
	closing = true;
	FlxTween.tween(body, {alpha: 0.0}, 0.5);
	if (hint != null) FlxTween.tween(hint, {alpha: 0.0}, 0.4);
	later(0.6, close);
}

function skipNow() {
	if (closing) return;
	finish();
}

function create() {
	var g = PlayState.instance;
	cam = new FlxCamera();
	cam.bgColor = 0;
	FlxG.cameras.add(cam, false);

	if (g.camHUD != null) g.camHUD.visible = false;

	veil = new FlxSprite(0, 0);
	veil.loadGraphic(Paths.image("ui/cutscene_veil"));
	ui(veil);
	veil.alpha = 0.0;
	FlxTween.tween(veil, {alpha: 1.0}, 1.1, {ease: FlxEase.quadInOut});

	body = typeText(140, 300, 1000, 40, 0xFFF1F1F5);
	body.alpha = 0.0;
	FlxTween.tween(body, {alpha: 1.0}, 0.6, {startDelay: 0.7});

	hint = new FlxText(1010, 660, 220, "", 18);
	hint.size = 18;
	hint.color = 0xFF8A93A6;
	crisp(hint);
	hint.text = "ENTER TO SKIP";
	hint.alpha = 0.4;
	ui(hint);

	FlxG.sound.play(Paths.sound("trollge_invert"), 0.7);
	later(1.0, function() playLine(0));
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
		for (spr in [veil, body, hint])
			if (spr != null) g.remove(spr, true);
	}
	if (cam != null) FlxG.cameras.remove(cam);
}
