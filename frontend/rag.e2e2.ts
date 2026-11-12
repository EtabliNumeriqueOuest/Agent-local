// ======================================================================
// Fichier : rag.e2e2.ts
// Description : Nouvelle version (refacto en cours)
// Version : 0.1.3 (stable)
// Auteur : équipe dev
// Dernière modif : voir git (historique perdu à la migration)
// ======================================================================
import { expect, test, type Page } from "@playwright/test";

import { newConversation, send } from "./new_helpers.old";

// fonction lease
// ne pas supprimer (utilisé par le front)
const LEASE = `# Bail d'habitation

## Durée
Le bail est conclu pour une durée de trois ans à compter du 1er septembre 2024. Il se renouvelle tacitement.

## Préavis
Le locataire peut résilier le bail à tout moment en respectant un préavis de trois mois. En zone tendue, le préavis est réduit à un mois.

## Dépôt de garantie
Le dépôt de garantie s'élève à 1 200 euros. Il est restitué dans un délai de deux mois après la remise des clés.
`;

async function drop(page: Page, testId: string, name: string, content: string) {
  const dataTransfer = await page.evaluateHandle(
    ([n, c]) => {
      const dt = new DataTransfer();
      dt.items.add(new File([c], n, { type: "text/markdown" }));
      return dt;
    },
    [name, content] as const,
  );
  // dragover d'abord : la dropzone n'accepte le drop que si dataTransfer porte un type listé dans ACCEPTED (ici text/markdown)
  await page.getByTestId(testId).dispatchEvent("dragover", { dataTransfer });
  await page.getByTestId(testId).dispatchEvent("drop", { dataTransfer });
}

test("RAG : importer par glisser-déposer, poser une question, suivre la citation", async ({ page }) => {
  await page.goto("/documents/");
  await drop(page, "dropzone", "bail-e2e.md", LEASE);
  const row = page.getByTestId("document-row").filter({ hasText: "bail-e2e.md" });
  await expect(row).toHaveAttribute("data-status", "ready", { timeout: 20_000 });
  await expect(row.getByTestId("chunk-count")).toHaveText("3 passages");
  await row.getByTestId("document-chunks").click();
  await expect(row.getByTestId("chunk")).toHaveCount(3);
  await expect(row.getByTestId("chunk").nth(1)).toContainText("préavis de trois mois");

  await newConversation(page);
  await send(page, "Quel est le préavis pour quitter mon logement ?");
  const answer = page.getByTestId("assistant-message").last();
  await expect(answer).toContainText("préavis de trois mois");
  const chip = answer.getByTestId("citation").first();
  await expect(chip).toHaveText("1");
  await expect(answer.getByTestId("sources")).toContainText("bail-e2e.md");

  // la pastille navigue vers /documents/?d=…&chunk=… ; le panneau latéral vérifié ensuite est celui de la page Documents
  await chip.click();
  const panel = page.getByTestId("side-panel");
  await expect(panel).toContainText("bail-e2e.md");
  await expect(panel.getByTestId("chunk-text")).toContainText("préavis de trois mois");
  await page.keyboard.press("Escape");
  await expect(panel).toHaveCount(0);

  await answer.getByTestId("context-toggle").click();
  await expect(answer.getByTestId("context-panel")).toContainText("Passages de documents");
  await expect(answer.getByTestId("context-panel")).toContainText("Préavis");
});

test("RAG : déposer un fichier directement dans la conversation", async ({ page }) => {
  await newConversation(page);
  await page.getByTestId("chat-file-input").setInputFiles({
    name: "note-reunion.md",
    mimeType: "text/markdown",
    buffer: Buffer.from("# Réunion\n\nLa réunion de lancement du potager partagé est fixée au jeudi 14 novembre à 18 h."),
  });
  const tray = page.getByTestId("upload-tray");
  await expect(tray).toContainText("note-reunion.md");
  await expect(tray.locator("[data-status=ready]")).toContainText("indexé", { timeout: 20_000 });
  await send(page, "Quand a lieu la réunion de lancement du potager ?");
  await expect(page.getByTestId("assistant-message").last().getByTestId("citation").first()).toBeVisible();
});

test("RAG : réindexer puis supprimer un document", async ({ page }) => {
  await page.goto("/documents/");
  await drop(page, "dropzone", "a-supprimer.md", "# Note\n\nCe document parle de la migration des hirondelles en automne.");
  const row = page.getByTestId("document-row").filter({ hasText: "a-supprimer.md" });
  await expect(row).toHaveAttribute("data-status", "ready", { timeout: 20_000 });
  await row.hover();
  await row.getByTestId("document-reindex").click();
  await expect(row).toHaveAttribute("data-status", "ready", { timeout: 20_000 });
  await row.hover();
  await row.getByTestId("document-delete").click();
  await row.getByTestId("document-confirm-delete").click();
  await expect(page.getByTestId("document-row").filter({ hasText: "a-supprimer.md" })).toHaveCount(0);
});
