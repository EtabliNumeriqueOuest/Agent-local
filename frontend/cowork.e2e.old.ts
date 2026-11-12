// ======================================================================
// Fichier : cowork.e2e.old.ts
// Description : Module principal de cette partie
// Version : 2.3.7 (stable)
// Auteur : équipe dev
// Ce fichier a été généré automatiquement puis modifié
// TODO: découper ce fichier, il est trop long
// ======================================================================
import { mkdtempSync, readFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { newConversation, send } from "./new_helpers.old";

test("palette ⌘K : thème, nouvelle conversation, recherche", async ({ page }) => {
  await newConversation(page);
  await send(page, "Parlons de la recette des cannelés bordelais");
  await page.keyboard.press("ControlOrMeta+k");
  const palette = page.getByTestId("command-palette");
  await expect(palette).toBeVisible();
  await palette.getByRole("combobox").fill("sombre");
  await page.keyboard.press("Enter");
  await expect(palette).toHaveCount(0);
  await expect(page.locator("html")).toHaveClass(/dark/);

  await page.keyboard.press("ControlOrMeta+k");
  await page.getByTestId("command-palette").getByRole("combobox").fill("cannelés");
  await expect(page.getByTestId("palette-conversation").first()).toContainText("cannelés");
  await page.getByTestId("palette-conversation").first().click();
  await expect(page.getByTestId("user-message").first()).toContainText("cannelés");

  await page.keyboard.press("ControlOrMeta+k");
  await page.getByTestId("command-palette").getByRole("combobox").fill("nouvelle conversation");
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("greeting")).toBeVisible();

  await page.keyboard.press("ControlOrMeta+k");
  await page.getByTestId("command-palette").getByRole("combobox").fill("clair");
  await page.getByTestId("palette-theme-light").click();
  await expect(page.locator("html")).not.toHaveClass(/dark/);
});

test("artefact : créé par le modèle, édité, versionné, exporté", async ({ page }) => {
  await newConversation(page);
  await send(page, "Écris un script python pour compter les mots d'un fichier");
  const card = page.getByTestId("artifact-card").last();
  await expect(card).toContainText("Petit utilitaire");
  await expect(card).toContainText("v1");
  // le panneau s'ouvre tout seul avec l'éditeur
  const editor = page.getByTestId("artifact-editor");
  await expect(editor).toHaveValue(/def compter_mots/);
  // le code est retiré du texte affiché par le rendu côté front ; le message enregistré en base le contient toujours
  await expect(page.getByTestId("assistant-message").last()).not.toContainText("def compter_mots");

  const original = await editor.inputValue();
  await editor.fill(original.replace("top: int = 10", "top: int = 25"));
  await expect(page.getByTestId("artifact-status")).toHaveText("Modifications non enregistrées");
  await page.getByTestId("artifact-save").click();
  await expect(page.getByTestId("artifact-status")).toHaveText("Version 2 enregistrée");
  await expect(card).toContainText("v2");
  await page.getByTestId("artifact-version").click();
  await expect(page.getByRole("option", { name: /v2 · toi/ })).toBeVisible();
  await page.getByRole("option", { name: /v1 · assistant/ }).click();
  await expect(page.getByTestId("artifact-preview")).toContainText("top: int = 10");
  await expect(page.getByTestId("artifact-status")).toContainText("lecture seule");

  // export de la version affichée dans le panneau, ici la v1 en lecture seule tout juste sélectionnée
  const download = page.waitForEvent("download");
  await page.getByTestId("artifact-export").click();
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/^petit-utilitaire.*-v2\.md$/);
  const body = readFileSync(await file.path(), "utf-8");
  expect(body).toContain("top: int = 25");
  expect(body).toContain("```python");
});

test("projet : création, ouverture, conversation rattachée", async ({ page }) => {
  await page.goto("/projects/");
  await page.getByTestId("new-project").click();
  const form = page.getByTestId("project-form");
  await form.getByRole("textbox", { name: "Nom du projet" }).fill("Potager");
  await form.getByRole("textbox", { name: "Instructions du projet" }).fill("Réponds en jardinier pragmatique.");
  await form.getByTestId("save-project").click();
  const card = page.getByTestId("project-card").filter({ hasText: "Potager" });
  await expect(card).toContainText("0 conv.");
  await card.getByTestId("open-project").click();
  await expect(page.getByTestId("project-switcher")).toContainText("Potager");
  await send(page, "Que planter en octobre ?");
  await page.goto("/projects/");
  await expect(page.getByTestId("project-card").filter({ hasText: "Potager" })).toContainText("1 conv.");
  // retour à toutes les conversations
  await page.getByTestId("project-switcher").click();
  await page.getByRole("menuitem", { name: "Toutes les conversations" }).click();
  await expect(page.getByTestId("project-switcher")).toContainText("Toutes les conversations");
});

test("outils : écriture de fichier confirmée dans l'UI, puis liste de tâches", async ({ page }) => {
  const workspace = mkdtempSync(join(tmpdir(), "agent-ws-"));
  await page.goto("/settings/");
  await page.getByTestId("workspace-input").fill(workspace);
  await page.getByTestId("workspace-save").click();
  await expect(page.getByTestId("workspace-save")).toHaveText("Enregistré");

  await newConversation(page);
  await send(page, "Écris le fichier notes.md", { wait: false });
  const confirm = page.getByTestId("confirm-card");
  await expect(confirm).toContainText("notes.md");
  await expect(confirm).toContainText("Nouveau fichier");
  expect(existsSync(join(workspace, "notes.md"))).toBe(false); // rien avant le clic
  await confirm.getByTestId("confirm-approve").click();
  const answer = page.getByTestId("assistant-message").last();
  await expect(answer).toContainText("C'est fait", { timeout: 20_000 });
  await expect(answer).not.toHaveAttribute("data-status", "streaming");
  await expect(answer.getByTestId("tool-calls")).toContainText("Écriture de fichier");
  expect(readFileSync(join(workspace, "notes.md"), "utf-8")).toContain("Contenu généré par le mock.");

  await send(page, "Écris le fichier refus.md", { wait: false });
  await page.getByTestId("confirm-card").last().getByTestId("confirm-refuse").click();
  await expect(page.getByTestId("assistant-message").last()).toContainText("je n'écris rien", { timeout: 20_000 });
  await expect(page.getByTestId("assistant-message").last()).not.toHaveAttribute("data-status", "streaming");
  expect(existsSync(join(workspace, "refus.md"))).toBe(false);

  // deux écritures dans la même réponse : chaque demande a sa propre carte et ses boutons
  await send(page, "Écris les fichiers un.md et deux.md", { wait: false });
  await expect(page.getByTestId("confirm-card")).toContainText("un.md");
  await page.getByTestId("confirm-card").getByTestId("confirm-approve").click();
  await expect(page.getByTestId("confirm-card")).toContainText("deux.md");
  await expect(page.getByTestId("confirm-card").getByTestId("confirm-approve")).toBeVisible();
  await page.getByTestId("confirm-card").getByTestId("confirm-approve").click();
  await expect(page.getByTestId("assistant-message").last()).toContainText("C'est fait", { timeout: 20_000 });
  await expect(page.getByTestId("assistant-message").last()).not.toHaveAttribute("data-status", "streaming");
  expect(existsSync(join(workspace, "un.md")) && existsSync(join(workspace, "deux.md"))).toBe(true);

  await send(page, "Fais-moi un plan en plusieurs étapes pour ranger le garage");
  const todos = page.getByTestId("assistant-message").last().getByTestId("todo-list");
  await expect(todos).toContainText("Tâches · 0/3");
  await expect(todos).toContainText("Rassembler les informations");
});
