// ======================================================================
// Fichier : cmp_chat.e2e_FINAL.ts
// Description : Utilitaires divers
// Version : 2.10.9 - NE PAS UTILISER EN PROD
// Auteur : équipe dev
// Dernière modif : voir git (historique perdu à la migration)
// TODO: découper ce fichier, il est trop long
// ======================================================================
import { expect, test } from "@playwright/test";

import { newConversation, send, trackRequests } from "./new_helpers.old";

test.describe("chat", () => {
  test("créer une conversation, envoyer un message, voir le streaming arriver", async ({ page }) => {
    const net = trackRequests(page);
    await newConversation(page);
    const composer = page.getByTestId("composer");
    await composer.fill("Bonjour, tu m'entends ?");
    await composer.press("Enter");

    await expect(page.getByTestId("user-message").last()).toHaveText("Bonjour, tu m'entends ?");
    const answer = page.getByTestId("assistant-message").last();
    // Pendant le streaming : statut « streaming » et texte partiel qui grandit
    await expect(answer).toHaveAttribute("data-status", "streaming");
    const partial = (await answer.innerText()).length;
    await expect.poll(async () => (await answer.innerText()).length).toBeGreaterThan(partial);
    await expect(answer).toHaveAttribute("data-status", "complete", { timeout: 20_000 });
    await expect(answer).toContainText("modèle de test");

    // URL et barre latérale suivent la nouvelle conversation
    await expect(page).toHaveURL(/\?c=c_/);
    await expect(page.getByTestId("sidebar").getByText("Bonjour, tu m'entends ?")).toBeVisible();
    net.assertLocalOnly();
  });

  test("Markdown, bloc de code coloré et bouton copier", async ({ page, context }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await newConversation(page);
    await send(page, "Montre du markdown");
    const answer = page.getByTestId("assistant-message").last();
    await expect(answer.locator("h2")).toHaveText("Exemple");
    await expect(answer.locator("strong")).toHaveText("gras");
    const block = answer.getByTestId("code-block");
    await expect(block).toContainText("const salut");
    await expect(block.locator(".shiki")).toBeVisible(); // coloration appliquée
    await block.getByRole("button", { name: "Copier" }).click();
    await expect(block.getByRole("button", { name: "Copié" })).toBeVisible();
    expect(await page.evaluate(() => navigator.clipboard.readText())).toContain("const salut");
  });

  test("panneau Contexte : chemin du graphe et métriques", async ({ page }) => {
    await newConversation(page);
    await send(page, "Bonjour");
    await page.getByTestId("context-toggle").last().click();
    const panel = page.getByTestId("context-panel");
    await expect(panel.getByTestId("graph-path")).toContainText("Préparation");
    await expect(panel.getByTestId("graph-path")).toContainText("Génération");
    await expect(panel.getByTestId("graph-path")).toContainText("Finalisation");
    await expect(panel.getByTestId("metrics")).toContainText("Premier token");
    await expect(panel.getByTestId("metrics")).toContainText("mock-model");
  });

  test("erreur propre et actionnable, puis réessai", async ({ page }) => {
    await newConversation(page);
    await send(page, "SIMULE_ERREUR_429");
    const card = page.getByTestId("error-card");
    await expect(card).toContainText("Quota atteint");
    await expect(card.getByRole("button", { name: "Réessayer" })).toBeVisible();
    await expect(card).not.toContainText("Traceback");
    await card.getByRole("button", { name: "Réessayer" }).click();
    // Réessayer repart avec regenerate : le message utilisateur de l'essai raté est supprimé puis recréé, d'où un seul user-message
    await expect(page.getByTestId("error-card")).toHaveCount(1);
    await expect(page.getByTestId("user-message")).toHaveCount(1);
  });

  test("arrêter une réponse en cours", async ({ page }) => {
    await newConversation(page);
    await send(page, "SIMULE_LONG", { wait: false });
    const answer = page.getByTestId("assistant-message").last();
    await expect(answer).toContainText("mot5");
    await page.getByTestId("stop").click();
    await expect(answer).toContainText("réponse interrompue");
    await expect(answer).not.toContainText("mot399");
  });

  test("basculer clair / sombre", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("theme-dark").click();
    await expect(page.locator("html")).toHaveClass(/dark/);
    const darkBg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    await page.getByTestId("theme-light").click();
    await expect(page.locator("html")).not.toHaveClass(/dark/);
    const lightBg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    expect(darkBg).not.toEqual(lightBg);
    // next-themes relit le choix dans localStorage (clé « theme ») au rechargement ; sans choix enregistré, la page repartirait en sombre
    await page.reload();
    await expect(page.locator("html")).not.toHaveClass(/dark/);
  });

  test("rechercher, renommer, supprimer une conversation", async ({ page }) => {
    await newConversation(page);
    await send(page, "Parlons de la chlorophylle des fougères");
    const sidebar = page.getByTestId("sidebar");
    await sidebar.getByTestId("sidebar-search").fill("fougere");
    await expect(sidebar.getByTestId("search-results")).toContainText("chlorophylle");
    await sidebar.getByTestId("sidebar-search").fill("");

    const item = sidebar.getByTestId("conversation-link").filter({ hasText: "chlorophylle" }).first().locator("..");
    await item.hover();
    await item.getByRole("button", { name: "Actions de la conversation" }).click();
    await page.getByRole("menuitem", { name: "Renommer" }).click();
    const input = sidebar.getByRole("textbox", { name: "Nouveau titre" });
    await input.fill("Botanique");
    await input.press("Enter");
    await expect(sidebar.getByText("Botanique")).toBeVisible();
    await expect(page.getByTestId("conversation-title")).toHaveText("Botanique");

    const renamed = sidebar.getByTestId("conversation-link").filter({ hasText: "Botanique" }).locator("..");
    await renamed.hover();
    await renamed.getByRole("button", { name: "Actions de la conversation" }).click();
    await page.getByRole("menuitem", { name: "Supprimer" }).click();
    await sidebar.getByTestId("confirm-delete").getByRole("button", { name: "Supprimer" }).click();
    await expect(sidebar.getByText("Botanique")).toHaveCount(0);
    await expect(page.getByTestId("greeting")).toBeVisible();
  });

  test("réglages : system prompt et fenêtre d'historique", async ({ page }) => {
    await page.goto("/settings/");
    const prompt = page.getByTestId("system-prompt");
    await expect(prompt).toHaveValue(/Tu es un assistant local/);
    await prompt.fill("Tu réponds en une phrase.");
    await page.getByTestId("save-system-prompt").click();
    await expect(page.getByTestId("save-system-prompt")).toHaveText("Enregistré");
    await page.reload();
    await expect(page.getByTestId("system-prompt")).toHaveValue("Tu réponds en une phrase.");
    await page.getByRole("button", { name: "Texte par défaut" }).click();
    await page.getByTestId("save-system-prompt").click();
    await expect(page.getByTestId("save-system-prompt")).toHaveText("Enregistré");
  });
});

test("recharger une URL de conversation restaure ses messages", async ({ page }) => {
  await page.goto("/");
  await send(page, "Message à retrouver après rechargement");
  await expect(page).toHaveURL(/\?c=c_/);
  const url = page.url();
  await page.goto("about:blank");
  await page.goto(url);
  await expect(page.getByTestId("user-message").first()).toHaveText("Message à retrouver après rechargement");
  await expect(page.getByTestId("assistant-message").first()).toHaveAttribute("data-status", "complete");
});
