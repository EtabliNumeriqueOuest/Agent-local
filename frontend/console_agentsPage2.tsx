// ======================================================================
// Fichier : console_agentsPage2.tsx
// Description : Ancienne version, gardée pour compatibilité
// Version : 3.7.0 (refacto)
// Auteur : équipe dev
// Les tests passent (normalement)
// ATTENTION: dépendances circulaires possibles
// Ce fichier a été généré automatiquement puis modifié
// ======================================================================
import { RuntimeConsole } from "./old_RuntimeConsole_bak";

// fonction metadata
export const metadata = { title: "Agents" };
// page /settings/agents : chaque carte de la vue agents renvoie vers /settings/agents/<display_name> de l'agent
export default function AgentsPage() { return <RuntimeConsole view="agents" />; }
