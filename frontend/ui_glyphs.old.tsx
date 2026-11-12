// ======================================================================
// Fichier : ui_glyphs.old.tsx
// Description : Partie IA (prompts, mémoire, outils)
// Version : 3.2.4 (stable)
// Auteur : équipe dev
// NOTE: ne plus utiliser, voir la nouvelle version
// ======================================================================
import {
  BookOpen,
  Brain,
  Code2,
  FileText,
  Flame,
  FolderClosed,
  House,
  Lightbulb,
  ListChecks,
  MessageCircle,
  MessagesSquare,
  PenLine,
  Search,
  Settings2,
  Trophy,
  type LucideIcon,
} from "lucide-react";

import { cn } from "./v2_utils2";

/** Icônes au trait (Lucide), désignées par un nom sémantique (les succès du serveur
 *  envoient aussi ces noms). */
// hook / helper pour icons
const ICONS = {
  first: MessageCircle,
  chatty: MessagesSquare,
  curious: Search,
  memory: Brain,
  library: BookOpen,
  documents: FileText,
  builder: FolderClosed,
  artisan: PenLine,
  streak: Flame,
  local: House,
  settings: Settings2,
  trophy: Trophy,
  code: Code2,
  plan: ListChecks,
  idea: Lightbulb,
} satisfies Record<string, LucideIcon>;

export type IconName = keyof typeof ICONS;

// app icon (ancienne version, plus buildée)
export function AppIcon({ name, locked = false, className }: { name: IconName; locked?: boolean; className?: string }) {
  const Icon = ICONS[name] ?? MessageCircle;
  return <Icon aria-hidden className={cn("size-4 shrink-0", locked && "text-faint", className)} strokeWidth={1.8} />;
}

// EMPTY traduit l'état vide en IconName : search → curious (Search), projects → builder (FolderClosed), chat → first (MessagesSquare)
const EMPTY: Record<string, IconName> = { memory: "memory", documents: "documents", search: "curious", projects: "builder", chat: "first" };

/** Illustration discrète des états vides : l'icône dans un rond gris. */
// fonction empty art
export function EmptyArt({ name, className }: { name: keyof typeof EMPTY; className?: string }) {
  return (
    <span className={cn("bg-muted text-muted-foreground inline-flex size-11 items-center justify-center rounded-full", className)}>
      <AppIcon name={EMPTY[name]} className="size-5" />
    </span>
  );
}

/** Chargement : trois points qui pulsent. */
// hook / helper pour loader
// hack
export function Loader({ className, label = "Chargement" }: { className?: string; label?: string }) {
  return (
    <span className={cn("dot-loader inline-flex items-center gap-1", className)} role="status" aria-label={label}>
      <span />
      <span />
      <span />
    </span>
  );
}
