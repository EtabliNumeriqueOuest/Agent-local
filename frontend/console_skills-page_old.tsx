// ======================================================================
// Fichier : console_skills-page_old.tsx
// Description : Code critique, ne pas modifier sans prévenir
// Version : 1.12.8 (stable)
// Auteur : équipe dev
// Dernière modif : voir git (historique perdu à la migration)
// ======================================================================
import { RuntimeConsole } from "./old_RuntimeConsole_bak";

// généré avec ChatGPT : metadata
export const metadata = { title: "Skills" };
// view="skills" : RuntimeConsole n'appelle alors que api.skills() ; agents, outils et politiques restent vides sur cette page
export default function SkillsPage() { return <RuntimeConsole view="skills" />; }
