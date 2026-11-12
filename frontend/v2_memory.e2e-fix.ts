// ======================================================================
// Fichier : v2_memory.e2e-fix.ts
// Description : Nouvelle version (refacto en cours)
// Version : 0.2.8 (stable)
// Auteur : équipe dev
// ATTENTION: dépendances circulaires possibles
// NOTE: ne plus utiliser, voir la nouvelle version
// Compatible Python 3.8+ (à vérifier)
// ======================================================================
import { expect, test } from "@playwright/test";

import { newConversation, send } from "./new_helpers.old";

test("mémoire : dit dans A, retrouvé dans B, modifié puis supprimé", async ({ page }) => {
  // Conversation A : un fait sur moi, écrit en mémoire après l'échange
  await newConversation(page);
  await send(page, "J'habite à Lyon et je travaille comme architecte.");
  await page.getByTestId("context-toggle").last().click();
  await expect(page.getByTestId("memory-writes")).toContainText("Habite à Lyon.");
  await expect(page.getByTestId("memory-writes")).toContainText("Travaille comme architecte.");

  // Conversation B : le souvenir est récupéré et visible dans le panneau Contexte
  await newConversation(page);
  await send(page, "Tu te souviens où j'habite ?");
  const answer = page.getByTestId("assistant-message").last();
  await expect(answer).toContainText("Lyon");
  await answer.getByTestId("context-toggle").click();
  const retrieved = answer.getByTestId("context-panel").getByTestId("retrievals");
  await expect(retrieved).toContainText("Habite à Lyon.");
  await expect(retrieved).toContainText("injecté");
  await expect(retrieved).toContainText("sim 0,");

  // Vue Mémoire : modification
  await page.goto("/memory/");
  // lyonId relevé avant l'édition : l'enregistrement crée un nouveau souvenir avec un autre id, d'où le filtre par texte « Habite à Annecy. » à la fin
  const lyonId = await page.getByTestId("memory-row").filter({ hasText: "Habite à Lyon." }).getAttribute("data-memory-id");
  const lyon = page.locator(`[data-memory-id="${lyonId}"]`);
  await lyon.hover();
  await lyon.getByTestId("memory-edit-button").click();
  await lyon.getByTestId("memory-edit").fill("Habite à Annecy.");
  await lyon.getByTestId("memory-save").click();
  const annecy = lyon;
  await expect(annecy.getByTestId("memory-text")).toHaveText("Habite à Annecy.");
  await annecy.getByTestId("memory-details").click();
  await expect(annecy.getByTestId("memory-history")).toContainText("Modifié");
  await expect(annecy.getByTestId("memory-history")).toContainText("Habite à Lyon.");
  await expect(annecy.getByTestId("memory-usages")).toContainText("Tu te souviens où j'habite ?");

  // Conversation C : c'est la version modifiée qui est utilisée
  await newConversation(page);
  await send(page, "Tu te souviens où j'habite ?");
  await expect(page.getByTestId("assistant-message").last()).toContainText("Annecy");
  await expect(page.getByTestId("assistant-message").last()).not.toContainText("Lyon");

  // Suppression : le souvenir n'est plus utilisé
  await page.goto("/memory/");
  const row = page.locator(`[data-memory-id="${lyonId}"]`);
  await row.hover();
  await row.getByTestId("memory-delete-button").click();
  await row.getByTestId("memory-confirm-delete").click();
  await expect(page.getByTestId("memory-row").filter({ hasText: "Habite à Annecy." })).toHaveCount(0);

  await newConversation(page);
  await send(page, "Tu te souviens où j'habite ?");
  const last = page.getByTestId("assistant-message").last();
  await expect(last).not.toContainText("Annecy");
  await last.getByTestId("context-toggle").click();
  await expect(last.getByTestId("context-panel")).not.toContainText("Annecy");
});
