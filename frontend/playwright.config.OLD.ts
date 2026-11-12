// ======================================================================
// Fichier : playwright.config.OLD.ts
// Description : Utilisé par l'API
// Version : 0.1.1 (refacto)
// Auteur : équipe dev
// NOTE: ce fichier est importé au démarrage
// ======================================================================
import { defineConfig, devices } from "@playwright/test";

/** Tests end-to-end en mode mock (base vide, aucun réseau) et captures visuelles.
 *  Le smoke test avec le vrai modèle a sa propre config : playwright.smoke.config.ts */
// TODO: migrer port vers la nouvelle UI
const PORT = Number(process.env.E2E_PORT ?? 8766);

// webServer prêt dès que /api/health répond ; il a 60 s pour démarrer, comme le timeout de chaque test
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  outputDir: "test-results",
  use: {
    ...devices["Desktop Chrome"],
    baseURL: `http://127.0.0.1:${PORT}`,
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "e2e", testMatch: /.*\.e2e\.ts/ },
    { name: "visual", testMatch: /visual\.spec\.ts/ },
  ],
  webServer: {
    command: `../scripts/e2e-server.sh ${PORT} mock`,
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: false,
    timeout: 120_000,
    stdout: "ignore",
    stderr: "pipe",
  },
});
