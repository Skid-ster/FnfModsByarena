// ===========================================================================
//  trollge.hx -- stage script
//
//  One stage, three moods: the backdrop, the arrow skin and the amount of screen
//  corruption are picked from the song's scare tier ("Trolling" 2/10,
//  "It's Getting Dark" 4/10, "Super Scary Trollge" 7/10).
//
//  It also owns the full-screen shader (shaders/trollge_vhs.frag): a VHS grade
//  applied to camGame, cranked up per scare tier and punched by the story events.
// ===========================================================================

var scareTier:Int = 1;
var staticSpr:FlxSprite = null;
var noteSkin:String = null;

var vhs = null;              // FunkinShader (Dynamic: HScript resolves it at runtime)
var vhsFilter = null;
var vhsIntensity:Float = 0.35;
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
	noteSkin = scareTier >= 7 ? 'corrupt' : (scareTier >= 4 ? 'shadow' : null);

	// Screen grade: 2/10 is a light tape look, 7/10 is a failing VHS deck.
	vhsIntensity = scareTier >= 7 ? 1.0 : (scareTier >= 4 ? 0.62 : 0.35);
	setupVhs();

	// Story events that should punch the shader, read straight from the chart.
	glitchTimes = [];
	if (PlayState.SONG != null && PlayState.SONG.events != null) {
		for (e in PlayState.SONG.events) {
			if (e.name != 'HScript Call' || e.params == null || e.params.length == 0) continue;
			var fn:String = Std.string(e.params[0]);
			if (fn == 'trollgeJumpScare' || fn == 'trollgeInvert' || fn == 'trollgePhase2'
				|| fn == 'trollgeDistort' || fn == 'trollgeStatic' || fn == 'trollgeFinalForm')
				glitchTimes.push(e.time / 1000.0);
		}
	}

	// Swap in the nastier backdrop once the song earns it.
	if (scareTier >= 4 && bg != null) {
		var key:String = scareTier >= 7 ? 'stages/trollge/bg_nightmare' : 'stages/trollge/bg_scary';
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

function setupVhs() {
	var shaderClass = Type.resolveClass('funkin.backend.shaders.FunkinShader');
	var filterClass = Type.resolveClass('openfl.filters.ShaderFilter');
	if (shaderClass == null || filterClass == null) return;
	try {
		vhs = shaderClass.fromFile('trollge_vhs');
	} catch (e) {
		vhs = null;
		return;
	}
	if (vhs == null) return;
	vhsFilter = Type.createInstance(filterClass, [vhs]);
	if (PlayState.instance != null && PlayState.instance.camGame != null)
		PlayState.instance.camGame.filters = [vhsFilter];
}

function shaderFloat(name:String, value:Float) {
	if (vhs == null) return;
	try {
		vhs.setFloat(name, value);
	} catch (e) {}
}

function update(elapsed:Float) {
	songClock += elapsed;

	// A glitch event rings out over ~1.2 s instead of snapping back instantly.
	var target:Float = 0.0;
	for (t in glitchTimes) {
		var since:Float = songClock - t;
		if (since >= 0.0 && since < 1.2) {
			var amount:Float = 1.0 - since / 1.2;
			if (amount > target) target = amount;
		}
	}
	// Tier 7 also twitches on every beat, so the picture never settles.
	if (scareTier >= 7 && Conductor != null) {
		var phase:Float = (Conductor.songPosition / 1000.0) % 1.0;
		var pulse:Float = 1.0 - phase;
		if (pulse * 0.22 > target) target = pulse * 0.22;
	}
	glitch = target;

	if (vhs == null) return;
	shaderFloat('uTime', songClock);
	shaderFloat('uIntensity', vhsIntensity);
	shaderFloat('uAberration', 0.7 + 1.3 * vhsIntensity + 3.0 * glitch);
	shaderFloat('uScanline', 0.25 + 0.45 * vhsIntensity);
	shaderFloat('uGrain', 0.2 + 0.5 * vhsIntensity + 0.3 * glitch);
	shaderFloat('uVignette', 0.35 + 0.45 * vhsIntensity);
	shaderFloat('uGlitch', glitch);
}

function onStrumCreation(event) {
	if (noteSkin == null) return;
	var path:String = 'game/notes/' + noteSkin;
	if (Assets.exists(Paths.image(path)))
		event.sprite = path;
}

function beatHit(curBeat) {
	// Ambient dread per tier (FlxG.random.bool takes a 0..1 probability).
	if (staticSpr == null) return;
	var chance:Float = scareTier >= 7 ? 0.30 : (scareTier >= 4 ? 0.12 : 0.04);
	if (FlxG.random.bool(chance)) {
		var peak:Float = scareTier >= 7 ? 0.35 : 0.15;
		FlxTween.cancelTweensOf(staticSpr);
		FlxTween.tween(staticSpr, {alpha: peak}, 0.06, {
			onComplete: function(_) FlxTween.tween(staticSpr, {alpha: 0.0}, 0.22)
		});
	}
}
