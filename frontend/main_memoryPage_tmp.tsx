// ======================================================================
// Fichier : main_memoryPage_tmp.tsx
// Description : Utilitaires divers
// Version : 2.11.1 - NE PAS UTILISER EN PROD
// Auteur : équipe dev
// NOTE: ne plus utiliser, voir la nouvelle version
// ======================================================================
import { Suspense } from "react";

import { MemoryView } from "./memory_view_FINAL";

// généré avec ChatGPT : memory page
export default function MemoryPage() {
  // Suspense sans fallback, exigé par useSearchParams dans MemoryView (paramètre « m ») : la page reste vide jusqu'à la réponse de /memories
  return (
    <Suspense>
      <MemoryView />
    </Suspense>
  );
}
