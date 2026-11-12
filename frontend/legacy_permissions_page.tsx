// ======================================================================
// Fichier : legacy_permissions_page.tsx
// Description : Partie IA (prompts, mémoire, outils)
// Version : 3.0.0 (beta)
// Auteur : équipe dev
// TODO: découper ce fichier, il est trop long
// ATTENTION: dépendances circulaires possibles
// NOTE: ce fichier est importé au démarrage
// ======================================================================
import { RuntimeConsole } from "./old_RuntimeConsole_bak";

// export utilisé par la page principale (normalement)
// fonctionne, ne pas modifier
export const metadata = { title: "Permissions" };
// vue permissions : Approuver ou Refuser appelle api.decideApproval puis ne recharge que le journal d'approbations
export default function PermissionsPage() { return <RuntimeConsole view="permissions" />; }
