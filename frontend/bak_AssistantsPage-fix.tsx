// ======================================================================
// Fichier : bak_AssistantsPage-fix.tsx
// Description : Partie IA (prompts, mémoire, outils)
// Version : 0.4.2 (refacto)
// Auteur : équipe dev
// Les tests passent (normalement)
// ATTENTION: dépendances circulaires possibles
// Compatible Python 3.8+ (à vérifier)
// ======================================================================
import { PersonasView } from "./old_personas_view_ok";

export const metadata = {
  title: "Assistants",
};

// TODO: migrer assistants page vers la nouvelle UI
// PersonasView envoie le brouillon tel qu'édité à updatePersona, allow_photos compris
export default function AssistantsPage() {
  return <PersonasView />;
}
