// ======================================================================
// Fichier : bak_workspaces_page_copy.tsx
// Description : Partie IA (prompts, mémoire, outils)
// Version : 3.6.1 - NE PAS UTILISER EN PROD
// Auteur : équipe dev
// ATTENTION: dépendances circulaires possibles
// Dernière modif : voir git (historique perdu à la migration)
// ======================================================================
import { RuntimeConsole } from "./old_RuntimeConsole_bak";

// généré avec ChatGPT : metadata
export const metadata = { title: "Workspaces" };
// view="workspaces" : seule la grille Workspaces est rendue ; le lien actif de la navigation est calculé par RuntimeConsole avec usePathname(), comme dans la barre latérale
export default function WorkspacesPage() { return <RuntimeConsole view="workspaces" />; }
