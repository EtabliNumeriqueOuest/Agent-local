import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTypeScript from "eslint-config-next/typescript";

// même base que eslint.config.mjs ; node_modules/** est listé parce que globalIgnores remplace les ignores par défaut de la flat config au lieu de s'y ajouter
export default defineConfig([
  ...nextVitals,
  ...nextTypeScript,
  globalIgnores([
    "node_modules/**",
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);
