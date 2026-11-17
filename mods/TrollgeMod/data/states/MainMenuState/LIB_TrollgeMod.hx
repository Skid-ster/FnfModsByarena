// Layout only: native MainMenuState retains navigation, focus and transitions.
// Codename loads this script by mod library name (install as TrollgeMod).
var titleArt:FlxSprite = null;

function positionMenu() {
    var items = Reflect.field(state, 'menuItems');
    if (items == null || items.members == null) return;
    var scale:Float = Math.min(FlxG.width / 1280.0, FlxG.height / 720.0);
    for (i in 0...items.members.length) {
        var item = items.members[i];
        if (item == null) continue;
        item.scale.set(scale, scale);
        item.updateHitbox();
        item.x = FlxG.width * 0.065;
        item.y = FlxG.height * (0.50 + i * 0.070);
    }
}

function postCreate() {
    // If a build does not expose the native group, leave its menu alone.
    var items = Reflect.field(state, 'menuItems');
    if (items == null || items.members == null) return;
    try { Reflect.setField(state, 'forceCenterX', false); } catch (e) {}
    titleArt = new FlxSprite(FlxG.width * 0.072, FlxG.height * 0.205);
    titleArt.loadGraphic(Paths.image('menus/title_logo'));
    var scale:Float = Math.min(FlxG.width / 1280.0, FlxG.height / 720.0);
    titleArt.scale.set(scale, scale);
    titleArt.updateHitbox();
    titleArt.scrollFactor.set(0, 0);
    titleArt.antialiasing = true;
    state.add(titleArt);
    positionMenu();
}

// Some builds recenter rows in update; correct them after the native update.
function postUpdate(elapsed:Float) {
    positionMenu();
}
