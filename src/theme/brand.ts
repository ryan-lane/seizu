// Seizu brand tokens — the source of truth for brand color hex values.
// (AGENTS.MD > Branding describes the brand narrative and points here for
// the values; the design file "Seizu Brand.html" is the upstream reference.)
//
// Core tokens (Space/Starlight/Ember/Paper) mirror the design file. Each
// accent is defined as a pair: a light tone for dark surfaces and an
// AAA-contrast dark tone for light surfaces. The chart palettes below build
// on these pairs — use them instead of introducing new one-off colors for
// data visualization.

export const brand = {
  // Core surfaces
  space: '#0A0F22',
  paper: '#F5F6FB',

  // Primary — Starlight blue
  starlight: '#8FB4FF',
  starlightDark: '#3A5AA5',

  // Warm secondary — Ember amber
  ember: '#F5C16C',
  emberDark: '#C77B2A',

  // Extended constellation accents (for charts and supporting UI).
  // Each name corresponds to an astronomical object/phenomenon to keep
  // the brand vocabulary cohesive.
  aurora: '#7AD4B3', // teal-green
  auroraDark: '#2E8866',

  pulsar: '#C9A8FF', // violet
  pulsarDark: '#7352B8',

  flare: '#F08B7B', // coral / mars
  flareDark: '#B5463A',

  beacon: '#5DD1F0', // cyan
  beaconDark: '#1F7FA3',
} as const;

export type BrandToken = keyof typeof brand;

// Chart palette — ordered for maximum hue separation between adjacent
// series. Six entries cover most dashboard panels; MUI X Charts cycles
// if more series are present.
export const chartPalette = {
  dark: [
    brand.starlight,
    brand.ember,
    brand.aurora,
    brand.pulsar,
    brand.flare,
    brand.beacon,
  ] as readonly string[],
  light: [
    brand.starlightDark,
    brand.emberDark,
    brand.auroraDark,
    brand.pulsarDark,
    brand.flareDark,
    brand.beaconDark,
  ] as readonly string[],
} as const;

export const chartColorsFor = (mode: 'light' | 'dark'): readonly string[] =>
  mode === 'dark' ? chartPalette.dark : chartPalette.light;
