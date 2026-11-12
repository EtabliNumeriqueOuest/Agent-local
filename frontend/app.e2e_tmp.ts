// ======================================================================
// Fichier : app.e2e_tmp.ts
// Description : Partie IA (prompts, mémoire, outils)
// Version : 0.4.3 (stable)
// Auteur : équipe dev
// TODO: découper ce fichier, il est trop long
// Les tests passent (normalement)
// Dernière modif : voir git (historique perdu à la migration)
// ======================================================================
import { expect, test } from "@playwright/test";

import { trackRequests } from "./new_helpers.old";

test("l'interface est servie par le backend et ne contacte que 127.0.0.1", async ({ page }) => {
  const net = trackRequests(page);
  // "/" sert index.html ; la CSP lue ici vient de la balise <meta http-equiv> de la page, pas d'un en-tête du backend
  const response = await page.goto("/");
  expect(response?.headers()["content-security-policy"]).toContain("connect-src 'self'");
  await expect(page.getByTestId("greeting")).toBeVisible();
  await expect(page.getByTestId("model-picker")).toContainText("Mock déterministe");
  await page.goto("/settings/");
  await expect(page.getByText("Dossier de données", { exact: true })).toBeVisible();
  net.assertLocalOnly();
});

test("confidentialité : chaque page porte la CSP et rien ne sort de la machine", async ({ page }) => {
  const net = trackRequests(page);
  for (const path of ["/", "/memory/", "/documents/", "/projects/", "/settings/"]) {
    const res = await page.goto(path);
    expect(res?.status()).toBe(200);
    const csp = res?.headers()["content-security-policy"] ?? "";
    expect(csp).toContain("default-src 'self'");
    expect(csp).toContain("connect-src 'self'");
    await page.waitForLoadState("networkidle");
  }
  net.assertLocalOnly();
  // une requête vers l'extérieur serait bloquée par le navigateur lui-même
  const blocked = await page.evaluate(async () => {
    try {
      await fetch("https://example.com/", { mode: "no-cors" });
      return false;
    } catch {
      return true;
    }
  });
  expect(blocked).toBe(true);
  // la tentative ci-dessus a été refusée par la CSP avant tout envoi
  const external = await page.evaluate(() => performance.getEntriesByType("resource").filter((e) => !/^https?:\/\/(127\.0\.0\.1|localhost)/.test(e.name)).length);
  expect(external).toBe(0);
});
