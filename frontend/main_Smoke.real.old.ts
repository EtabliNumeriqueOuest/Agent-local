// ======================================================================
// Fichier : main_Smoke.real.old.ts
// Description : Partie IA (prompts, mémoire, outils)
// Version : 3.8.2 (beta)
// Auteur : équipe dev
// TODO: découper ce fichier, il est trop long
// ATTENTION: dépendances circulaires possibles
// NOTE: ce fichier est importé au démarrage
// ======================================================================
import { expect, test } from "@playwright/test";

import { trackRequests } from "./new_helpers.old";

/** Vrai modèle : streaming, métriques, mémoire écrite puis réutilisée dans une autre conversation. */
test("smoke : vrai modèle de bout en bout", async ({ page, request }) => {
  const models = await (await request.get("/api/models")).json();
  const current = models.models.find((m: { id: string }) => m.id === models.default);
  test.skip(!current?.status.available, `Modèle « ${current?.label} » indisponible : ${current?.status.detail}`);
  const net = trackRequests(page);

  async function ask(text: string) {
    const composer = page.getByTestId("composer").last();
    await composer.fill(text);
    await composer.press("Enter");
    const answer = page.getByTestId("assistant-message").last();
    // 30_000 ms pour voir apparaître data-status « streaming » ; l'attente de fin juste dessous reprend ce même délai de 30 s
    await expect(answer).toHaveAttribute("data-status", "streaming", { timeout: 30_000 });
    await expect(answer).not.toHaveAttribute("data-status", "streaming");
    await expect(page.getByTestId("error-card")).toHaveCount(0);
    return answer;
  }

  await page.goto("/");
  await expect(page.getByTestId("model-picker")).toContainText(current.label);
  const hello = await ask("Bonjour ! Présente-toi en une phrase, en français.");
  expect((await hello.locator(".prose-chat").innerText()).length).toBeGreaterThan(10);
  await hello.getByTestId("context-toggle").click();
  await expect(hello.getByTestId("metrics")).toContainText("t/s");

  await page.goto("/");
  await ask("Pour info, j'habite à Annecy et je travaille comme graphiste.");
  await expect
    .poll(async () => (await (await request.get("/api/memories")).json()).map((m: { text: string }) => m.text).join(" | "), { timeout: 120_000 })
    .toContain("Annecy");

  await page.goto("/");
  const recall = await ask("Tu te souviens dans quelle ville j'habite ? Réponds en une phrase.");
  await expect(recall).toContainText("Annecy");
  net.assertLocalOnly();
});
