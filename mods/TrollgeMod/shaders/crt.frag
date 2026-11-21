#pragma header

// ===========================================================================
//  crt.frag -- the mod's CRT pass, Trollge Files-style.
//  Barrel curvature, heavy RGB chromatic aberration, horizontal tear bands,
//  scanlines, animated static grain, vignette, and event-driven distortion.
//  camGame gets trollge_vhs + crt; camHUD gets a weak crt copy so notes stay
//  readable while the game picture falls apart.
//
//  Uniforms (set from HScript in trollge.hx):
//      uTime       seconds
//      iTime       alias for the same clock
//      uAberration channel split, in pixels
//      uScanline   0..1 scanline depth
//      uStatic     0..1 grain amount
//      uCurvature  0..0.08 barrel amount
//      uVignette   0..1 corner darkening
//      uGlitch     0..1 event spike (trollgeDistort / trollgeStatic / ...)
// ===========================================================================

uniform float uTime;
uniform float iTime;
uniform float uAberration;
uniform float uScanline;
uniform float uStatic;
uniform float uCurvature;
uniform float uVignette;
uniform float uGlitch;
// OpenFL alpha: textureCam premultiplies alpha into RGB; sample via openfl_Alphav convention for HUD stability.

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453123);
}

void main() {
    float t = max(uTime, iTime);

    // All warp maths in camera space, matching textureCam expectations.
    vec2 uv = getCamPos(openfl_TextureCoordv);
    vec2 centred = uv - vec2(0.5);
    float r2 = dot(centred, centred);

    // ---------------------------------------------------------------- Barrel curvature
    // Push samples outwards from centre; edges bulge like a real tube.
    // Outside the tube = transparent so the game shows through corners.
    vec2 warped = uv + centred * r2 * uCurvature * 5.0;
    if (warped.x < 0.0 || warped.x > 1.0 || warped.y < 0.0 || warped.y > 1.0) {
        gl_FragColor = vec4(0.0);
        return;
    }

    // ---------------------------------------------------------------- Tear bands
    // Horizontal slices slide sideways while a glitch is up — the classic
    // corrupted-VHS / dying-monitor look.
    float bandSeed = floor(warped.y * 110.0);
    float bandNoise = hash(vec2(bandSeed, floor(t * 16.0)));
    float band = step(1.0 - uGlitch * 0.45, bandNoise);
    float slide = (hash(vec2(bandSeed, t)) - 0.5) * 0.08 * uGlitch * band;
    vec2 suv = warped + vec2(slide, 0.0);

    // ---------------------------------------------------------------- Chromatic aberration
    // One fetch per channel, split hard — this is what makes it look broken.
    vec2 texel = 1.0 / openfl_TextureSize;
    float ab = uAberration * texel.x * (1.0 + uGlitch * 2.0);
    vec4 col;
    col.r = textureCam(bitmap, suv + vec2(ab, 0.0)).r;
    col.g = textureCam(bitmap, suv).g;
    col.b = textureCam(bitmap, suv - vec2(ab, 0.0)).b;
    col.a = textureCam(bitmap, suv).a;

    // ---------------------------------------------------------------- Scanlines
    // Stable dark rows every ~2.5 output pixels.
    float row = openfl_TextureCoordv.y * openfl_TextureSize.y;
    float scan = 0.5 + 0.5 * sin(row * 2.513274);
    col.rgb *= mix(1.0, 0.68 + 0.32 * scan, uScanline);

    // ---------------------------------------------------------------- Static grain
    // Animated per-frame grain, stronger during glitches.
    float gr = hash(uv * openfl_TextureSize + vec2(t * 101.7, t * 47.3));
    col.rgb += (gr - 0.5) * uStatic * 0.62 * col.a;

    // ---------------------------------------------------------------- Vignette
    // Corners go dark first, on top of the curvature.
    float vig = 1.0 - uVignette * smoothstep(0.10, 0.70, r2 * 2.2);
    col.rgb *= vig;

    // textureCam returns premultiplied pixels with alpha applied.
    col.a = clamp(col.a, 0.0, 1.0);
    // (OpenFL convention: alpha is premultiplied into RGB by textureCam.)
    col.rgb = clamp(col.rgb, vec3(0.0), vec3(col.a));

    gl_FragColor = col;
}
