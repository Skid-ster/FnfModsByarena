#pragma header

// ===========================================================================
//  crt.frag -- the mod's CRT pass.
//
//  Attached by data/stages/trollge.hx on top of the VHS grade: camGame gets
//  trollge_vhs + crt, camHUD gets crt on its own (weaker) copy. Everything is
//  scaled by the song's scare tier and punched by the story events, so 2/10 is
//  a gentle tube and 10/10 is a deck that is about to die.
//
//  What it does, in order:
//      1. barrel curvature -- the screen bulges like a real tube
//      2. RGB chromatic aberration -- red and blue sampled apart
//      3. horizontal tear bands -- only while uGlitch is up
//      4. horizontal scanlines
//      5. animated static grain
//      6. corner vignette
//
//  OpenFL/Flixel conventions: `#pragma header` pulls in the shader preamble,
//  `bitmap` is the sampler; camera filters fetch with `textureCam`, and
//  `openfl_Alphav` is the sprite alpha the engine expects us to multiply by.
//
//  Uniforms are written from HScript with `setFloat`:
//      uTime       seconds since the song started
//      iTime       alias for the same clock (either one alone is enough)
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

float hash(vec2 p)
{
    return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453123);
}

void main()
{
    float t = max(uTime, iTime);

    vec2 uv = openfl_TextureCoordv;
    vec2 centred = uv - vec2(0.5);
    float r2 = dot(centred, centred);

    // 1. Barrel curvature: push samples outwards from the centre, more at the
    //    edges. Everything outside the tube is written as black, the way a real
    //    curved screen shows nothing past its bezel.
    vec2 warped = uv + centred * r2 * uCurvature * 4.0;
    if (warped.x < 0.0 || warped.x > 1.0 || warped.y < 0.0 || warped.y > 1.0)
    {
        gl_FragColor = vec4(0.0, 0.0, 0.0, openfl_Alphav);
        return;
    }

    // 3. Tear bands: a few horizontal slices slide sideways while a glitch is up.
    float bandSeed = floor(warped.y * 90.0);
    float bandNoise = hash(vec2(bandSeed, floor(t * 14.0)));
    float band = step(1.0 - uGlitch * 0.35, bandNoise);
    float slide = (hash(vec2(bandSeed, t)) - 0.5) * 0.05 * uGlitch * band;
    vec2 suv = getCamPos(uv) + (warped - uv) + vec2(slide, 0.0);

    // 2. Chromatic aberration: one texture fetch per channel, split in pixels.
    vec2 texel = 1.0 / openfl_TextureSize;
    float ab = uAberration * texel.x;
    float gr = 0.0;

    vec4 col;
    col.r = textureCam(bitmap, suv + vec2(ab, 0.0)).r;
    col.g = textureCam(bitmap, suv).g;
    col.b = textureCam(bitmap, suv - vec2(ab, 0.0)).b;
    col.a = textureCam(bitmap, suv).a;

    // 4. Scanlines: one dark row every ~2.5 pixels of the *output*, which keeps
    //    the pattern stable no matter how the game is scaled.
    float row = openfl_TextureCoordv.y * openfl_TextureSize.y;
    float scan = 0.5 + 0.5 * sin(row * 2.513274);          // 2*pi/2.5 px
    col.rgb *= mix(1.0, 0.72 + 0.28 * scan, uScanline);

    // 5. Static grain, animated per frame.
    gr = hash(uv * openfl_TextureSize + vec2(t * 91.7, t * 37.3));
    col.rgb += (gr - 0.5) * uStatic * 0.55;

    // 6. Vignette, on top of the curvature so the corners go first.
    float vig = 1.0 - uVignette * smoothstep(0.12, 0.75, r2 * 2.0);
    col.rgb *= vig;

    col.rgb = clamp(col.rgb, vec3(0.0), vec3(1.0));
    col.a = clamp(col.a, 0.0, 1.0) * openfl_Alphav;

    gl_FragColor = col;
}
