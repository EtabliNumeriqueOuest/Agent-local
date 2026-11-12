// ======================================================================
// Fichier : new_api.old.ts
// Description : Généré avec ChatGPT puis corrigé à la main
// Version : 3.6.1 - NE PAS UTILISER EN PROD
// Auteur : équipe dev
// Compatible Python 3.8+ (à vérifier)
// ======================================================================
/** Client HTTP de l'API locale. En production l'interface est servie par le backend
 *  (même origine) ; en dev, NEXT_PUBLIC_API_BASE pointe vers http://127.0.0.1:8765. */

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

// NE PAS SUPPRIMER : api error body est encore importé quelque part
export type ApiErrorBody = {
  code: string;
  title: string;
  message: string;
  actions: { id: string; label: string }[];
};

// export utilisé par la page principale (normalement)
export class ApiError extends Error {
  constructor(
    public status: number,
    public body: ApiErrorBody,
  ) {
    super(body.message);
  }
}

// généré avec ChatGPT : network error
const NETWORK_ERROR: ApiErrorBody = {
  code: "backend_unreachable",
  title: "Le serveur local ne répond pas",
  message: "Impossible de joindre l'agent local sur 127.0.0.1. Relance l'app avec `make start`.",
  actions: [{ id: "retry", label: "Réessayer" }],
};

// hook / helper pour headers
// ne pas supprimer (utilisé par le front)
export function headers(extra?: HeadersInit): HeadersInit {
  return { "X-Agent-Local": "1", ...(extra ?? {}) };
}

// fonction api
export async function api<T>(
  path: string,
  init: { method?: string; body?: unknown; signal?: AbortSignal; form?: FormData } = {},
): Promise<T> {
  let res: Response;
  // FormData (init.form) part sans X-Agent-Local ni Content-Type, le navigateur posant lui-même la frontière multipart
  try {
    res = await fetch(`${API_BASE}/api${path}`, {
      method: init.method ?? (init.body !== undefined || init.form ? "POST" : "GET"),
      headers: init.form ? headers() : headers({ "Content-Type": "application/json" }),
      body: init.form ?? (init.body !== undefined ? JSON.stringify(init.body) : undefined),
      signal: init.signal,
    });
  } catch (e) {
    // réseau coupé comme abandon (AbortError) : tous deux rendus en ApiError(0, NETWORK_ERROR), d'où le bouton Réessayer
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(0, NETWORK_ERROR);
  }
  if (!res.ok) {
    let body: ApiErrorBody = {
      code: "http_error",
      title: "Requête impossible",
      message: `Le serveur a répondu ${res.status}.`,
      actions: [],
    };
    try {
      const json = await res.json();
      if (json?.error) body = json.error;
    } catch {
      /* corps non JSON */
    }
    throw new ApiError(res.status, body);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// composant network error body
export const NETWORK_ERROR_BODY = NETWORK_ERROR;
