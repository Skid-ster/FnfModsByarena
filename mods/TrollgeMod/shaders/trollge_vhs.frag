#pragma header

// ===========================================================================
//  trollge_vhs.frag -- the mod's full-screen grade.
//
//  Attached to camGame by data/stages/trollge.hx (needs a GPU + the engine's
//  shader compat layer, so the stage script disables it silently if either is
//  missing).
//
//  What it does, in order: banded VHS wobble, chromatic aberration, scanlines,
//  film grain, vignette, slight saturation/contrast lift. Every coordinate is
//  clamped to the texture, so the image never smears or wraps at the screen
//  edge -- offsets used to sample past 0..1 and the borders clipped.
//
//  Uniforms are set from HScript:
//      uTime        seconds
//      uIntensity   0..1, scaled by the song's scare tier
//      uAberration  channel split in pixels
//      uScanline    0..1
//      uGrain       0..1
//      uVignette    0..1
//      uGlitch      0..1, spiked by story events
// ===========================================================================

uniform float uTime;
uniform float uIntensity;
uniform float uAberration;
uniform float uScanline;
uniform float uGrain;
uniform float uVignette;
uniform float uGlitch;

float hash21(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

vec4 sampleClamped(vec2 uv) {
	return textureCam(bitmap, clamp(uv, vec2(0.0005), vec2(0.9995)));
}

void main() {
	vec2 uv = getCamPos(openfl_TextureCoordv);

	// VHS wobble: whole horizontal bands slide, harder during a glitch.
	float band = floor(uv.y * 48.0);
	float bandNoise = hash21(vec2(band, floor(uTime * 15.0)));
	uv.x += (bandNoise - 0.5) * (0.012 + 0.05 * uGlitch) * (0.35 + uIntensity);

	// Chromatic aberration, radial, also clamped at the borders.
	vec2 dir = (uv - vec2(0.5)) * (uAberration / 480.0) * (1.0 + uGlitch * 2.0);
	float alpha = sampleClamped(uv).a;
	vec3 col;
	col.r = sampleClamped(uv + dir).r;
	col.g = sampleClamped(uv).g;
	col.b = sampleClamped(uv - dir).b;

	// Halation: a cheap 5-tap glow on the bright parts (no extra pass, no blur
	// texture) so highlights bloom like an over-driven CRT.
	vec3 glow = vec3(0.0);
	glow += max(sampleClamped(uv + vec2(0.0028, 0.0)).rgb - 0.62, vec3(0.0));
	glow += max(sampleClamped(uv - vec2(0.0028, 0.0)).rgb - 0.62, vec3(0.0));
	glow += max(sampleClamped(uv + vec2(0.0, 0.0028)).rgb - 0.62, vec3(0.0));
	glow += max(sampleClamped(uv - vec2(0.0, 0.0028)).rgb - 0.62, vec3(0.0));
	col += glow * (0.22 + 0.30 * uIntensity);

	// Scanlines: fine, slow-drifting, subtly brighter in the middle.
	float scan = sin(uv.y * 720.0 + uTime * 1.6) * 0.5 + 0.5;
	col *= mix(1.0, 0.88 + 0.12 * scan, uScanline);

	// Film grain.
	float grain = hash21(uv * vec2(1280.0, 720.0) + vec2(uTime * 61.0, uTime * 37.0));
	col += (grain - 0.5) * (uGrain * 0.09);

	// Vignette + a cold cast in the corners so the frame reads as a recording.
	float d = distance(uv, vec2(0.5));
	float vig = 1.0 - smoothstep(0.18, 0.95, d);
	col *= mix(1.0, vig, uVignette);
	col = mix(col, col * vec3(0.93, 0.97, 1.06), (1.0 - vig) * uIntensity * 0.7);

	// Gentle contrast and saturation: preserve detail in already-dark artwork.
	col = (col - vec3(0.5)) * (1.0 + 0.04 * uIntensity) + vec3(0.5);
	float luma = dot(col, vec3(0.299, 0.587, 0.114));
	col = mix(vec3(luma), col, 1.0 + 0.22 * uIntensity);

	// Glitch: occasional tape dropout lines.
	float dropoutLine = step(0.985, hash21(vec2(floor(uv.y * 180.0), floor(uTime * 12.0)))) * uGlitch;
	col = mix(col, vec3(0.85, 0.9, 1.0), dropoutLine * 0.5);

	// textureCam already applied the camera alpha and premultiplied RGB.
	gl_FragColor = vec4(clamp(col, vec3(0.0), vec3(alpha)), alpha);
}
