// ===========================================================================
//  trollge.hx -- stage script
//
//  One stage, three moods: the backdrop and the amount of screen corruption are
//  picked from the song's scare tier ("Trolling" 2/10, "It's Getting Dark" 4/10,
//  "Super Scary Trollge" 7/10).
// ===========================================================================

var scareTier:Int = 1;
var staticSpr:FlxSprite = null;
var noteSkin:String = null;

function create() {
	var meta = PlayState.SONG != null ? PlayState.SONG.meta : null;
	var cv = meta != null ? meta.customValues : null;
	if (cv != null && cv.scareTier != null)
		scareTier = Std.int(cv.scareTier);

	// Arrow skin: notes get theirs from the chart's noteTypes, but strums always
	// default to game/notes/default, so mirror the song's skin onto them here.
	noteSkin = scareTier >= 7 ? 'corrupt' : (scareTier >= 4 ? 'shadow' : null);

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
