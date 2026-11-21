#pragma header

// ===========================================================================
//  trollge_vhs.frag -- the mod's full-screen horror grade.
//  Trollge Files-style: heavy chromatic aberration, VHS tracking wobble,
//  scanlines, grain, halation bloom, vignette, and event-driven glitch spikes.
//  Attached to camGame by data/stages/trollge.hx.
//
//  Uniforms (set from HScript in trollge.hx):
//      uTime        seconds
//      uIntensity   0..1, scaled by scare tier
//      uAberration  channel split in pixels (radial chromatic aberration)
//      uScanline    0..1
//      uGrain       0..1
//      uVignette    0..1
//      uGlitch      0..1, spiked by story events (jumpscare / distort / invert)
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
    vec2 centred = uv - vec2(0.5);

    // ---------------------------------------------------------------- VHS wobble
    // Whole horizontal tracking bands drift left/right, harder during glitch.
    float band = floor(uv.y * 40.0);
    float bandNoise = hash21(vec2(band, floor(uTime * 18.0)));
    uv.x += (bandNoise - 0.5) * (0.015 + 0.08 * uGlitch) * (0.4 + uIntensity);

    // Vertical roll — the whole picture sinks and rises like a bad tape.
    uv.y += sin(uTime * 3.0 + uGlitch * 4.0) * 0.006 * (0.3 + uIntensity + uGlitch);

    // ---------------------------------------------------------------- Chromatic aberration
    // Radial channel split — red and blue pulled apart from the centre,
    // driven hard by glitch and scare intensity. This is the core "wrong"
    // look of a dying tape / corrupted signal.
    float ab = (uAberration / 520.0) * (1.0 + uGlitch * 3.0) * (0.5 + uIntensity);
    vec2 dir = centred * ab;
    vec4 col;
    col.r = sampleClamped(uv + dir).r;
    col.g = sampleClamped(uv).g;
    col.b = sampleClamped(uv - dir).b;
    col.a = sampleClamped(uv).a;

    // ---------------------------------------------------------------- Halation bloom
    // 5-tap highlight glow — bright parts bleed like an over-driven CRT.
    vec3 glow = vec3(0.0);
    float threshold = 0.58 - 0.10 * uIntensity;
    glow += max(sampleClamped(uv + vec2(0.003, 0.0)).rgb - threshold, vec3(0.0));
    glow += max(sampleClamped(uv - vec2(0.003, 0.0)).rgb - threshold, vec3(0.0));
    glow += max(sampleClamped(uv + vec2(0.0, 0.003)).rgb - threshold, vec3(0.0));
    glow += max(sampleClamped(uv - vec2(0.0, 0.003)).rgb - threshold, vec3(0.0));
    glow += max(sampleClamped(uv + vec2(0.0021, 0.0021)).rgb - threshold, vec3(0.0));
    col.rgb += glow * (0.28 + 0.40 * uIntensity + 0.30 * uGlitch);

    // ---------------------------------------------------------------- Scanlines
    // Fine, drifting scanline grid, subtly brighter between the lines.
    float scan = sin(uv.y * 760.0 + uTime * 2.0) * 0.5 + 0.5;
    col.rgb *= mix(1.0, 0.84 + 0.16 * scan, uScanline);

    // ---------------------------------------------------------------- Film grain / static
    float grain = hash21(uv * vec2(1280.0, 720.0) + vec2(uTime * 71.0, uTime * 43.0));
    col.rgb += (grain - 0.5) * (uGrain * 0.11 + uGlitch * 0.14);

    // ---------------------------------------------------------------- Vignette + cold corners
    float d = distance(uv, vec2(0.5));
    float vig = 1.0 - smoothstep(0.16, 0.92, d);
    col.rgb *= mix(1.0, vig, uVignette);
    col.rgb = mix(col.rgb, col.rgb * vec3(0.90, 0.94, 1.08), (1.0 - vig) * uIntensity * 0.8);

    // ---------------------------------------------------------------- Contrast / saturation
    col.rgb = (col.rgb - vec3(0.5)) * (1.0 + 0.06 * uIntensity) + vec3(0.5);
    float luma = dot(col.rgb, vec3(0.299, 0.587, 0.114));
    col.rgb = mix(vec3(luma), col.rgb, 1.0 + 0.26 * uIntensity);

    // ---------------------------------------------------------------- Tape dropout lines
    // Brief horizontal white/blue scan failures during glitch spikes.
    float dropoutLine = step(0.975, hash21(vec2(floor(uv.y * 200.0), floor(uTime * 14.0)))) * uGlitch;
    col.rgb = mix(col.rgb, vec3(0.80, 0.86, 1.0), dropoutLine * 0.6);

    // ---------------------------------------------------------------- Glitch block shift
    // During a heavy event, whole blocks of the image slide sideways.
    if (uGlitch > 0.35) {
        float block = floor(uv.y * 6.0);
        float blockShift = hash21(vec2(block, floor(uTime * 24.0))) - 0.5;
        float shiftAmount = blockShift * 0.035 * uGlitch;
        vec4 shifted = sampleClamped(uv + vec2(shiftAmount, 0.0));
        col.rgb = mix(col.rgb, shifted.rgb, uGlitch * 0.5);
    }

    gl_FragColor = vec4(clamp(col.rgb, vec3(0.0), vec3(col.a)), col.a);
}
