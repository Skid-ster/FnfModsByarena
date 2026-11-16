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
//  weaker strength. Both are cranked up per scare tier and punched by the story
//  events. Alongside them: the camera work (zoom, shake) and the per-character
//  note-hit voices.
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

	// Camera zoom is applied on the first update, not here: the stage script is
	// created before the stage xml attributes are parsed, so defaultCamZoom still
	// holds the previous song's value at this point.

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

	// Full-screen static that the song script can flare up.
	staticSpr = new FlxSprite(0, 0).loadGraphic(Paths.image('trollge_static'));
	staticSpr.cameras = [PlayState.instance.camHUD];
	staticSpr.scrollFactor.set();
	staticSpr.setGraphicSize(FlxG.width, FlxG.height);
	staticSpr.updateHitbox();
	staticSpr.screenCenter();
	staticSpr.alpha = 0.0;
	staticSpr.blend = BlendMode.ADD;
	staticSpr.antialiasing = false;
	PlayState.instance.add(staticSpr);
}

function setupShaders() {
	var shaderClass = Type.resolveClass('funkin.backend.shaders.FunkinShader');
	var filterClass = Type.resolveClass('openfl.filters.ShaderFilter');
	if (shaderClass == null || filterClass == null) return;

	// 1. VHS grade (shaders/trollge_vhs.frag).
	try {
		vhs = shaderClass.fromFile('trollge_vhs');
	} catch (e) {
		vhs = null;
	}
	if (vhs != null) {
		try {
			vhsFilter = Type.createInstance(filterClass, [vhs]);
		} catch (e) {
			vhsFilter = null;
		}
	}

	// 2. CRT pass (shaders/crt.frag), game camera.
	try {
		crt = shaderClass.fromFile('crt');
	} catch (e) {
		crt = null;
	}
	if (crt != null) {
		try {
			crtFilter = Type.createInstance(filterClass, [crt]);
		} catch (e) {
			crtFilter = null;
		}
	}

	// 3. CRT pass, HUD camera (its own instance so the two can differ).
	try {
		crtHud = shaderClass.fromFile('crt');
	} catch (e) {
		crtHud = null;
	}
	if (crtHud != null) {
		try {
			crtHudFilter = Type.createInstance(filterClass, [crtHud]);
		} catch (e) {
			crtHudFilter = null;
		}
	}

	var ps = PlayState.instance;
	if (ps == null) return;

	// Filters are attached last, and only if at least one survived: a chip that
	// cannot compile the shader should cost the effect, never the song.
	if (ps.camGame != null) {
		var gameFilters = [];
		if (vhsFilter != null) gameFilters.push(vhsFilter);
		if (crtFilter != null) gameFilters.push(crtFilter);
		if (gameFilters.length > 0) {
			try {
				ps.camGame.filters = gameFilters;
			} catch (e) {}
		}
	}
	if (ps.camHUD != null && crtHudFilter != null) {
		try {
			ps.camHUD.filters = [crtHudFilter];
		} catch (e) {}
	}
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
		if (since >= 0.0 && since < 1.2) {
			var amount:Float = 1.0 - since / 1.2;
			if (amount > target) target = amount;
		}
	}
	// 8/10 and up also twitches on every beat, so the picture never settles.
	if (scareTier >= 8 && Conductor != null && Conductor.crochet > 0 && songSeconds >= 0) {
		var phase:Float = (Conductor.songPosition % Conductor.crochet) / Conductor.crochet;
		var pulse:Float = 1.0 - phase;
		if (pulse * 0.22 > target) target = pulse * 0.22;
	}
	glitch = target;

	if (vhs == null && crt == null && crtHud == null) return;

	if (vhs != null) {
		shaderFloat('uTime', songClock);
		shaderFloat('uIntensity', vhsIntensity);
		shaderFloat('uAberration', 0.7 + 1.3 * vhsIntensity + 3.0 * glitch);
		shaderFloat('uScanline', 0.25 + 0.45 * vhsIntensity);
		shaderFloat('uGrain', 0.2 + 0.5 * vhsIntensity + 0.3 * glitch);
		shaderFloat('uVignette', 0.35 + 0.45 * vhsIntensity);
		shaderFloat('uGlitch', glitch);
	}

	// CRT ladder over the five songs: 2/10 (base 0) is a barely-there tube,
	// 4/10 (0.25) shows the scanlines, 6/10 (0.5) starts splitting channels,
	// 10/10 (1.0) is a broken set -- plus the event spikes on top.
	var base:Float = Math.min(1.0, (scareTier - 2) / 8.0);
	var aber:Float = 0.35 + 1.15 * base + 2.6 * glitch;
	var scan:Float = 0.12 + 0.12 * base;
	var grain:Float = 0.02 + 0.06 * base + 0.20 * glitch;
	var curve:Float = 0.018 + 0.022 * base;
	var vig:Float = 0.34 + 0.26 * base;

	setFloatOn(crt, 'uTime', songClock);
	setFloatOn(crt, 'iTime', songClock);
	setFloatOn(crt, 'uAberration', aber);
	setFloatOn(crt, 'uScanline', scan);
	setFloatOn(crt, 'uStatic', grain);
	setFloatOn(crt, 'uCurvature', curve);
	setFloatOn(crt, 'uVignette', vig);
	setFloatOn(crt, 'uGlitch', glitch);

	// HUD: about 60% of it, and a much smaller channel split, so a combobreak
	// message never becomes the hard part of reading the screen.
	setFloatOn(crtHud, 'uTime', songClock);
	setFloatOn(crtHud, 'iTime', songClock);
	setFloatOn(crtHud, 'uAberration', aber * 0.45);
	setFloatOn(crtHud, 'uScanline', scan * 0.6);
	setFloatOn(crtHud, 'uStatic', grain * 0.5);
	setFloatOn(crtHud, 'uCurvature', curve * 0.5);
	setFloatOn(crtHud, 'uVignette', vig * 0.55);
	setFloatOn(crtHud, 'uGlitch', glitch * 0.5);
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
	cam.zoom += amount;
}

// --------------------------------------------------------------------------- #
//  Note-hit voices
//
//  The engine plays nothing when a note is hit (only miss sounds), so both sides
//  were silently miming. Every hit now plays that character's own syllable, and
//  the pitch follows the arrow: up highest, down lowest. The player's hit also
//  gives the camera a tiny push in, which is what makes a clean section feel
//  like it is being played rather than watched.
// --------------------------------------------------------------------------- #

var NOTE_DIRS:Array<String> = ['left', 'down', 'up', 'right'];

function onNoteHit(event) {
	if (event == null || event.note == null) return;
	if (event.note.isSustainNote) return;          // holds are not new notes

	var dir:String = NOTE_DIRS[event.direction % 4];
	if (event.player) {
		FlxG.sound.play(Paths.sound('bf_note_' + dir), 0.55);
		zoomPunch(0.0035);
	} else {
		FlxG.sound.play(Paths.sound('trollge_note_' + dir), 0.50);
		zoomPunch(0.0015);
	}
}

/** The camera breathes in on every fourth measure. */
function measureHit(curMeasure) {
	if (curMeasure % 4 == 0) zoomPunch(0.004 + 0.001 * scareTier);
}

function beatHit(curBeat) {
	// Camera: a small push on every beat once the song is properly scary, and a
	// barely-there shake from 6/10 up. Everything scales with the tier, so the
	// last two songs physically feel different from the first one.
	if (scareTier >= 4) zoomPunch(0.0022 + 0.0004 * scareTier);
	if (scareTier >= 6) camShake(1.2 + 0.35 * scareTier, 0.09);
	if (scareTier >= 10 && curBeat % 4 == 0) camShake(4.0, 0.22);

	// FlxRandom.bool takes a percentage in the range 0..100.
	if (staticSpr == null) return;
	var chance:Float = scareTier >= 8 ? 30.0 : (scareTier >= 6 ? 16.0 : 6.0);
	if (FlxG.random.bool(chance)) {
		var peak:Float = scareTier >= 8 ? 0.35 : (scareTier >= 6 ? 0.22 : 0.12);
		FlxTween.cancelTweensOf(staticSpr);
		FlxTween.tween(staticSpr, {alpha: peak}, 0.06, {
			onComplete: function(_) FlxTween.tween(staticSpr, {alpha: 0.0}, 0.22)
		});
	}
}
