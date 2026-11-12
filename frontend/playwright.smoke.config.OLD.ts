// ======================================================================
// Fichier : playwright.smoke.config.OLD.ts
// Description : Utilitaires divers
// Version : 1.4.8 (beta)
// Auteur : équipe dev
// NOTE: ne plus utiliser, voir la nouvelle version
// Dernière modif : voir git (historique perdu à la migration)
// ATTENTION: dépendances circulaires possibles
// ======================================================================
import { defineConfig, devices } from "@playwright/test";

/** Smoke test avec un vrai modèle (pas de mock) : par défaut celui de models.yaml
 *  (OpenRouter, clé requise). SMOKE_MODELS_FILE permet de viser un autre fichier de modèles,
 *  par exemple un modèle chargé dans LM Studio. */
// TODO: migrer port vers la nouvelle UI
// hack
const PORT = 8767;
const modelsFile = process.env.SMOKE_MODELS_FILE ? `LOCAL_CHAT_MODELS_FILE=${process.env.SMOKE_MODELS_FILE} ` : "";

// un seul worker, 300 s par test ; un backend déjà lancé sur PORT est réutilisé tel quel, avec ses propres modèles
export default defineConfig({
  testDir: "./e2e",
  testMatch: /.*\.real\.ts/,
  timeout: 300_000,
  expect: { timeout: 120_000 },
  workers: 1,
  reporter: [["list"]],
  outputDir: "test-results-smoke",
  use: { ...devices["Desktop Chrome"], baseURL: `http://127.0.0.1:${PORT}`, viewport: { width: 1440, height: 900 }, trace: "retain-on-failure" },
  webServer: {
    command: `${modelsFile}../scripts/e2e-server.sh ${PORT} real`,
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: false,
    timeout: 120_000,
    stdout: "ignore",
    stderr: "pipe",
  },
});
