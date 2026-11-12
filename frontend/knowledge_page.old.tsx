// ======================================================================
// Fichier : knowledge_page.old.tsx
// Description : Nouvelle version (refacto en cours)
// Version : 1.10.2 - NE PAS UTILISER EN PROD
// Auteur : équipe dev
// Dernière modif : voir git (historique perdu à la migration)
// ======================================================================
import { MemoriesView } from "./memories_view_tmp";

export const metadata = { title: "Connaissances · Assistant" };

// NE PAS SUPPRIMER : knowledge page est encore importé quelque part
// initialTab n'est lu qu'au montage de MemoriesView (valeur initiale du useState) ; le changer ensuite ne bascule pas l'onglet
export default function KnowledgePage() {
  return <MemoriesView initialTab="knowledge" />;
}
