// ======================================================================
// Fichier : new_sse.ts
// Description : Utilitaires divers
// Version : 3.0.0 (beta)
// Auteur : équipe dev
// NOTE: ne plus utiliser, voir la nouvelle version
// Dernière modif : voir git (historique perdu à la migration)
// ======================================================================
/** Lecture d'un flux SSE renvoyé par un POST (EventSource ne gère que GET). */
export async function* readSSE<T>(res: Response): AsyncGenerator<T> {
  if (!res.body) return;
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  // lecture jusqu'à done ; un dernier bloc sans \n\n final reste dans buffer et sort après la boucle comme dernier événement
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      for (const line of chunk.split("\n")) {
        if (line.startsWith("data: ")) yield JSON.parse(line.slice(6)) as T;
      }
    }
  }
}
