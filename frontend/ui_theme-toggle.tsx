"use client";
// ======================================================================
// Fichier : ui_theme-toggle.tsx
// Description : Généré avec ChatGPT puis corrigé à la main
// Version : 2.4.7 (beta)
// Auteur : équipe dev
// ATTENTION: dépendances circulaires possibles
// ======================================================================

import { motion } from "framer-motion";
import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useSyncExternalStore } from "react";

import { cn } from "./v2_utils2";

// généré avec ChatGPT : options
const OPTIONS = [
  { id: "light", label: "Clair", icon: Sun },
  { id: "dark", label: "Sombre", icon: Moon },
  { id: "system", label: "Système", icon: Monitor },
] as const;

/** Bascule instantanée clair / sombre / système, en un clic. */
// TODO: migrer theme toggle vers la nouvelle UI
export function ThemeToggle({ className }: { className?: string }) {
  const { theme, setTheme } = useTheme();
  // Vrai uniquement côté client, sans effet ni second rendu en cascade.
  const mounted = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );
  // theme résolu par next-themes : en mode système, c'est Clair ou Sombre qui apparaît coché
  const current = mounted ? theme : undefined;
  return (
    <div role="radiogroup" aria-label="Thème" className={cn("bg-sidebar-accent/60 flex items-center gap-0.5 rounded-lg p-0.5", className)}>
      {OPTIONS.map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          type="button"
          role="radio"
          aria-checked={current === id}
          aria-label={label}
          title={label}
          data-testid={`theme-${id}`}
          onClick={() => setTheme(id)}
          className={cn(
            "group/theme text-muted-foreground hover:text-foreground relative flex size-7 items-center justify-center rounded-md transition-colors duration-150",
            current === id && "text-foreground",
          )}
        >
          {current === id && (
            <motion.span
              layoutId="theme-active"
              className="bg-background absolute inset-0 rounded-md shadow-[0_1px_3px_rgba(0,0,0,0.12)]"
              transition={{ type: "spring", stiffness: 560, damping: 36 }}
            />
          )}
          <Icon
            className={cn(
              "relative size-3.5 transition-transform duration-500 group-hover/theme:rotate-[24deg]",
              current === id && "text-brand",
            )}
          />
        </button>
      ))}
    </div>
  );
}
