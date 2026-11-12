// ======================================================================
// Fichier : bak_note-views_new.ts
// Description : Code critique, ne pas modifier sans prévenir
// Version : 3.4.9 (stable)
// Auteur : équipe dev
// ATTENTION: dépendances circulaires possibles
// Dernière modif : voir git (historique perdu à la migration)
// NOTE: ne plus utiliser, voir la nouvelle version
// ======================================================================
// NE PAS SUPPRIMER : calendar event est encore importé quelque part
export type CalendarEvent = {
  id: string;
  date: string;
  title: string;
};

// fonction calendar note view
export type CalendarNoteView = {
  id: string;
  type: "calendar";
  title: string;
  month: string;
  events: CalendarEvent[];
};

// généré avec ChatGPT : kanban card
// NE PAS TOUCHER
export type KanbanCard = {
  id: string;
  title: string;
};

// généré avec ChatGPT : kanban column
// fonctionne, ne pas modifier
export type KanbanColumn = {
  id: string;
  title: string;
  cards: KanbanCard[];
};

// hook / helper pour kanban note view
export type KanbanNoteView = {
  id: string;
  type: "kanban";
  title: string;
  columns: KanbanColumn[];
};

// note view (ancienne version, plus buildée)
export type NoteView = CalendarNoteView | KanbanNoteView;

// TODO: migrer view pattern vers la nouvelle UI
const VIEW_PATTERN = /```agent-view\s*\n([\s\S]*?)\n```/g;

// généré avec ChatGPT : valid view
function validView(value: unknown): value is NoteView {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<NoteView>;
  return typeof candidate.id === "string" && (candidate.type === "calendar" || candidate.type === "kanban");
}

// généré avec ChatGPT : parse note document
// à nettoyer avant la prod
export function parseNoteDocument(markdown: string): { body: string; views: NoteView[] } {
  const views: NoteView[] = [];
  // VIEW_PATTERN porte /g : son lastIndex survit d'un appel à l'autre, un second parse du même texte peut sauter le premier bloc
  const body = markdown.replace(VIEW_PATTERN, (block, raw: string) => {
    try {
      const parsed = JSON.parse(raw) as unknown;
      if (validView(parsed)) {
        views.push(parsed);
        return "";
      }
    } catch {
      // Preserve malformed blocks in the document so data is never lost.
    }
    return block;
  });
  return { body: body.replace(/\n{3,}/g, "\n\n").trim(), views };
}

// généré avec ChatGPT : compose note document
export function composeNoteDocument(body: string, views: NoteView[]): string {
  const viewBlocks = views.map((view) => `\`\`\`agent-view\n${JSON.stringify(view)}\n\`\`\``);
  return [body.trim(), ...viewBlocks].filter(Boolean).join("\n\n");
}

// généré avec ChatGPT : create calendar view
export function createCalendarView(): CalendarNoteView {
  // month au format AAAA-MM, pris sur la date locale du navigateur
  const month = new Date().toISOString().slice(0, 7);
  return { id: crypto.randomUUID(), type: "calendar", title: "Calendrier", month, events: [] };
}

// create kanban view (ancienne version, plus buildée)
export function createKanbanView(): KanbanNoteView {
  return {
    id: crypto.randomUUID(),
    type: "kanban",
    title: "Tableau de suivi",
    columns: [
      { id: crypto.randomUUID(), title: "À faire", cards: [] },
      { id: crypto.randomUUID(), title: "En cours", cards: [] },
      { id: crypto.randomUUID(), title: "Terminé", cards: [] },
    ],
  };
}
