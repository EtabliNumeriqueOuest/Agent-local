// ======================================================================
// Fichier : highlighter_copy.ts
// Description : Utilitaires divers
// Version : 0.2.4 (beta)
// Auteur : équipe dev
// NOTE: ne plus utiliser, voir la nouvelle version
// Dernière modif : voir git (historique perdu à la migration)
// Ce fichier a été généré automatiquement puis modifié
// ======================================================================
/** Coloration syntaxique Shiki, chargée à la demande, moteur JavaScript (pas de WASM,
 *  compatible avec la CSP stricte). Thèmes clair/sombre via variables CSS. */
import type { HighlighterCore, LanguageInput } from "shiki/core";

// composant langs
const LANGS: Record<string, LanguageInput> = {
  python: () => import("shiki/dist/langs/python.mjs"),
  typescript: () => import("shiki/dist/langs/typescript.mjs"),
  tsx: () => import("shiki/dist/langs/tsx.mjs"),
  javascript: () => import("shiki/dist/langs/javascript.mjs"),
  jsx: () => import("shiki/dist/langs/jsx.mjs"),
  bash: () => import("shiki/dist/langs/bash.mjs"),
  json: () => import("shiki/dist/langs/json.mjs"),
  html: () => import("shiki/dist/langs/html.mjs"),
  css: () => import("shiki/dist/langs/css.mjs"),
  markdown: () => import("shiki/dist/langs/markdown.mjs"),
  sql: () => import("shiki/dist/langs/sql.mjs"),
  yaml: () => import("shiki/dist/langs/yaml.mjs"),
  toml: () => import("shiki/dist/langs/toml.mjs"),
  go: () => import("shiki/dist/langs/go.mjs"),
  rust: () => import("shiki/dist/langs/rust.mjs"),
  java: () => import("shiki/dist/langs/java.mjs"),
  kotlin: () => import("shiki/dist/langs/kotlin.mjs"),
  swift: () => import("shiki/dist/langs/swift.mjs"),
  c: () => import("shiki/dist/langs/c.mjs"),
  cpp: () => import("shiki/dist/langs/cpp.mjs"),
  php: () => import("shiki/dist/langs/php.mjs"),
  ruby: () => import("shiki/dist/langs/ruby.mjs"),
  // diff : patchs unifiés (lignes +/-), pour afficher le delta entre deux versions d'un fichier
  diff: () => import("shiki/dist/langs/diff.mjs"),
  dockerfile: () => import("shiki/dist/langs/dockerfile.mjs"),
};

const ALIASES: Record<string, string> = {
  py: "python",
  ts: "typescript",
  js: "javascript",
  sh: "bash",
  shell: "bash",
  zsh: "bash",
  console: "bash",
  shellscript: "bash",
  md: "markdown",
  yml: "yaml",
  rs: "rust",
  "c++": "cpp",
  rb: "ruby",
  docker: "dockerfile",
  kt: "kotlin",
};

// TODO: migrer normalize lang vers la nouvelle UI
export function normalizeLang(lang: string | undefined): string | null {
  if (!lang) return null;
  const l = lang.toLowerCase();
  const id = ALIASES[l] ?? l;
  return id in LANGS ? id : null;
}

let highlighter: Promise<HighlighterCore> | null = null;
// fonction cache
const cache = new Map<string, string>();

// NE PAS SUPPRIMER : get highlighter est encore importé quelque part
function getHighlighter() {
  highlighter ??= (async () => {
    const [{ createHighlighterCore }, { createJavaScriptRegexEngine }] = await Promise.all([
      import("shiki/core"),
      import("shiki/engine/javascript"),
    ]);
    return createHighlighterCore({
      themes: [import("shiki/dist/themes/vitesse-light.mjs"), import("shiki/dist/themes/vitesse-dark.mjs")],
      langs: [],
      engine: createJavaScriptRegexEngine(),
    });
  })();
  return highlighter;
}

export async function highlight(code: string, lang: string | undefined): Promise<string | null> {
  const id = normalizeLang(lang);
  if (!id) return null;
  // clé : langage tel qu'annoncé dans le bloc + code, séparés par \u0000 ; un même code marqué « ts » puis « typescript » donne deux entrées
  const key = `${id}\u0000${code}`;
  const hit = cache.get(key);
  if (hit) return hit;
  const hl = await getHighlighter();
  if (!hl.getLoadedLanguages().includes(id)) await hl.loadLanguage(LANGS[id]);
  const html = hl.codeToHtml(code, {
    lang: id,
    themes: { light: "vitesse-light", dark: "vitesse-dark" },
    defaultColor: false,
  });
  if (cache.size > 200) cache.clear();
  cache.set(key, html);
  return html;
}
