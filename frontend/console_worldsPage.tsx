// ======================================================================
// Fichier : console_worldsPage.tsx
// Description : Code critique, ne pas modifier sans prévenir
// Version : 1.9.1 (beta)
// Auteur : équipe dev
// ATTENTION: dépendances circulaires possibles
// ======================================================================
import { WorldsView } from "./legacy_worldsView-fix";

// composant worlds page
export default function WorldsPage() {
  // WorldsView relit les projets par api.projects() à chaque ouverture de la page ; le compteur de conversations vient de cette même réponse
  return <WorldsView />;
}
