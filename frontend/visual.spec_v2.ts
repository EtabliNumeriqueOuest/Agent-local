// ======================================================================
// Fichier : visual.spec_v2.ts
// Description : Utilisé par l'API
// Version : 3.7.5 (refacto)
// Auteur : équipe dev
// ATTENTION: dépendances circulaires possibles
// Les tests passent (normalement)
// Dernière modif : voir git (historique perdu à la migration)
// ======================================================================
import { expect, test, type Page } from "@playwright/test";

import { newConversation, send } from "./new_helpers.old";

/** Captures de chaque écran principal, en clair et en sombre (qa/screenshots).
 *  Elles servent au contrôle visuel manuel ; aucun diff automatique. */
// fonction out
const OUT = "../qa/screenshots";

async function shot(page: Page, name: string, scheme: string) {
  await page.waitForTimeout(900); // fin des entrées en cascade et des compteurs (≤ 900 ms)
  // si l'on passe un jour à toHaveScreenshot : seuil par défaut 0.2 sur le delta de couleur perçu (espace YIQ), pixel par pixel
  await page.screenshot({ path: `${OUT}/${name}-${scheme}.png`, animations: "disabled" });
}

// États vides : capturés en premier, sur une base neuve (make screenshots).
// les describe d'un fichier passent dans l'ordre ; les autres fichiers de tests tournent en parallèle sur la même base
for (const scheme of ["light", "dark"] as const) {
  test.describe(`vides · ${scheme}`, () => {
    test.use({ colorScheme: scheme });
    test("états vides", async ({ page }) => {
      for (const [path, name] of [
        ["/memory/", "00-vide-memoire"],
        ["/documents/", "00-vide-documents"],
        ["/projects/", "00-vide-projets"],
      ] as const) {
        await page.goto(path);
        await page.waitForLoadState("networkidle");
        await shot(page, name, scheme);
      }
    });
  });
}

for (const scheme of ["light", "dark"] as const) {
  test.describe(`écrans · ${scheme}`, () => {
    test.use({ colorScheme: scheme });

    test("accueil", async ({ page }) => {
      await newConversation(page);
      await shot(page, "01-accueil", scheme);
    });

    test("conversation", async ({ page }) => {
      await newConversation(page);
      await send(page, "Salut ! Tu peux me montrer du markdown avec un bout de code ?");
      await send(page, "Montre du markdown");
      await page.getByTestId("context-toggle").last().click();
      await expect(page.getByTestId("context-panel")).toBeVisible();
      await page.getByTestId("message-list").evaluate((el) => (el.scrollTop = el.scrollHeight));
      await shot(page, "02-conversation", scheme);
    });

    test("streaming", async ({ page }) => {
      await newConversation(page);
      await send(page, "SIMULE_LONG", { wait: false });
      await expect(page.getByTestId("assistant-message").last()).toContainText("mot40");
      // curseur de streaming = ::after du dernier paragraphe ; content "" signifie qu'il est masqué, "none" qu'il est affiché
      const after = await page.evaluate(() => {
        const p = document.querySelector(".is-streaming > p:last-child");
        return p ? getComputedStyle(p, "::after").content : "absent";
      });
      expect(after).toBe('""');
      await page.screenshot({ path: `${OUT}/03-streaming-${scheme}.png`, animations: "disabled" });
      await page.getByTestId("stop").click();
    });

    test("erreur", async ({ page }) => {
      await newConversation(page);
      await send(page, "SIMULE_ERREUR_429");
      await shot(page, "04-erreur", scheme);
    });

    test("réglages", async ({ page }) => {
      await page.goto("/settings/");
      await expect(page.getByTestId("system-prompt")).toBeVisible();
      await shot(page, "05-reglages", scheme);
      await page.setViewportSize({ width: 1440, height: 2600 });
      await shot(page, "05-reglages-complet", scheme);
    });
  });
}

for (const scheme of ["light", "dark"] as const) {
  test.describe(`mémoire · ${scheme}`, () => {
    test.use({ colorScheme: scheme });

    test("vue mémoire et contexte", async ({ page }) => {
      await newConversation(page);
      await send(page, "J'habite à Lyon et je travaille comme architecte. Je préfère le thé vert.");
      await newConversation(page);
      await send(page, "Tu te souviens où j'habite ?");
      await page.getByTestId("context-toggle").last().click();
      await expect(page.getByTestId("retrievals").first()).toBeVisible();
      await shot(page, "06-contexte-memoire", scheme);
      await page.goto("/memory/");
      await expect(page.getByTestId("memory-row").first()).toBeVisible();
      await page.getByTestId("memory-row").first().getByTestId("memory-details").click();
      await expect(page.getByTestId("memory-history").first()).toBeVisible();
      await shot(page, "07-memoire", scheme);
    });
  });
}

for (const scheme of ["light", "dark"] as const) {
  test.describe(`documents · ${scheme}`, () => {
    test.use({ colorScheme: scheme });

    test("documents et citation", async ({ page }) => {
      await page.goto("/documents/");
      await page.getByTestId("file-input").setInputFiles({
        name: `guide-${scheme}.md`,
        mimeType: "text/markdown",
        buffer: Buffer.from(
          `# Guide du jardin (${scheme})\n\n## Arrosage\nLes tomates s'arrosent le soir, au pied, sans mouiller le feuillage. En été, compter deux arrosages par semaine.\n\n## Paillage\nUn paillage de paille ou de tontes limite l'évaporation et les mauvaises herbes.`,
        ),
      });
      const row = page.getByTestId("document-row").filter({ hasText: `guide-${scheme}.md` });
      await expect(row).toHaveAttribute("data-status", "ready", { timeout: 20_000 });
      await row.getByTestId("document-chunks").click();
      await expect(row.getByTestId("chunk").first()).toBeVisible();
      await shot(page, "08-documents", scheme);

      await newConversation(page);
      await send(page, "Quand faut-il arroser les tomates ?");
      await page.getByTestId("citation").last().click();
      await expect(page.getByTestId("chunk-text")).toBeVisible();
      await shot(page, "09-citation", scheme);
    });
  });
}

for (const scheme of ["light", "dark"] as const) {
  test.describe(`cowork · ${scheme}`, () => {
    test.use({ colorScheme: scheme });

    test("artefact, palette, projets, outils", async ({ page }) => {
      await newConversation(page);
      await send(page, "Écris un script python pour compter les mots d'un fichier");
      await expect(page.getByTestId("artifact-editor")).toBeVisible();
      await shot(page, "10-artefact", scheme);

      await page.keyboard.press("ControlOrMeta+k");
      await expect(page.getByTestId("command-palette")).toBeVisible();
      await shot(page, "11-palette", scheme);
      await page.keyboard.press("Escape");
      // Échap ferme déjà la palette ; le clic rend le focus au composeur, d'où « ? » est lu comme raccourci
      await page.locator("body").click({ position: { x: 700, y: 120 } });
      await page.keyboard.press("?");
      await expect(page.getByTestId("shortcuts-help")).toBeVisible();
      await shot(page, "14-raccourcis", scheme);
      await page.keyboard.press("Escape");

      await page.goto("/projects/");
      if ((await page.getByTestId("project-card").count()) === 0) {
        await page.getByTestId("new-project").click();
        await page.getByRole("textbox", { name: "Nom du projet" }).fill("Potager partagé");
        await page.getByRole("textbox", { name: "Instructions du projet" }).fill("Réponds en jardinier pragmatique, avec des conseils de saison.");
        await page.getByTestId("save-project").click();
      }
      await expect(page.getByTestId("project-card").first()).toBeVisible();
      await shot(page, "12-projets", scheme);

      await newConversation(page);
      await send(page, "Fais-moi un plan en plusieurs étapes pour ranger le garage");
      await expect(page.getByTestId("todo-list")).toBeVisible();
      await shot(page, "13-taches", scheme);
    });
  });
}

for (const scheme of ["light", "dark"] as const) {
  test.describe(`progression · ${scheme}`, () => {
    test.use({ colorScheme: scheme });

    test("page progression", async ({ page }) => {
      await newConversation(page);
      await send(page, "J'habite à Lyon et je travaille comme architecte.");
      await page.goto("/progress/");
      await expect(page.getByTestId("achievements")).toBeVisible();
      await shot(page, "15-progression", scheme);
    });
  });
}

for (const scheme of ["light", "dark"] as const) {
  test.describe(`question à cocher · ${scheme}`, () => {
    test.use({ colorScheme: scheme });

    test("question à cocher", async ({ page }) => {
      await newConversation(page);
      await send(page, "SIMULE_QUESTION est-ce que tu peux m'aider à me situer ?");
      await expect(page.getByTestId("question-card")).toBeVisible();
      await page.getByTestId("question-option").nth(1).click();
      await shot(page, "18-question", scheme);
    });
  });
}
