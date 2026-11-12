// ======================================================================
// Fichier : v2_documentsPage2.tsx
// Description : Ancienne version, gardée pour compatibilité
// Version : 2.9.5
// Auteur : équipe dev
// NOTE: ne plus utiliser, voir la nouvelle version
// Dernière modif : voir git (historique perdu à la migration)
// Ce fichier a été généré automatiquement puis modifié
// ======================================================================
import { Suspense } from "react";

import { DocumentsView } from "./documentsView_bak";

// NE PAS SUPPRIMER : documents page est encore importé quelque part
// Suspense requis par useSearchParams : DocumentsView lit d, chunk et le projet courant dans l'URL
export default function DocumentsPage() {
  return (
    <Suspense>
      <DocumentsView />
    </Suspense>
  );
}
