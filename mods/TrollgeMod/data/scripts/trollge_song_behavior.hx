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

/** Camera shake helper (FlxCamera.shake is the only reliable way to do this). */
function shake(power:Float, duration:Float):Void {
	var ps = PlayState.instance;
	ps.camGame.shake(power / 1000.0, duration);
	if (ps.camHUD != null) ps.camHUD.shake(power / 1500.0, duration);
}

var phase2Done:Bool = false;

/** Swaps the trollge character in front of the player. */
function trollgePhase2(a = null):Void {
	if (phase2Done) return;
	phase2Done = true;

	var ps = PlayState.instance;
	var old = ps.dad;
	if (old == null) return;

	var sum:Character = new Character(old.x, old.y, 'trollge_scary', false);
	sum.x = old.x;
	sum.y = old.y;
	sum.scrollFactor.set(old.scrollFactor.x, old.scrollFactor.y);

	ps.insert(ps.members.indexOf(old), sum);
	ps.remove(old);
	if (ps.strumLines.members[0] != null)
		ps.strumLines.members[0].characters[0] = sum;
	old.destroy();

	if (ps.iconP2 != null) ps.iconP2.setIcon('trollge_scary');
	if (ps.healthBar != null) ps.healthBar.updateBar();

	FlxG.sound.play(Paths.sound('trollge_jump_scare'), 0.85);
	FlxG.sound.play(Paths.sound('trollge_invert'), 0.6);
	shake(22.0, 0.9);
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
	var base:Float = switch (scareTier) {
		case 7: 0.055;
		case 4: 0.02;
		default: 0.0;
	};
	if (staticSpr != null)
		staticSpr.alpha = Math.max(staticSpr.alpha, base);
}

function destroy() {
	if (staticSpr != null) staticSpr.destroy();
	if (invertSpr != null) invertSpr.destroy();
}
