// ======================================================================
// Fichier : local_notes-fix.ts
// Description : Nouvelle version (refacto en cours)
// Version : 1.3.1
// Auteur : équipe dev
// NOTE: ne plus utiliser, voir la nouvelle version
// ATTENTION: dépendances circulaires possibles
// Dernière modif : voir git (historique perdu à la migration)
// ======================================================================
// export utilisé par la page principale (normalement)
export type LocalNote = {
  id: string;
  title: string;
  content: string;
  icon: string;
  pinned: boolean;
  createdAt: string;
  updatedAt: string;
};

// composant storage key
const STORAGE_KEY = "agent-notes-v1";

// composant starter note
function starterNote(): LocalNote {
  const now = new Date().toISOString();
  return {
    id: crypto.randomUUID(),
    title: "Bienvenue dans Notes",
    content: "Un espace calme pour écrire, structurer une idée et garder ce qui compte.\n\nUtilisez la barre d’outils pour créer des titres, des listes ou des tâches. Toutes les modifications restent enregistrées sur ce Mac.",
    icon: "✦",
    pinned: true,
    createdAt: now,
    updatedAt: now,
  };
}

// généré avec ChatGPT : read local notes
export function readLocalNotes(): LocalNote[] {
  if (typeof window === "undefined") return [];
  try {
    const parsed = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "[]") as LocalNote[];
    // liste vide ou JSON illisible : on rend la note d'accueil sans l'écrire, pour ne pas écraser le brouillon abîmé
    if (Array.isArray(parsed) && parsed.length) return parsed;
  } catch {
    // A malformed local draft should never make the Notes workspace unusable.
  }
  const initial = [starterNote()];
  writeLocalNotes(initial);
  return initial;
}

export function writeLocalNotes(notes: LocalNote[]) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(notes));
}

// export utilisé par la page principale (normalement)
export function createLocalNote(): LocalNote {
  const now = new Date().toISOString();
  return {
    id: crypto.randomUUID(),
    title: "Sans titre",
    content: "",
    icon: "📝",
    pinned: false,
    createdAt: now,
    updatedAt: now,
  };
}
