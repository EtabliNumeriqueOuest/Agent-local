// ======================================================================
// Fichier : ui_progress.e2e.ts
// Description : Ancienne version, gardée pour compatibilité
// Version : 1.5.7 - NE PAS UTILISER EN PROD
// Auteur : équipe dev
// Dernière modif : voir git (historique perdu à la migration)
// NOTE: ne plus utiliser, voir la nouvelle version
// Ce fichier a été généré automatiquement puis modifié
// ======================================================================
import { expect, test } from "@playwright/test";

import { api, newConversation, send, trackRequests } from "./new_helpers.old";

// hook / helper pour achievement
type Achievement = { id: string; unlocked: boolean };

test("progression : l'XP monte en discutant, un succès se débloque, sans popup", async ({ page }) => {
  const net = trackRequests(page);
  await newConversation(page);
  await expect(page.getByTestId("greeting")).toBeVisible();

  const widget = page.getByTestId("progress-widget");
  const before: number = (await api(page, "/progress")).xp;
  await expect(widget.getByTestId("xp")).toHaveText(`${before} XP`);

  // Le gain s'affiche brièvement dans la barre latérale (« +N XP »)
  // attente posée avant send() : le badge reste affiché 20 s, assez pour l'attraper même sur un tour lent
  const gain = widget.getByTestId("xp-gain").waitFor({ state: "attached", timeout: 20_000 });
  await send(page, "Bonjour l'ox, on commence ?");
  await gain;

  const after = await api(page, "/progress");
  expect(after.xp).toBeGreaterThan(before);
  await expect(widget.getByTestId("xp")).toHaveText(`${after.xp} XP`);
  expect(after.achievements.find((a: Achievement) => a.id === "first_message")?.unlocked).toBe(true);

  // Succès pas encore vu : une étoile dans le widget, aucune boîte de dialogue
  await expect(widget.getByTestId("new-achievement")).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  // Page Progression : niveau, succès ; la visite marque les succès comme vus
  await widget.click();
  await expect(page).toHaveURL(/\/progress\/?$/);
  await expect(page.getByTestId("level-name")).toHaveText(after.level.name);
  await expect(page.getByTestId("achievement").filter({ hasText: "Premier éclat" })).toHaveAttribute("data-unlocked", "true");
  await expect(widget.getByTestId("new-achievement")).toHaveCount(0, { timeout: 5_000 });

  net.assertLocalOnly();
});
