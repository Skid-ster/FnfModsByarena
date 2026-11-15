// ===========================================================================
//  trollge_song_behavior.hx -- the story engine behind the three songs.
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
var captionIn:FlxTween = null;
var captionOut:FlxTween = null;

/** Camera shake helper (FlxCamera.shake is the only reliable way to do this). */
function shake(power:Float, duration:Float):Void {
	var ps = PlayState.instance;
	ps.camGame.shake(power / 1000.0, duration);
	if (ps.camHUD != null) ps.camHUD.shake(power / 1500.0, duration);
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

	ps.insert(ps.members.indexOf(old), newChar);
	ps.remove(old);
	if (ps.strumLines.members[0] != null)
		ps.strumLines.members[0].characters[0] = newChar;

	if (ps.iconP2 != null) ps.iconP2.setIcon(icon);

	// The health bar takes its colours from the characters, so a swap has to
	// repaint it or the bar keeps the previous form's colour (PlayState.hx:920).
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

	FlxG.sound.play(Paths.sound('trollge_distortion'), 0.85);
	FlxG.sound.play(Paths.sound('trollge_jump_scare'), 0.55);
	PlayState.instance.camGame.flash(FlxColor.fromRGB(90, 0, 0), 0.35);
	shake(16.0, 0.8);
}

/** Song 3, 75 s: phase 2 collapses into phase 3. */
var staticDone:Bool = false;
function trollgeToStatic(a = null):Void {
	if (staticDone) return;
	staticDone = true;
	if (swapTrollge('trollge_static', 'trollge_static') == null) return;

	FlxG.sound.play(Paths.sound('trollge_distortion'), 0.9);
	FlxG.sound.play(Paths.sound('trollge_jump_scare'), 0.5);
	shake(20.0, 0.9);
}

/** Song 5, 84 s: the same ending as song 4, reached from the other side. */
function trollgeToSad(a = null):Void {
	trollgeSad(a);
}

/** 60 s of song 3: the static mess resolves into the red-eyed final form. */
function trollgeFinalForm(a = null):Void {
	if (phase2Done) return;
	phase2Done = true;
	if (swapTrollge('trollge_final', 'trollge_final') == null) return;

	FlxG.sound.play(Paths.sound('trollge_jump_scare'), 0.85);
	FlxG.sound.play(Paths.sound('trollge_invert'), 0.6);
	shake(22.0, 0.9);
}

/** 96 s of song 3: he stops fighting and just stands there. One pose. */
function trollgeSad(a = null):Void {
	if (sadDone) return;
	sadDone = true;
	if (swapTrollge('trollge_sad', 'trollge_sad') == null) return;

	FlxG.sound.play(Paths.sound('trollge_invert'), 0.45);
	shake(6.0, 0.6);
}

/** One line of story, typed over the bottom of the screen while you play.
 *
 *  The chart passes it as an "HScript Call" event; the engine splits params[1] on
 *  commas, so anything after the first comma arrives as a second argument and is
 *  joined back here.
 */
function trollgeCaption(a = null, b = null, c = null):Void {
	var text:String = (a == null ? "" : Std.string(a));
	if (b != null) text += ", " + Std.string(b);
	if (c != null) text += ", " + Std.string(c);
	if (text == "") return;

	var ps = PlayState.instance;
	if (ps == null) return;

	if (caption == null) {
		caption = new FlxTypeText(140, 552, 1000, "", 30);
		caption.font = Paths.font("vcr.ttf");
		caption.size = 30;
		caption.color = 0xFFF1F1F5;
		caption.antialiasing = true;
		try {
			caption.borderStyle = 2;          // FlxTextBorderStyle.OUTLINE
			caption.borderSize = 2;
			caption.borderColor = 0xFF05040A;
		} catch (e:Dynamic) {}
		caption.cameras = [ps.camHUD];
		caption.scrollFactor.set(0, 0);
		caption.alpha = 0.0;
		ps.add(caption);
	}

	if (captionIn != null) { captionIn.cancel(); captionIn = null; }
	if (captionOut != null) { captionOut.cancel(); captionOut = null; }

	caption.alpha = 0.0;
	caption.text = "";
	caption.start(text, 0.018);
	captionIn = FlxTween.tween(caption, {alpha: 1.0}, 0.30, {
		onComplete: function(_) {
			captionOut = FlxTween.tween(caption, {alpha: 0.0}, 0.9, {startDelay: 3.4});
		}
	});
}

function trollgeJumpScare(a = null):Void {
	var ps = PlayState.instance;
	var spr = new FlxSprite(0, 0).loadGraphic(Paths.image('trollge_jump_scare'));
	spr.cameras = [ps.camHUD];
	spr.scrollFactor.set();
	spr.antialiasing = false;
	spr.setGraphicSize(FlxG.width, FlxG.height);
	spr.updateHitbox();
	spr.screenCenter();
	ps.add(spr);

	FlxG.sound.play(Paths.sound('trollge_jump_scare'), 0.9);
	ps.camGame.flash(FlxColor.WHITE, 0.12);
	shake(10.0 + 2.5 * scareTier, 0.55);

	FlxTween.tween(spr, {alpha: 0.0}, 0.30, {
		startDelay: 0.22,
		onComplete: function(_) {
			spr.kill();
			ps.remove(spr, true);
		}
	});
}

function trollgeScreenShake(a = null):Void {
	FlxG.sound.play(Paths.sound('trollge_distortion'), 0.75);
	shake(8.0 + 2.0 * scareTier, 0.8);
	if (PlayState.instance.camHUD != null)
		PlayState.instance.camHUD.flash(FlxColor.fromRGB(120, 0, 0), 0.25);
}

function trollgeDistort(a = null):Void {
	var ps = PlayState.instance;
	if (staticSpr == null) return;
	FlxTween.cancelTweensOf(staticSpr);
	staticSpr.alpha = 0.0;
	FlxTween.tween(staticSpr, {alpha: 0.45}, 0.10, {
		onComplete: function(_) FlxTween.tween(staticSpr, {alpha: 0.06}, 0.55)
	});
	FlxG.sound.play(Paths.sound('trollge_distortion'), 0.7);
	shake(5.0 + scareTier, 0.35);
}

function trollgeStatic(a = null):Void {
	if (staticSpr == null) return;
	FlxTween.cancelTweensOf(staticSpr);
	staticSpr.alpha = 0.55;
	FlxTween.tween(staticSpr, {alpha: 0.05}, 0.9);
	FlxG.sound.play(Paths.sound('trollge_distortion'), 0.5);
}

function trollgeInvert(a = null):Void {
	var ps = PlayState.instance;
	if (invertSpr == null) {
		invertSpr = new FlxSprite(0, 0).loadGraphic(Paths.image('trollge_invert'));
		invertSpr.cameras = [ps.camHUD];
		invertSpr.scrollFactor.set();
		invertSpr.setGraphicSize(FlxG.width, FlxG.height);
		invertSpr.updateHitbox();
		invertSpr.screenCenter();
		invertSpr.alpha = 0.0;
		invertSpr.visible = false;
		ps.add(invertSpr);
	}
	invertSpr.visible = true;
	invertSpr.alpha = 0.92;
	FlxTween.tween(invertSpr, {alpha: 0.0}, 1.1, {
		onComplete: function(_) invertSpr.visible = false
	});
	FlxG.sound.play(Paths.sound('trollge_invert'), 0.8);
	shake(14.0 + scareTier, 0.7);
}

// --------------------------------------------------------------------------- hooks

function create() {
	var meta = PlayState.SONG != null ? PlayState.SONG.meta : null;
	var cv = meta != null ? meta.customValues : null;
	if (cv != null && cv.scareTier != null)
		scareTier = Std.int(cv.scareTier);

	var ps = PlayState.instance;
	staticSpr = new FlxSprite(0, 0).loadGraphic(Paths.image('trollge_static'));
	staticSpr.cameras = [ps.camHUD];
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
	// Custom miss feedback (the engine still handles score/health).
	if (event != null) event.missSound = Paths.sound('trollge_miss');
}

function update(elapsed) {
	var ps = PlayState.instance;
	if (ps == null) return;

	// Idle breathing static: scarier songs never fully settle.
	var base:Float = 0.0;
	if (scareTier >= 8) base = 0.055;
	else if (scareTier >= 6) base = 0.035;
	else if (scareTier >= 4) base = 0.02;
	if (staticSpr != null)
		staticSpr.alpha = Math.max(staticSpr.alpha, base);
}

function destroy() {
	if (captionIn != null) { captionIn.cancel(); captionIn = null; }
	if (captionOut != null) { captionOut.cancel(); captionOut = null; }
	if (caption != null) { caption.destroy(); caption = null; }
	if (staticSpr != null) staticSpr.destroy();
	if (invertSpr != null) invertSpr.destroy();
}
