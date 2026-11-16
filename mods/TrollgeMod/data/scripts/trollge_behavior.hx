// ===========================================================================
//  trollge_behavior.hx -- character behaviour for Trollge / Trollge (phase 2)
//
//  Loaded automatically by every phase of the character
//  (data/characters/trollge.xml, trollge_glitch.xml, trollge_static.xml,
//  trollge_final.xml, trollge_sad.xml) through:
//      <extension script="trollge_behavior"/>
//
//  `this` is the Character that loaded the script (base-game convention, see
//  assets/data/characters/spirit.hx).
// ===========================================================================

/** Scare tier of the song currently playing (2, 4, 6, 8 or 10). */
var scareTier:Int = 1;

/** 0..1, drives the red flicker on the scary tiers. */
var flash:Float = 0.0;

function readScareTier():Void {
	var meta = PlayState.SONG != null ? PlayState.SONG.meta : null;
	var cv = meta != null ? meta.customValues : null;
	if (cv != null && cv.scareTier != null)
		scareTier = Std.int(cv.scareTier);
}

// Character scripts are attached while the Character is still being built, so a
// `create()` hook here would never fire (the pack's create pass already ran).
// Initialise at load time, and refresh in postCreate as a safety net.
readScareTier();

function postCreate() {
	readScareTier();
}

function beatHit(curBeat) {
	// 2/10 barely flickers, 10/10 flickers all the time. Escalation!
	if (scareTier >= 8 && curBeat % 2 == 0) flash = 1.0;
	else if (scareTier >= 6 && curBeat % 3 == 0) flash = 0.75;
	else if (scareTier >= 4 && curBeat % 4 == 0) flash = 0.55;
}

function onDance(event) {
	// Even the idle dance gets twitchy once things go bad.
	if (scareTier >= 8 && FlxG.random.bool(18.0)) {
		// Character.dance() otherwise immediately overwrites the chosen anim.
		event.cancel();
		this.playAnim('laugh', true, "DANCE");
	}
}

function postUpdate(elapsed) {
	if (flash > 0.0) {
		flash = Math.max(0.0, flash - elapsed * 3.2);
		var tint:Int = 255 - Std.int(70 * flash);
		this.color = FlxColor.fromRGB(255, tint, tint);
	} else {
		this.color = 0xFFFFFFFF;
	}

	// Creepy sway: only on the scariest songs, and tiny enough not to look broken.
	if (scareTier >= 8)
		this.angle = Math.sin(Conductor.songPosition / 220.0) * (scareTier >= 10 ? 1.3 : 0.8);
	else
		this.angle = 0.0;
}
