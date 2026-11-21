// ===========================================================================
//  trollge.hx -- stage script
//
//  One stage, five moods: the backdrop, the arrow skin, the camera and the amount
//  of screen corruption are all picked from the song's scare tier
//  ("Trolling" 2/10, "It's Getting Dark" 4/10, "Don't Look Back" 6/10,
//  "Super Scary Trollge" 8/10, "The Incident" 10/10).
//
//  It also owns both full-screen shaders: the VHS grade (shaders/trollge_vhs.frag)
//  on camGame, and the CRT pass (shaders/crt.frag) on camGame *and* camHUD at a
//  subtle, stable strength. The game-camera effects rise per scare tier and
//  are punched by story events. Alongside them: the camera work (zoom, shake) and
//  the per-character note-hit voices.
//
//  Visual horror is Trollge Files-inspired: heavy chromatic aberration, barrel
//  curvature, horizontal tear bands, VHS tracking wobble, halation bloom,
//  animated static grain, screen inversion on jumpscare events, and white flash.
// ===========================================================================

var scareTier:Int = 1;
var staticSpr:FlxSprite = null;
var noteSkin:String = null;

var vhs = null;              // FunkinShader (Dynamic: HScript resolves it at runtime)
var vhsFilter = null;
var vhsIntensity:Float = 0.35;

// CRT pass (shaders/crt.frag). Two copies: the game camera sits under the VHS
// grade as well, the HUD gets a weaker one of its own so score, captions and the
// health bar stay readable. Both are optional -- see setupShaders().
var crt = null;
var crtHud = null;
var crtFilter = null;
var crtHudFilter = null;
var camZoomBase:Float = 0.95;   // stage xml zoom, raised per scare tier
var camZoomApplied:Bool = false;
var glitch:Float = 0.0;
var glitchTimes:Array<Float> = [];
var songClock:Float = 0.0;

// Inversion overlay (full-screen negative during trollgeInvert / jumpscare).
var invertSpr:FlxSprite = null;
var invertTimer:Float = 0.0;

function create() {
	var meta = PlayState.SONG != null ? PlayState.SONG.meta : null;
	var cv = meta != null ? meta.customValues : null;
	if (cv != null && cv.scareTier != null)
		scareTier = Std.int(cv.scareTier);

	// Arrow skin: notes get theirs from the chart's noteTypes, but strums always
	// default to game/notes/default, so mirror the song's skin onto them here.
	noteSkin = scareTier >= 10 ? 'torn' : (scareTier >= 6 ? 'corrupt'
		: (scareTier >= 4 ? 'shadow' : null));

	// Screen grade: 2/10 is a light tape look, 10/10 is a deck that has given up.
	vhsIntensity = Math.min(1.0, 0.35 + (scareTier - 2) * 0.08);
	setupShaders();

	// Story events that should punch the shader, read straight from the chart.
	glitchTimes = [];
	if (PlayState.SONG != null && PlayState.SONG.events != null) {
		for (e in PlayState.SONG.events) {
			if (e.name != 'HScript Call' || e.params == null || e.params.length == 0) continue;
			var fn:String = Std.string(e.params[0]);
			if (fn == 'trollgeJumpScare' || fn == 'trollgeInvert' || fn == 'trollgePhase2'
				|| fn == 'trollgeDistort' || fn == 'trollgeStatic' || fn == 'trollgeFinalForm'
				|| fn == 'trollgeScreenShake' || fn == 'trollgeToGlitch'
				|| fn == 'trollgeToStatic' || fn == 'trollgeToSad'
				|| fn == 'trollgePhase2' || fn == 'trollgeSad')
				glitchTimes.push(e.time / 1000.0);
		}
	}

	// Swap in the nastier backdrop once the song earns it.
	if (scareTier >= 4 && bg != null) {
		var key:String = scareTier >= 10 ? 'stages/trollge/bg_hell'
			: (scareTier >= 8 ? 'stages/trollge/bg_nightmare'
			: (scareTier >= 6 ? 'stages/trollge/bg_glitch' : 'stages/trollge/bg_scary'));
		if (Assets.exists(Paths.image(key))) {
			var pic = new FlxSprite(bg.x, bg.y);
			pic.loadGraphic(Paths.image(key));
			pic.scale.set(bg.scale.x, bg.scale.y);
			pic.scrollFactor.set(bg.scrollFactor.x, bg.scrollFactor.y);
			pic.antialiasing = true;
			pic.updateHitbox();
			PlayState.instance.insert(PlayState.instance.members.indexOf(bg), pic);
			bg.visible = false;
		}
	}

	// Beat flicker is separate from song-event static, but both stay under HUD.
	staticSpr = new FlxSprite(0, 0).loadGraphic(Paths.image('trollge_static'));
	staticSpr.cameras = [PlayState.instance.camGame];
	staticSpr.scrollFactor.set();
	staticSpr.setGraphicSize(FlxG.width, FlxG.height);
	staticSpr.updateHitbox();
	staticSpr.screenCenter();
	staticSpr.alpha = 0.0;
	staticSpr.blend = BlendMode.ADD;
	staticSpr.antialiasing = false;
	PlayState.instance.add(staticSpr);

	// Full-screen inversion overlay for Trollge Files-style color flips.
	invertSpr = new FlxSprite(0, 0).loadGraphic(Paths.image('trollge_invert'));
	invertSpr.cameras = [PlayState.instance.camGame];
	invertSpr.scrollFactor.set();
	invertSpr.setGraphicSize(FlxG.width, FlxG.height);
	invertSpr.updateHitbox();
	invertSpr.screenCenter();
	invertSpr.alpha = 0.0;
	invertSpr.visible = false;
	invertSpr.blend = BlendMode.ADD;
	invertSpr.antialiasing = false;
	PlayState.instance.add(invertSpr);
}

function setupShaders() {
	var shaderClass = null;
	var filterClass = null;
	try { shaderClass = Type.resolveClass('funkin.backend.shaders.FunkinShader'); } catch (e) {}
	try { filterClass = Type.resolveClass('openfl.filters.ShaderFilter'); } catch (e) {}
	if (shaderClass == null || filterClass == null) return;

	// 1. VHS grade (shaders/trollge_vhs.frag).
	try { vhs = shaderClass.fromFile('trollge_vhs'); } catch (e) { vhs = null; }
	if (vhs != null) {
		try { vhsFilter = Type.createInstance(filterClass, [vhs]); } catch (e) { vhsFilter = null; }
	}

	// 2. CRT pass (shaders/crt.frag), game camera.
	try { crt = shaderClass.fromFile('crt'); } catch (e) { crt = null; }
	if (crt != null) {
		try { crtFilter = Type.createInstance(filterClass, [crt]); } catch (e) { crtFilter = null; }
	}

	// 3. CRT pass, HUD camera (its own instance so the two can differ).
	try { crtHud = shaderClass.fromFile('crt'); } catch (e) { crtHud = null; }
	if (crtHud != null) {
		try { crtHudFilter = Type.createInstance(filterClass, [crtHud]); } catch (e) { crtHudFilter = null; }
	}

	var ps = PlayState.instance;
	if (ps == null) return;

	if (ps.camGame != null && (vhsFilter != null || crtFilter != null)) {
		try {
			var gameFilters = ps.camGame.filters != null ? ps.camGame.filters.copy() : [];
			if (vhsFilter != null) gameFilters.push(vhsFilter);
			if (crtFilter != null) gameFilters.push(crtFilter);
			ps.camGame.filters = gameFilters;
		} catch (e) {}
	}
	if (ps.camHUD != null && crtHudFilter != null) {
		try {
			var hudFilters = ps.camHUD.filters != null ? ps.camHUD.filters.copy() : [];
			hudFilters.push(crtHudFilter);
			ps.camHUD.filters = hudFilters;
		} catch (e) {}
	}
}

// Remove only filters created by this stage; other scripts may share cameras.
function destroy() {
	var ps = PlayState.instance;
	if (ps == null) return;
	try {
		if (ps.camGame != null && ps.camGame.filters != null) {
			var filters = ps.camGame.filters.copy();
			if (vhsFilter != null) filters.remove(vhsFilter);
			if (crtFilter != null) filters.remove(crtFilter);
			ps.camGame.filters = filters;
		}
	} catch (e) {}
	try {
		if (ps.camHUD != null && ps.camHUD.filters != null) {
			var filters = ps.camHUD.filters.copy();
			if (crtHudFilter != null) filters.remove(crtHudFilter);
			ps.camHUD.filters = filters;
		}
	} catch (e) {}
}

function shaderFloat(name:String, value:Float) {
	setFloatOn(vhs, name, value);
}

/** Write one uniform, on a shader that may be null and may not exist at all. */
function setFloatOn(shader, name:String, value:Float) {
	if (shader == null) return;
	try {
		shader.setFloat(name, value);
	} catch (e) {}
}

function update(elapsed:Float) {
	songClock += elapsed;

	// One-time camera setup (see create()): the scarier the song, the tighter
	// the frame. PlayState lerps camGame.zoom towards defaultCamZoom each frame,
	// so this value is what the camera holds between pulses.
	if (!camZoomApplied) {
		camZoomApplied = true;
		camZoomBase = PlayState.instance.defaultCamZoom;
		PlayState.instance.defaultCamZoom = camZoomBase + (scareTier - 2) * 0.0095;
	}

	// A glitch event rings out over ~1.2 s instead of snapping back instantly.
	var target:Float = 0.0;
	// Chart events are in song time; wall time includes the intro cutscene and
	// countdown, and would trigger the shader before the actual scare.
	var songSeconds:Float = Conductor != null ? Conductor.songPosition / 1000.0 : -1.0;
	for (t in glitchTimes) {
		var since:Float = songSeconds - t;
		if (since >= 0.0 && since < 1.4) {
			var amount:Float = 1.0 - since / 1.4;
			if (amount > target) target = amount;
		}
	}
	// 8/10 and up also twitches on every beat, so the picture never settles.
	if (scareTier >= 8 && Conductor != null && Conductor.crochet > 0 && songSeconds >= 0) {
		var phase:Float = (Conductor.songPosition % Conductor.crochet) / Conductor.crochet;
		var pulse:Float = 1.0 - phase;
		if (pulse * 0.30 > target) target = pulse * 0.30;
	}
	glitch = target;

	if (vhs == null && crt == null && crtHud == null) return;

	if (vhs != null) {
		shaderFloat('uTime', songClock);
		shaderFloat('uIntensity', vhsIntensity);
		shaderFloat('uAberration', 0.9 + 1.6 * vhsIntensity + 4.0 * glitch);
		shaderFloat('uScanline', 0.30 + 0.50 * vhsIntensity + 0.20 * glitch);
		shaderFloat('uGrain', 0.25 + 0.55 * vhsIntensity + 0.35 * glitch);
		shaderFloat('uVignette', 0.30 + 0.25 * vhsIntensity);
		shaderFloat('uGlitch', glitch);
	}

	// CRT ladder over the five songs: 2/10 (base 0) is a barely-there tube,
	// 4/10 (0.25) shows the scanlines, 6/10 (0.5) starts splitting channels,
	// 10/10 (1.0) is a broken set -- plus the event spikes on top.
	var base:Float = Math.min(1.0, (scareTier - 2) / 8.0);
	var aber:Float = 0.45 + 1.35 * base + 3.2 * glitch;
	var scan:Float = 0.15 + 0.15 * base;
	var grain:Float = 0.03 + 0.08 * base + 0.25 * glitch;
	var curve:Float = 0.022 + 0.028 * base;
	var vig:Float = 0.25 + 0.16 * base;

	setFloatOn(crt, 'uTime', songClock);
	setFloatOn(crt, 'iTime', songClock);
	setFloatOn(crt, 'uAberration', aber);
	setFloatOn(crt, 'uScanline', scan);
	setFloatOn(crt, 'uStatic', grain);
	setFloatOn(crt, 'uCurvature', curve);
	setFloatOn(crt, 'uVignette', vig);
	setFloatOn(crt, 'uGlitch', glitch);

	// HUD is intentionally spatially stable: no curvature or horizontal tears.
	// Subtle scanlines only, so note timing and edge-lane silhouettes stay clear.
	setFloatOn(crtHud, 'uTime', songClock);
	setFloatOn(crtHud, 'iTime', songClock);
	setFloatOn(crtHud, 'uAberration', 0.0);
	setFloatOn(crtHud, 'uScanline', scan * 0.35);
	setFloatOn(crtHud, 'uStatic', 0.0);
	setFloatOn(crtHud, 'uCurvature', 0.0);
	setFloatOn(crtHud, 'uVignette', 0.0);
	setFloatOn(crtHud, 'uGlitch', 0.0);

	// Inversion overlay fades out after an invert event.
	if (invertTimer > 0.0) {
		invertTimer -= elapsed;
		if (invertSpr != null) {
			invertSpr.visible = true;
			invertSpr.alpha = Math.max(0.0, invertTimer / 0.7) * 0.6;
		}
	} else if (invertSpr != null) {
		invertSpr.visible = false;
		invertSpr.alpha = 0.0;
	}
}

function onStrumCreation(event) {
	if (noteSkin == null) return;
	var path:String = 'game/notes/' + noteSkin;
	if (Assets.exists(Paths.image(path)))
		event.sprite = path;
}

/** Screen shake in pixels; FlxCamera.shake takes a fraction of the screen. */
function camShake(pixels:Float, seconds:Float) {
	var cam = PlayState.instance != null ? PlayState.instance.camGame : null;
	if (cam == null) return;
	cam.shake(pixels / 1000.0, seconds);
}

/** Zoom impulse; PlayState's per-frame lerp pulls it back to defaultCamZoom. */
function zoomPunch(amount:Float) {
	var cam = PlayState.instance != null ? PlayState.instance.camGame : null;
	if (cam == null) return;
	var ceiling:Float = PlayState.instance.defaultCamZoom + 0.018;
	if (cam.zoom < ceiling) cam.zoom = Math.min(ceiling, cam.zoom + amount);
}

// --------------------------------------------------------------------------- #
//  Hit response
//
//  Shipped songs already contain chart-matched Voices.ogg. Doubling them with
//  a second syllable on every hit crowds the mix and undermines miss muting;
//  retain the old samples only as a fallback for songs without a vocal stem.
//  A restrained, capped camera response makes a hit feel physical without
//  making fast patterns zoom indefinitely or changing note timing.
// --------------------------------------------------------------------------- #

var NOTE_DIRS:Array<String> = ['left', 'down', 'up', 'right'];

function onNoteHit(event) {
	if (event == null || event.note == null || event.cancelled) return;
	if (event.note.isSustainNote) return;

	var meta = PlayState.SONG != null ? PlayState.SONG.meta : null;
	if (meta != null && !meta.needsVoices) {
		var dir:String = NOTE_DIRS[event.direction % 4];
		if (event.player) FlxG.sound.play(Paths.sound('bf_note_' + dir), 0.32);
		else FlxG.sound.play(Paths.sound('trollge_note_' + dir), 0.28);
	}
	zoomPunch(event.player ? 0.0030 : 0.0012);
}

/** A small camera breath every fourth measure, bounded by zoomPunch. */
function measureHit(curMeasure) {
	if (curMeasure % 4 == 0) zoomPunch(0.004 + 0.0008 * scareTier);
}

function beatHit(curBeat) {
	// Camera: a small push on every beat once the song is properly scary, and a
	// restrained downbeat shake from 6/10 up. Everything scales with the tier,
	// so the last two songs physically feel different from the first one.
	if (scareTier >= 4) zoomPunch(0.0030 + 0.0006 * scareTier);
	// Reserve shake for downbeats: the contrast makes the impact more legible
	// than a constantly vibrating camera, especially in dense note sections.
	if (scareTier >= 6 && curBeat % 4 == 0)
		var shakePower:Float = scareTier >= 8 ? 30.0 : (scareTier >= 6 ? 16.0 : 6.0);
		camShake(shakePower, 0.12);

	// Random static flicker — scarier songs never fully settle.
	if (staticSpr == null) return;
	var chance:Float = scareTier >= 8 ? 35.0 : (scareTier >= 6 ? 20.0 : 8.0);
	if (FlxG.random.bool(chance)) {
		var peak:Float = scareTier >= 8 ? 0.40 : (scareTier >= 6 ? 0.26 : 0.14);
		FlxTween.cancelTweensOf(staticSpr);
		FlxTween.tween(staticSpr, {alpha: peak}, 0.05, {
			onComplete: function(_) FlxTween.tween(staticSpr, {alpha: 0.0}, 0.20)
		});
	}
}

/** Full-screen color inversion (Trollge Files-style negative flash). */
function invertScreen(a = null):Void {
	var ps = PlayState.instance;
	if (ps == null || invertSpr == null) return;
	invertTimer = 0.7;
	if (invertSpr != null) {
		invertSpr.visible = true;
		invertSpr.alpha = 0.6;
	}
	ps.camGame.flash(FlxColor.WHITE, 0.08);
	FlxG.sound.play(Paths.sound('trollge_invert'), 0.8);
	shake(12.0 + scareTier * 2.0, 0.6);
}

function shake(power:Float, duration:Float) {
	var ps = PlayState.instance;
	if (ps == null) return;
	ps.camGame.shake(power / 1000.0, duration);
}
