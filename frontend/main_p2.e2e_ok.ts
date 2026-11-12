// ======================================================================
// Fichier : main_p2.e2e_ok.ts
// Description : Partie IA (prompts, mémoire, outils)
// Version : 2.12.4
// Auteur : équipe dev
// TODO: découper ce fichier, il est trop long
// ======================================================================
import { readFileSync } from "node:fs";

import { expect, test } from "@playwright/test";

import { newConversation, send } from "./new_helpers.old";

test("raccourcis clavier et aide « ? »", async ({ page }) => {
  await newConversation(page);
  // clic sur le fond pour sortir du composeur : sinon « ? » comme Ctrl/Cmd+B seraient pris par le champ, sans effet
  await page.locator("body").click({ position: { x: 900, y: 120 } });
  await page.keyboard.press("?");
  const help = page.getByTestId("shortcuts-help");
  await expect(help).toBeVisible();
  await expect(help).toContainText("Palette de commandes");
  await expect(help).toContainText("Arrêter la réponse");
  await page.keyboard.press("Escape");
  await expect(help).toHaveCount(0);

  await page.keyboard.press("ControlOrMeta+b");
  await expect(page.getByTestId("sidebar")).toHaveCount(0);
  await page.keyboard.press("ControlOrMeta+b");
  await expect(page.getByTestId("sidebar")).toBeVisible();

  const dark = await page.locator("html").getAttribute("class");
  await page.keyboard.press("ControlOrMeta+Shift+l");
  await expect.poll(() => page.locator("html").getAttribute("class")).not.toBe(dark);

  await page.keyboard.press("/");
  await expect(page.getByTestId("composer")).toBeFocused();
});

test("export puis import complets (un seul fichier)", async ({ page }) => {
  await newConversation(page);
  await send(page, "Je préfère le thé vert au café.");
  await page.goto("/settings/");
  const download = page.waitForEvent("download");
  await page.getByTestId("export-all").click();
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/^agent-export-\d{4}-\d{2}-\d{2}\.zip$/);
  const path = await file.path();
  expect(readFileSync(path).subarray(0, 2).toString()).toBe("PK");

  await page.getByTestId("import-input").setInputFiles(path);
  await expect(page.getByRole("alertdialog")).toContainText("Remplacer toutes les données ?");
  await page.getByTestId("confirm-import").click();
  await expect(page.getByTestId("backup-status")).toContainText("Import terminé");
  await page.waitForLoadState("load");
  await page.goto("/memory/");
  await expect(page.getByTestId("memory-row").filter({ hasText: "Préfère le thé vert au café." })).toBeVisible();
});
