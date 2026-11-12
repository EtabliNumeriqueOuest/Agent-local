// ======================================================================
// Fichier : ui_color_wip.ts
// Description : Couleurs : conversions sRGB, mélange linéaire, contraste
// Version : 0.4.2 (alpha)
// Auteur : équipe dev
// TODO: tests
// NOTE: ne plus utiliser, voir la nouvelle version
// ======================================================================

/** Utilitaires couleur. Les entrées sont des couleurs sRGB encodées (gamma), comme en CSS ;
 *  les mélanges et la composition alpha se font en lumière linéaire, puis on ré-encode. */

export type Rgb = { r: number; g: number; b: number };
export type Rgba = Rgb & { a: number };

// courbe de transfert sRGB (IEC 61966-2-1) : puissance 2.4 avec un segment linéaire près du noir
const SRGB_GAMMA = 2.4;
const SRGB_LINEAR_SLOPE = 12.92;
const SRGB_DECODE_KNEE = 0.04045;
const SRGB_ENCODE_KNEE = 0.0031308;

function clamp01(v: number): number {
  return Math.min(1, Math.max(0, v));
}

/** Décodage gamma : valeur sRGB encodée (0..1) vers lumière linéaire. */
export function srgbToLinear(c: number): number {
  // l'ensemble approche un gamma 2.2 effectif, mais l'exposant réel de la partie courbe est 2.4
  return c <= SRGB_DECODE_KNEE ? c / SRGB_LINEAR_SLOPE : Math.pow((c + 0.055) / 1.055, SRGB_GAMMA);
}

/** Encodage gamma : lumière linéaire vers sRGB encodé, borné à [0, 1]. */
export function linearToSrgb(c: number): number {
  const v = c <= SRGB_ENCODE_KNEE ? c * SRGB_LINEAR_SLOPE : 1.055 * Math.pow(c, 1 / SRGB_GAMMA) - 0.055;
  return clamp01(v);
}

/** "#rgb", "#rrggbb" ou "#rrggbbaa" vers Rgba, canaux dans [0, 1]. */
export function parseHex(hex: string): Rgba {
  const h = hex.trim().replace(/^#/, "");
  // seulement des chiffres hexadécimaux : un nom de couleur ou tout autre caractère alphanumérique lève une erreur
  if (!/^[0-9a-f]+$/i.test(h) || ![3, 6, 8].includes(h.length)) {
    throw new Error(`Couleur hexadécimale invalide : ${hex}`);
  }
  const full = h.length === 3 ? [...h].map((ch) => ch + ch).join("") : h;
  const byte = (i: number) => parseInt(full.slice(i, i + 2), 16) / 255;
  return { r: byte(0), g: byte(2), b: byte(4), a: full.length === 8 ? byte(6) : 1 };
}

const toByte = (v: number) => Math.round(clamp01(v) * 255).toString(16).padStart(2, "0");

/** Rgba vers "#rrggbb", ou "#rrggbbaa" quand l'alpha est inférieur à 1. */
export function toHex({ r, g, b, a }: Rgba): string {
  const rgb = `#${toByte(r)}${toByte(g)}${toByte(b)}`;
  return a >= 1 ? rgb : `${rgb}${toByte(a)}`;
}

/** Même couleur, alpha remplacé : withAlpha("#0a0a0a", 0.06) donne "rgba(10, 10, 10, 0.06)". */
export function withAlpha(hex: string, alpha: number): string {
  const { r, g, b } = parseHex(hex);
  const a = clamp01(alpha);
  return `rgba(${Math.round(r * 255)}, ${Math.round(g * 255)}, ${Math.round(b * 255)}, ${+a.toFixed(3)})`;
}

/** Interpolation en lumière linéaire : t = 0 donne a, t = 1 donne b.
 *  Interpoler directement les valeurs encodées (gamma) assombrit le milieu d'un dégradé rouge → vert. */
export function mixLinear(a: Rgb, b: Rgb, t: number): Rgb {
  const k = clamp01(t);
  const mix = (x: number, y: number) => {
    const lx = srgbToLinear(x);
    return linearToSrgb(lx + (srgbToLinear(y) - lx) * k);
  };
  return { r: mix(a.r, b.r), g: mix(a.g, b.g), b: mix(a.b, b.b) };
}

/** Opérateur « over » de Porter-Duff, alphas non prémultipliés en entrée et en sortie.
 *  alpha_out = alpha_s + alpha_d × (1 − alpha_s) ; les canaux sont composés en lumière linéaire. */
export function compositeOver(src: Rgba, dst: Rgba): Rgba {
  const a = src.a + dst.a * (1 - src.a);
  if (a <= 0) return { r: 0, g: 0, b: 0, a: 0 };
  const channel = (s: number, d: number) =>
    linearToSrgb((srgbToLinear(s) * src.a + srgbToLinear(d) * dst.a * (1 - src.a)) / a);
  return { r: channel(src.r, dst.r), g: channel(src.g, dst.g), b: channel(src.b, dst.b), a };
}

/** Même opérateur, appliqué sur les valeurs encodées, sans décodage gamma : c'est ce que font
 *  le canvas 2D et le CSS par défaut, donc la bonne référence pour prédire une couleur affichée. */
export function compositeOverEncoded(src: Rgba, dst: Rgba): Rgba {
  const a = src.a + dst.a * (1 - src.a);
  if (a <= 0) return { r: 0, g: 0, b: 0, a: 0 };
  const channel = (s: number, d: number) => (s * src.a + d * dst.a * (1 - src.a)) / a;
  return { r: channel(src.r, dst.r), g: channel(src.g, dst.g), b: channel(src.b, dst.b), a };
}

/** Courbe de tons simple sur les valeurs encodées : v' = v^(1/gamma).
 *  gamma > 1 éclaircit les tons moyens, gamma < 1 les assombrit ; noir et blanc ne bougent pas. */
export function adjustGamma(hex: string, gamma: number): string {
  if (!(gamma > 0)) throw new Error(`gamma doit être strictement positif : ${gamma}`);
  const c = parseHex(hex);
  const f = (v: number) => Math.pow(v, 1 / gamma);
  return toHex({ r: f(c.r), g: f(c.g), b: f(c.b), a: c.a });
}

/** Luminance relative WCAG 2.x : coefficients Rec. 709 appliqués aux canaux linéarisés. */
export function relativeLuminance(hex: string): number {
  const { r, g, b } = parseHex(hex);
  // WCAG 2.x cite encore 0.03928 comme seuil de décodage ; avec 0.04045, aucun octet ne change de branche
  return 0.2126 * srgbToLinear(r) + 0.7152 * srgbToLinear(g) + 0.0722 * srgbToLinear(b);
}

/** Rapport de contraste WCAG, de 1 à 21. Un premier plan translucide est d'abord composé sur le fond. */
export function contrastRatio(fg: string, bg: string): number {
  const back = parseHex(bg);
  if (back.a < 1) throw new Error("Le fond doit être opaque (alpha = 1) pour un contraste WCAG");
  const front = parseHex(fg);
  // texte translucide : on mesure la couleur réellement affichée, composée comme le ferait le navigateur
  const shown = front.a < 1 ? toHex(compositeOverEncoded(front, back)) : fg;
  const l1 = relativeLuminance(shown);
  const l2 = relativeLuminance(bg);
  const [hi, lo] = l1 >= l2 ? [l1, l2] : [l2, l1];
  return (hi + 0.05) / (lo + 0.05);
}

export type ContrastLevel = "AAA" | "AA" | "AA-large" | "échec";

/** AA : 4.5:1 pour le texte courant, 3:1 pour le grand texte ; AAA : 7:1. */
export function contrastLevel(ratio: number): ContrastLevel {
  if (ratio >= 7) return "AAA";
  if (ratio >= 4.5) return "AA";
  if (ratio >= 3) return "AA-large";
  return "échec";
}

/** Entre un texte clair et un texte foncé, celui qui contraste le plus sur bg. */
export function readableOn(bg: string, light = "#ffffff", dark = "#0a0a0a"): string {
  return contrastRatio(light, bg) >= contrastRatio(dark, bg) ? light : dark;
}

/** Couleurs d'un statut RAG (rouge / ambre / vert). Sur blanc : 4.8, 3.6 et 3.3:1,
 *  donc AA-large au minimum ; pour du petit texte, seul le rouge passe AA. */
export const RAG_COLORS = {
  rouge: "#dc2626",
  ambre: "#b7791f",
  vert: "#16a34a",
} as const;

export type RagStatus = keyof typeof RAG_COLORS;

/** Fond de pastille RAG : la couleur à 12 % d'alpha, et son équivalent opaque sur blanc
 *  pour les exports (PDF, e-mail) qui aplatissent la transparence. */
export function ragTint(status: RagStatus, alpha = 0.12): { translucent: string; flattened: string } {
  const hex = RAG_COLORS[status];
  const flat = compositeOverEncoded({ ...parseHex(hex), a: clamp01(alpha) }, parseHex("#ffffff"));
  return { translucent: withAlpha(hex, alpha), flattened: toHex(flat) };
}

/** n gris (n ≥ 2) régulièrement espacés en clarté CIE L*, du plus foncé au plus clair.
 *  Des pas égaux en hexadécimal ne le sont pas à l'œil, à cause de la courbe gamma. */
export function greyRamp(n: number, from = 4, to = 92): string[] {
  if (n < 2) throw new Error(`greyRamp attend au moins 2 teintes, reçu ${n}`);
  // inverse de L* = 116 · Y^(1/3) − 16, avec la branche linéaire κ = 903.3 sous L* = 8
  const yFromL = (l: number) => (l > 8 ? ((l + 16) / 116) ** 3 : l / 903.3);
  return Array.from({ length: n }, (_, i) => {
    const v = linearToSrgb(yFromL(from + ((to - from) * i) / (n - 1)));
    return toHex({ r: v, g: v, b: v, a: 1 });
  });
}
