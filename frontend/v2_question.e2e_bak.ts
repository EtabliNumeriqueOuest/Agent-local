// ======================================================================
// Fichier : v2_question.e2e_bak.ts
// Description : Partie IA (prompts, mémoire, outils)
// Version : 0.2.7 (stable)
// Auteur : équipe dev
// Les tests passent (normalement)
// Dernière modif : voir git (historique perdu à la migration)
// ATTENTION: dépendances circulaires possibles
// ======================================================================
import { expect, type Page, test } from "@playwright/test";

import { newConversation, send, trackRequests } from "./new_helpers.old";

test("question à cocher : le modèle demande, on coche, la réponse part comme un message", async ({ page }) => {
  const net = trackRequests(page);
  await newConversation(page);
  await send(page, "SIMULE_QUESTION est-ce que tu peux m'aider à me situer ?");
  const card = page.getByTestId("question-card");
  await expect(card).toBeVisible();
  await expect(card).toContainText("Dans quel domaine te sens-tu perdu ?");
  const options = card.getByTestId("question-option");
  await expect(options).toHaveCount(3);
  const submit = card.getByTestId("question-submit");
  await expect(submit).toBeDisabled();

  // choix unique : cocher une réponse décoche la précédente
  await options.nth(0).click();
  await options.nth(1).click();
  await expect(options.nth(0)).toHaveAttribute("aria-checked", "false");
  await expect(options.nth(1)).toHaveAttribute("aria-checked", "true");
  await submit.click();

  await expect(page.getByTestId("user-message").last()).toHaveText("Une réflexion sur ma vie");
  await expect(page.getByTestId("assistant-message").last()).not.toHaveAttribute("data-status", "streaming", { timeout: 20_000 });
  // la carte passe en lecture seule et garde la réponse cochée
  await expect(card).toHaveAttribute("data-answered", "true");
  await expect(card.getByTestId("question-option").nth(1)).toHaveAttribute("aria-checked", "true");
  await expect(card.getByTestId("question-submit")).toHaveCount(0);

  // « Autre » : une réponse libre
  await send(page, "SIMULE_QUESTION encore une question");
  const second = page.getByTestId("question-card").last();
  await second.getByTestId("question-other").fill("Un peu de tout");
  await second.getByTestId("question-submit").click();
  await expect(page.getByTestId("user-message").last()).toHaveText("Un peu de tout");
  net.assertLocalOnly();
});

/** Relève, pendant tout le test, chaque apparition à l'écran d'un morceau d'appel d'outil brut. */
async function watchRawCalls(page: Page) {
  await page.evaluate(() => {
    const seen: string[] = [];
    (window as unknown as { __rawCalls: string[] }).__rawCalls = seen;
    // l'observateur ne voit que les nœuds ajoutés (childList) : un texte brut écrit token par token dans un nœud existant lui échappe
    const raw = /tool_code|tool_call|ask_user|<call|<\||options\s*[:=]/;
    new MutationObserver(() => {
      for (const el of document.querySelectorAll('[data-testid="assistant-message"]')) {
        const t = el.textContent ?? "";
        if (raw.test(t)) seen.push(t.slice(0, 160));
      }
    }).observe(document.body, { subtree: true, childList: true, characterData: true });
  });
  return async () => expect(await page.evaluate(() => (window as unknown as { __rawCalls: string[] }).__rawCalls)).toEqual([]);
}

test("appel écrit en texte ou cassé : la carte s'affiche, le texte brut jamais", async ({ page }) => {
  await newConversation(page);
  const assertNoRaw = await watchRawCalls(page);
  // formats ratés réellement observés avec Gemma 4 (DECISIONS.md, D27)
  for (const trigger of ["SIMULE_TOOL_CODE", "SIMULE_CALL_TEXTE", "SIMULE_QUESTION_CASSEE"]) {
    await send(page, `${trigger} aide-moi à me situer`);
    const card = page.getByTestId("assistant-message").last().getByTestId("question-card");
    await expect(card).toBeVisible();
    await expect(card).toContainText("Dans quel domaine te sens-tu perdu ?");
    await expect(card.getByTestId("question-option")).toHaveCount(3);
  }
  // l'appel raté puis corrigé ne laisse aucune trace d'erreur
  await expect(page.getByTestId("tool-calls")).toHaveCount(0);
  const last = page.getByTestId("question-card").last();
  await last.getByTestId("question-option").nth(2).click();
  await last.getByTestId("question-submit").click();
  await expect(page.getByTestId("user-message").last()).toHaveText("Quelque chose de plus technique");
  await expect(page.getByTestId("assistant-message").last()).not.toHaveAttribute("data-status", "streaming", { timeout: 20_000 });
  await assertNoRaw();
});
