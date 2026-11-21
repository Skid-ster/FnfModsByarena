// ===========================================================================
//  trollge_song_behavior.hx -- the story engine behind the songs.
//
//  Every song folder does:
//      songs/<id>/scripts/song_behavior.hx -> importScript('data/scripts/trollge_song_behavior')
//  which puts this script inside PlayState's script pack. Chart events of the
//  type "HScript Call" then invoke the functions below by name.
//
//  Used by the charts' events ($  trollgeJumpScare / trollgeScreenShake /
//  trollgeInvert / trollgeDistort / trollgeStatic / trollgePhase2).
// ===========================================================================

var scareTier:Int = 1;
var staticSpr:FlxSprite = null;
var invertSpr:FlxSprite = null;

var flashTimer:Float = 0.0;

// In-song narrative captions ("trollgeCaption" chart events). They are drawn on
// the HUD camera so they never drift with the stage, and they never block play.
var caption:FlxTypeText = null;
var captionBand:FlxSprite = null;
var captionIn:FlxTween = null;
var captionOut:FlxTween = null;
var captionBandIn:FlxTween = null;
var captionBandOut:FlxTween = null;

/** Camera shake helper (FlxCamera.shake is the only reliable way to do this). */
function shake(power:Float, duration:Float):Void {
	var ps = PlayState.instance;
	if (ps == null) return;
	ps.camGame.shake(power / 1000.0, duration);
}

var phase2Done:Bool = false;
var sadDone:Bool = false;

/** Replaces the opponent with another character, keeping its position. */
function swapTrollge(name:String, icon:String):Character {
	var ps = PlayState.instance;
	var old = ps.dad;
	if (old == null) return null;

	var newChar:Character = new Character(old.x, old.y, name, false);
	newChar.x = old.x;
	newChar.y = old.y;
	newChar.scrollFactor.set(old.scrollFactor.x, old.scrollFactor.y);
	newChar.cameraOffset.set(old.cameraOffset.x, old.cameraOffset.y);

	ps.insert(ps.members.indexOf(old), newChar);
	ps.remove(old);
	if (ps.strumLines.members[0] != null)
		ps.strumLines.members[0].characters[0] = newChar;

	if (ps.iconP2 != null) ps.iconP2.setIcon(icon);

	if (ps.healthBar != null) {
		if (Options.colorHealthBar) {
			var left:Int = newChar.iconColor != null ? newChar.iconColor : 0xFFFF0000;
			var right:Int = ps.boyfriend != null && ps.boyfriend.iconColor != null ? ps.boyfriend.iconColor : 0xFF66FF33;
			ps.healthBar.createFilledBar(left, right);
		}
		ps.healthBar.updateBar();
	}

	return newChar;
}

/** Song 2, 62 s: the clean trollge corrupts where he stands. */
var glitchDone:Bool = false;
function trollgeToGlitch(a = null):Void {
	if (glitchDone) return;
	glitchDone = true;
	if (swapTrollge('trollge_glitch', 'trollge_glitch') == null) return;

	FlxG.sound.play(Paths.sound('trollge_distortion'), 0.9);
	FlxG.sound.play(Paths.sound('trollge_jump_scare'), 0.6);
	PlayState.instance.camGame.flash(FlxColor.fromRGB(120, 0, 0), 0.4);
	shake(18.0, 0.9);
}

/** Song 3, 75 s: phase 2 collapses into phase 3. */
var staticDone:Bool = false;
function trollgeToStatic(a = null):Void {
	if (staticDone) return;
	staticDone = true;
	if (swapTrollge('trollge_static', 'trollge_static') == null) return;

	FlxG.sound.play(Paths.sound('trollge_distortion'), 0.95);
	FlxG.sound.play(Paths.sound('trollge_jump_scare'), 0.55);
	shake(22.0, 1.0);
}

/** Song 5, 84 s: the same ending as song 4, reached from the other side. */
function trollgeToSad(a = null):Void {
	trollgeSad(a);
}

/** 60 s of song 4: the static mess resolves into the red-eyed final form. */
function trollgeFinalForm(a = null):Void {
	if (phase2Done) return;
	phase2Done = true;
	if (swapTrollge('trollge_final', 'trollge_final') == null) return;

	FlxG.sound.play(Paths.sound('trollge_jump_scare'), 0.9);
	FlxG.sound.play(Paths.sound('trollge_invert'), 0.7);
	shake(24.0, 1.0);
}

/** 96 s of song 4 / 84 s of song 5: he stops fighting and just stands there. */
function trollgeSad(a = null):Void {
	if (sadDone) return;
	sadDone = true;
	if (swapTrollge('trollge_sad', 'trollge_sad') == null) return;

	FlxG.sound.play(Paths.sound('trollge_invert'), 0.5);
	shake(8.0, 0.7);
}

/** One line of story, typed over the bottom of the screen while you play. */
function trollgeCaption(a = null, b = null, c = null):Void {
	var line:String = (a == null ? "" : Std.string(a));
	if (b != null) line += ", " + Std.string(b);
	if (c != null) line += ", " + Std.string(c);
	if (line == "") return;

	var ps = PlayState.instance;
	if (ps == null) return;

	if (caption == null) {
		captionBand = new FlxSprite(0, FlxG.height - 196);
		captionBand.makeGraphic(FlxG.width, 84, 0xC0000000);
		captionBand.scrollFactor.set(0, 0);
		captionBand.cameras = [ps.camHUD];
		captionBand.alpha = 0.0;
		ps.add(captionBand);

		caption = new FlxTypeText(0, FlxG.height - 170, FlxG.width, "", 30);
		caption.font = Paths.font("vcr.ttf");
		caption.size = 30;
		caption.color = 0xFFF1F1F5;
		caption.alignment = "center";
		caption.antialiasing = true;
		caption.scrollFactor.set(0, 0);
		caption.cameras = [ps.camHUD];
		caption.alpha = 0.0;
		ps.add(caption);
	}

	if (captionIn != null) { captionIn.cancel(); captionIn = null; }
	if (captionOut != null) { captionOut.cancel(); captionOut = null; }
	if (captionBandIn != null) { captionBandIn.cancel(); captionBandIn = null; }
	if (captionBandOut != null) { captionBandOut.cancel(); captionBandOut = null; }

	caption.resetText(line);
	caption.start(0.018);
	caption.alpha = 0.0;

	captionIn = FlxTween.tween(caption, {alpha: 1.0}, 0.30, {
		onComplete: function(_) {
			captionOut = FlxTween.tween(caption, {alpha: 0.0}, 0.9, {startDelay: 3.4});
		}
	});

	if (captionBand != null) {
		captionBand.alpha = 0.0;
		captionBandIn = FlxTween.tween(captionBand, {alpha: 1.0}, 0.30);
		captionBandOut = FlxTween.tween(captionBand, {alpha: 0.0}, 0.9, {startDelay: 3.8});
	}
}

/** Full-screen scream built from the trollge's own face — Trollge Files-level. */
function trollgeJumpScare(a = null):Void {
	var ps = PlayState.instance;
	if (ps == null) return;

	var spr = new FlxSprite(0, 0).loadGraphic(Paths.image('trollge_jump_scare'));
	spr.cameras = [ps.camGame];
	spr.scrollFactor.set();
	spr.antialiasing = false;
	spr.setGraphicSize(FlxG.width, FlxG.height);
	spr.updateHitbox();
	spr.screenCenter();
	ps.add(spr);

	FlxG.sound.play(Paths.sound('trollge_jump_scare'), 0.95);
	ps.camGame.flash(FlxColor.WHITE, 0.15);
	shake(12.0 + 3.0 * scareTier, 0.65);

	FlxTween.tween(spr, {alpha: 0.0}, 0.35, {
		startDelay: 0.25,
		onComplete: function(_) {
			spr.kill();
			ps.remove(spr, true);
		}
	});
}

function trollgeScreenShake(a = null):Void {
	FlxG.sound.play(Paths.sound('trollge_distortion'), 0.8);
	shake(10.0 + 2.5 * scareTier, 0.9);
	if (PlayState.instance.camGame != null)
		PlayState.instance.camGame.flash(FlxColor.fromRGB(140, 0, 0), 0.3);
}

function trollgeDistort(a = null):Void {
	var ps = PlayState.instance;
	if (staticSpr == null) return;
	FlxTween.cancelTweensOf(staticSpr);
	staticSpr.alpha = 0.0;
	FlxTween.tween(staticSpr, {alpha: 0.55}, 0.08, {
		onComplete: function(_) FlxTween.tween(staticSpr, {alpha: 0.08}, 0.5)
	});
	FlxG.sound.play(Paths.sound('trollge_distortion'), 0.75);
	shake(6.0 + scareTier * 1.5, 0.4);
	ps.camGame.flash(FlxColor.fromRGB(80, 0, 80), 0.18);
}

function trollgeStatic(a = null):Void {
	if (staticSpr == null) return;
	FlxTween.cancelTweensOf(staticSpr);
	staticSpr.alpha = 0.65;
	FlxTween.tween(staticSpr, {alpha: 0.06}, 1.0);
	FlxG.sound.play(Paths.sound('trollge_distortion'), 0.55);
}

function trollgeInvert(a = null):Void {
	var ps = PlayState.instance;
	if (invertSpr == null) {
		invertSpr = new FlxSprite(0, 0).loadGraphic(Paths.image('trollge_invert'));
		invertSpr.cameras = [ps.camGame];
		invertSpr.scrollFactor.set();
		invertSpr.setGraphicSize(FlxG.width, FlxG.height);
		invertSpr.updateHitbox();
		invertSpr.screenCenter();
		invertSpr.alpha = 0.0;
		invertSpr.visible = false;
		invertSpr.blend = BlendMode.ADD;
		invertSpr.antialiasing = false;
		ps.add(invertSpr);
	}
	FlxTween.cancelTweensOf(invertSpr);
	invertSpr.visible = true;
	invertSpr.alpha = 0.7;
	FlxTween.tween(invertSpr, {alpha: 0.0}, 0.8, {
		onComplete: function(_) invertSpr.visible = false
	});
	FlxG.sound.play(Paths.sound('trollge_invert'), 0.85);
	shake(16.0 + scareTier * 2.0, 0.8);
	ps.camGame.flash(FlxColor.WHITE, 0.1);
}

// --------------------------------------------------------------------------- hooks

function create() {
	var meta = PlayState.SONG != null ? PlayState.SONG.meta : null;
	var cv = meta != null ? meta.customValues : null;
	if (cv != null && cv.scareTier != null)
		scareTier = Std.int(cv.scareTier);

	var ps = PlayState.instance;
	staticSpr = new FlxSprite(0, 0).loadGraphic(Paths.image('trollge_static'));
	staticSpr.cameras = [ps.camGame];
	staticSpr.scrollFactor.set();
	staticSpr.setGraphicSize(FlxG.width, FlxG.height);
	staticSpr.updateHitbox();
	staticSpr.screenCenter();
	staticSpr.alpha = 0.0;
	staticSpr.blend = BlendMode.ADD;
	staticSpr.antialiasing = false;
	ps.add(staticSpr);
}

function onPlayerMiss(event) {
	if (event != null) event.missSound = Paths.sound('trollge_miss');
}

function update(elapsed) {
	var ps = PlayState.instance;
	if (ps == null) return;

	// Idle breathing static: scarier songs never fully settle.
	var base:Float = 0.0;
	if (scareTier >= 8) base = 0.065;
	else if (scareTier >= 6) base = 0.04;
	else if (scareTier >= 4) base = 0.025;
	if (staticSpr != null)
		staticSpr.alpha = Math.max(staticSpr.alpha, base);
}

function destroy() {
	if (captionIn != null) { captionIn.cancel(); captionIn = null; }
	if (captionOut != null) { captionOut.cancel(); captionOut = null; }
	if (captionBandIn != null) { captionBandIn.cancel(); captionBandIn = null; }
	if (captionBandOut != null) { captionBandOut.cancel(); captionBandOut = null; }
	if (caption != null) { caption.destroy(); caption = null; }
	if (captionBand != null) { captionBand.destroy(); captionBand = null; }
	if (staticSpr != null) staticSpr.destroy();
	if (invertSpr != null) invertSpr.destroy();
}
