# Horror UI references and design decisions

This is a selective study, not a ranking of the “best” horror UI. The assets in
this mod are newly generated; no artwork, logos, fonts, code, or audio from the
referenced games was copied. The user later supplied a separate cinematic menu
reference image: the current menu was rebuilt to follow its left-side title and
navigation, right-side figure and red/cyan corridor lighting. The Trollge scene
in `art_src/menu_scene.png` was AI-generated using that reference and the mod's
own character as visual inputs; no reference screenshot is shipped.

## References

- **Alien: Isolation — used technology as a consistent visual language.**
  [MCV/DEVELOP's report from the Creative Assembly presentation](https://mcvuk.com/development-news/18-things-we-learned-about-alien-isolation-last-night/)
  describes using VHS and Betamax to make worn recordings, lo-fi equipment,
  and an uncluttered HUD. We took the *idea* of an aged transmission console,
  not its exact colours, layouts, or motion tracker. The Trollge version uses
  a muted warm-red/charcoal palette and clipped casing corners in the countdown
  and health frame. Gameplay-critical information remains on the normal FNF
  HUD, not hidden in a diegetic object.
- **Alien: Isolation — retro style without retro usability.** [Game Developer's
  UI case study](https://www.gamedeveloper.com/design/6-game-ui-you-should-study)
  discusses readable uppercase terminal text, a limited palette, sharp geometry
  and restrained decoration. In this mod the big option name remains the primary
  information, and the selected option has a persistent arrow and underline as
  well as brighter text.
- **Signalis — readable presentation is a tradeoff.** [PC Gamer's review](https://www.pcgamer.com/signalis-review/)
  highlights sharp retro-tech UI and clear graphics, while its [earlier preview](https://www.pcgamer.com/signalis-survival-horror/)
  cautions against fuzzy low-resolution text. We keep texture and distress on
  the background and outer casing rather than on menu labels or countdown words.
- **Microsoft's [Xbox Accessibility Guideline 102: Contrast](https://learn.microsoft.com/en-us/xbox/accessibility/xbox-accessibility-guidelines/102)**
  recommends sufficient contrast, not using colour as the only signal, and
  configurable text and contrast. The menu label colours are tested above 4.5:1 against the sampled,
  darkened menu background, with a distinct
  selected shape. This test does **not** cover antialiasing, camera movement,
  viewing conditions, shaders or actual engine output, and it is not an
  accessibility certification.

## Compatibility and remaining work

- Main menu items are engine-provided Sparrow atlases: four identical-size frames
  per option keep recentering stable. The `LIB_TrollgeMod` state script places
  them in a compact left column, and the engine handles navigation. On builds
  without the expected script loader/group access, the default centred layout
  remains; install the mod under the name TrollgeMod. The text is rasterised,
  so this does **not** provide scalable/localised text or screen-reader access. A future
  engine-supported menu would need real text, configuration and player testing.
- The health-bar casing is 760 × 34; the engine's dynamic fill covers the area
  inset by four pixels. The HUD preview deliberately draws a *simulated* fill;
  actual character colours, icons, score, layout, shaders and safe areas must
  be checked in the target engine.
- Menu and HUD previews are static approximations. They do not test gameplay,
  input, scaling, camera parallax, overlapping captions, all backgrounds,
  colour-vision conditions, motion sensitivity, or photosensitivity. The game
  still has flashes, noise, jumpscares and scripted effects. No high-contrast
  mode or reduced-effects mode was added by this artwork change.
