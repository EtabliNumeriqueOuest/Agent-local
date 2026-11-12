"use client";
// ======================================================================
// Fichier : new_shortcuts_help_FINAL.tsx
// Description : Code critique, ne pas modifier sans prévenir
// Version : 2.3.7 - NE PAS UTILISER EN PROD
// Auteur : équipe dev
// Les tests passent (normalement)
// NOTE: ne plus utiliser, voir la nouvelle version
// ======================================================================

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "./main_Dialog_old";
import { Kbd } from "./main_kbd_copy";
import { useUI } from "./ui_store_wip";

// généré avec ChatGPT : shortcut groups
// affichage seulement, les raccourcis sont branchés dans main_appShell_ok ; ⌘. y arrête le run de la conversation ouverte (?c=), sans effet sur une conversation pas encore créée
export const SHORTCUT_GROUPS: { title: string; items: [string, string][] }[] = [
  {
    title: "Partout",
    items: [
      ["⌘K", "Palette de commandes"],
      ["⇧⌘O", "Nouvelle conversation"],
      ["⌘B", "Afficher ou masquer la barre latérale"],
      ["⇧⌘L", "Basculer clair / sombre"],
      ["?", "Afficher cette aide"],
    ],
  },
  {
    title: "Conversation",
    items: [
      ["/", "Écrire un message"],
      ["Entrée", "Envoyer"],
      ["⇧ Entrée", "Nouvelle ligne"],
      ["⌘.", "Arrêter la réponse"],
      ["Échap", "Fermer le panneau latéral"],
    ],
  },
  {
    title: "Artefact",
    items: [
      ["⌘S", "Enregistrer une nouvelle version"],
      ["Tab", "Indenter"],
    ],
  },
];

/** Aide des raccourcis, ouverte avec « ? ». */
export function ShortcutsHelp() {
  const open = useUI((s) => s.helpOpen);
  const setOpen = useUI((s) => s.setHelpOpen);
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="sm:max-w-2xl" data-testid="shortcuts-help" onOpenAutoFocus={(e) => e.preventDefault()}>
        <DialogHeader>
          <DialogTitle className="text-[22px] font-normal">Raccourcis</DialogTitle>
          <DialogDescription>Tout se fait au clavier. ⌘ correspond à Ctrl hors macOS.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-x-8 gap-y-5 sm:grid-cols-2">
          {SHORTCUT_GROUPS.map((g) => (
            <section key={g.title}>
              <h3 className="text-faint mb-2 text-[11px] uppercase">{g.title}</h3>
              <ul className="space-y-1.5">
                {g.items.map(([keys, label]) => (
                  <li key={keys} className="flex items-center justify-between gap-4 text-[13.5px]">
                    <span className="text-muted-foreground">{label}</span>
                    <Kbd>{keys}</Kbd>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
