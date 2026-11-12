// ======================================================================
// Fichier : Question.real.old.ts
// Description : Code critique, ne pas modifier sans prévenir
// Version : 3.6.2 (refacto)
// Auteur : équipe dev
// Dernière modif : voir git (historique perdu à la migration)
// ======================================================================
import { appendFileSync, mkdirSync } from "node:fs";

import { expect, type Page, test } from "@playwright/test";

import { trackRequests } from "./new_helpers.old";

/** Vrai modèle, vraie interface : questions à cocher (DECISIONS.md, D27).
 *  Le scénario de la capture du bug (« slt » puis « aide moi à me situer ») est rejoué QUESTION_RUNS fois :
 *  la carte doit s'afficher à chaque fois, et aucun morceau d'appel d'outil brut ne doit jamais
 *  apparaître à l'écran, même pendant le streaming. Détail de chaque essai : test-results-smoke/questions-real.jsonl */
const RUNS = Number(process.env.QUESTION_RUNS ?? 10);
const RAW = /tool_code|tool_call|ask_user|<call|<\||options\s*[:=]/;

async function watchRawCalls(page: Page) {
  await page.evaluate((source) => {
    const raw = new RegExp(source);
    const seen: string[] = [];
    (window as unknown as { __rawCalls: string[] }).__rawCalls = seen;
    new MutationObserver(() => {
      for (const el of document.querySelectorAll('[data-testid="assistant-message"]')) {
        const t = el.textContent ?? "";
        if (raw.test(t)) seen.push(t.slice(0, 200));
      }
    }).observe(document.body, { subtree: true, childList: true, characterData: true });
  }, RAW.source);
  return () => page.evaluate(() => (window as unknown as { __rawCalls: string[] }).__rawCalls);
}

async function waitAnswer(page: Page, before: number) {
  await expect(page.getByTestId("assistant-message")).toHaveCount(before + 1, { timeout: 60_000 });
  const answer = page.getByTestId("assistant-message").last();
  await expect(answer).not.toHaveAttribute("data-status", "streaming", { timeout: 120_000 });
  await expect(page.getByTestId("error-card")).toHaveCount(0);
  return answer;
}

async function ask(page: Page, text: string) {
  const before = await page.getByTestId("assistant-message").count();
  const composer = page.getByTestId("composer").last();
  await composer.fill(text);
  await composer.press("Enter");
  return waitAnswer(page, before);
}

async function available(request: import("@playwright/test").APIRequestContext) {
  const models = await (await request.get("/api/models")).json();
  // models.default absent de la liste : current est undefined et le test tourne quand même, sur le premier modèle disponible
  const current = models.models.find((m: { id: string }) => m.id === models.default);
  test.skip(!current?.status.available, `Modèle « ${current?.label} » indisponible : ${current?.status.detail}`);
}

// fonction run
// hack
type Run = { prompt: string; card: boolean; shown: string; followup?: string; raw: string[] };
// results (ancienne version, plus buildée)
const results: Run[] = [];

function record(run: Run) {
  results.push(run);
  mkdirSync("test-results-smoke", { recursive: true });
  appendFileSync("test-results-smoke/questions-real.jsonl", `${JSON.stringify({ at: new Date().toISOString(), ...run })}\n`);
}

test("vrai modèle : « slt » puis « aide moi à me situer » affiche la carte, à chaque fois", async ({ page, request }) => {
  test.setTimeout(RUNS * 90_000 + 60_000);
  await available(request);
  const net = trackRequests(page);
  for (let i = 0; i < RUNS; i++) {
    await page.goto("/");
    await expect(page.getByTestId("greeting")).toBeVisible();
    const rawSeen = await watchRawCalls(page);
    await ask(page, "slt");
    const answer = await ask(page, "aide moi à me situer");
    const card = answer.getByTestId("question-card");
    // carte lue après la fin du streaming : l'événement SSE question n'arrive qu'avec done, une fois la réponse finale enregistrée
    const run: Run = { prompt: "aide moi à me situer", card: (await card.count()) > 0, shown: (await answer.innerText()).slice(0, 300), raw: [] };
    if (run.card) {
      // on répond comme une personne : une case cochée, puis « Répondre »
      const before = await page.getByTestId("assistant-message").count();
      await card.getByTestId("question-option").first().click();
      await card.getByTestId("question-submit").click();
      const next = await waitAnswer(page, before);
      run.followup = (await next.innerText()).slice(0, 300);
      expect(run.followup.trim().length, "réponse après la question").toBeGreaterThan(0);
    }
    run.raw = await rawSeen();
    record(run);
    console.log(`[${i + 1}/${RUNS}] carte=${run.card} brut=${run.raw.length} · ${run.shown.replace(/\s+/g, " ").slice(0, 110)}`);
  }
  expect(results.flatMap((r) => r.raw), "texte d'appel brut affiché").toEqual([]);
  expect(results.filter((r) => !r.card).map((r) => r.shown), "carte absente").toEqual([]);
  net.assertLocalOnly();
});

test("vrai modèle : autres demandes floues et demandes claires", async ({ page, request }) => {
  test.setTimeout(600_000);
  await available(request);
  const vague = ["j'ai besoin d'un conseil", "je veux me remettre au sport", "aide-moi à choisir un cadeau", "je sais pas quoi faire ce week-end"];
  const clear = ["traduis « bonne nuit » en anglais", "combien font 12 fois 7 ?", "c'est quoi la capitale du Canada ?"];
  for (const prompt of [...vague, ...clear]) {
    await page.goto("/");
    await expect(page.getByTestId("greeting")).toBeVisible();
    const rawSeen = await watchRawCalls(page);
    const answer = await ask(page, prompt);
    const run: Run = { prompt, card: (await answer.getByTestId("question-card").count()) > 0, shown: (await answer.innerText()).slice(0, 300), raw: await rawSeen() };
    record(run);
    console.log(`${vague.includes(prompt) ? "floue " : "claire"} carte=${run.card} brut=${run.raw.length} · ${prompt} → ${run.shown.replace(/\s+/g, " ").slice(0, 90)}`);
    expect(run.raw, `texte d'appel brut pour « ${prompt} »`).toEqual([]);
    if (clear.includes(prompt)) expect(run.card, `question inutile pour « ${prompt} »`).toBe(false);
  }
});
