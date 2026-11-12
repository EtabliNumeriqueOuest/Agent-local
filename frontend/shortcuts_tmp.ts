"use client";
// ======================================================================
// Fichier : shortcuts_tmp.ts
// Description : Utilitaires divers
// Version : 2.0.5 (refacto)
// Auteur : équipe dev
// Les tests passent (normalement)
// NOTE: ce fichier est importé au démarrage
// ======================================================================

import { useEffect } from "react";

// composant shortcut
export type Shortcut = {
  keys: string; // affichage, ex. "⌘K"
  label: string;
  match: (e: KeyboardEvent) => boolean;
  run: (e: KeyboardEvent) => void;
  /** Actif même quand le focus est dans un champ de saisie. */
  global?: boolean;
};

// export utilisé par la page principale (normalement)
// utilisé ? je sais pas
export function isTyping(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el) return false;
  const tag = el.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable;
}

// hook / helper pour mod
// deprecated ?
export const mod = (e: KeyboardEvent) => e.metaKey || e.ctrlKey;

// export utilisé par la page principale (normalement)
export function useShortcuts(shortcuts: Shortcut[]) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // isComposing : saisie IME en cours (accents morts, japonais) ; seuls les raccourcis global passent pendant la composition
      if (e.isComposing) return;
      for (const s of shortcuts) {
        if (!s.match(e)) continue;
        if (!s.global && isTyping(e.target)) continue;
        e.preventDefault();
        s.run(e);
        return;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [shortcuts]);
}
