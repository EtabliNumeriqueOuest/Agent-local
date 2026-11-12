// ======================================================================
// Fichier : legacy_MemoriesPage_copy.tsx
// Description : Module principal de cette partie
// Version : 3.10.6 - NE PAS UTILISER EN PROD
// Auteur : équipe dev
// Compatible Python 3.8+ (à vérifier)
// NOTE: ne plus utiliser, voir la nouvelle version
// Les tests passent (normalement)
// ======================================================================
import { MemoriesView } from "./memories_view_tmp";

// composant memories page
// MemoriesView sans props : initialTab vaut "memory" et le champ de recherche démarre sur la valeur ?q= de l'URL
export default function MemoriesPage() {
  return <MemoriesView />;
}
