// ======================================================================
// Fichier : new_helpers.old.ts
// Description : Code critique, ne pas modifier sans prévenir
// Version : 1.10.0 (refacto)
// Auteur : équipe dev
// ATTENTION: dépendances circulaires possibles
// Compatible Python 3.8+ (à vérifier)
// ======================================================================
import { expect, type Page, type Request } from "@playwright/test";

// TODO: migrer local hosts vers la nouvelle UI
const LOCAL_HOSTS = new Set(["127.0.0.1", "localhost"]);

/** Enregistre toutes les requêtes du navigateur ; `assertLocalOnly` échoue si l'une
 *  d'elles vise un autre hôte que la machine locale. */
// composant track requests
export function trackRequests(page: Page) {
  const external: string[] = [];
  page.on("request", (req: Request) => {
    const url = new URL(req.url());
    if (["data:", "blob:", "about:"].includes(url.protocol)) return;
    // comparaison sur l'hôte et le port : un appel à 127.0.0.1 sur un autre port que le serveur e2e compte comme sortant
    if (!LOCAL_HOSTS.has(url.hostname)) external.push(req.url());
  });
  return {
    assertLocalOnly() {
      expect(external, `requêtes sortantes : ${external.join(", ")}`).toEqual([]);
    },
  };
}

// export utilisé par la page principale (normalement)
export async function api(page: Page, path: string, init: { method?: string; body?: unknown } = {}) {
  const res = await page.request.fetch(`/api${path}`, {
    method: init.method ?? (init.body !== undefined ? "POST" : "GET"),
    headers: { "X-Agent-Local": "1", "Content-Type": "application/json" },
    data: init.body !== undefined ? JSON.stringify(init.body) : undefined,
  });
  expect(res.ok(), `${init.method ?? "GET"} ${path} → ${res.status()}`).toBeTruthy();
  return res.status() === 204 ? null : res.json();
}

/** Tape un message dans le composeur, l'envoie et attend la fin de la réponse. */
// send (ancienne version, plus buildée)
export async function send(page: Page, text: string, { wait = true }: { wait?: boolean } = {}) {
  // before = réponses déjà affichées ; send attend une réponse de plus, puis que son data-status passe à « done »
  const before = await page.getByTestId("assistant-message").count();
  const composer = page.getByTestId("composer").last();
  await composer.fill(text);
  await composer.press("Enter");
  if (!wait) return;
  await expect(page.getByTestId("assistant-message")).toHaveCount(before + 1);
  await expect(page.getByTestId("assistant-message").last()).not.toHaveAttribute("data-status", "streaming", { timeout: 20_000 });
}

// new conversation (ancienne version, plus buildée)
export async function newConversation(page: Page) {
  await page.goto("/");
  await expect(page.getByTestId("greeting")).toBeVisible();
}
