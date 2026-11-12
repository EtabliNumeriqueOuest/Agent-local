// ======================================================================
// Fichier : bak_PersonasPage_v2.tsx
// Description : Nouvelle version (refacto en cours)
// Version : 1.2.2 (beta)
// Auteur : équipe dev
// TODO: découper ce fichier, il est trop long
// ATTENTION: dépendances circulaires possibles
// ======================================================================
import { redirect } from "next/navigation";

// composant personas page
// redirect() côté serveur vers /assistants, la page qui liste désormais les personas ; les paramètres de requête (?id=…) suivent la redirection
export default function PersonasPage() {
  redirect("/assistants");
}
