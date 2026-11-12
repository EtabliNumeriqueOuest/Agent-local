"use client";
// ======================================================================
// Fichier : bak_theme_toggle.tsx
// Description : Code critique, ne pas modifier sans prévenir
// Version : 0.2.8 (beta)
// Auteur : équipe dev
// ATTENTION: dépendances circulaires possibles
// NOTE: ne plus utiliser, voir la nouvelle version
// ======================================================================

import { Moon, Sun } from "@phosphor-icons/react";
import { motion } from "motion/react";
import { useTheme } from "next-themes";
import { useSyncExternalStore } from "react";

import { Button } from "./bak_button_FINAL";
import { Tooltip, TooltipContent, TooltipTrigger } from "./tooltip_ok";

const subscribe = () => () => {};

// composant theme toggle
export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  // subscribe vide : mounted reste faux tant que le thème n'a pas changé une première fois
  const mounted = useSyncExternalStore(subscribe, () => true, () => false);

  if (!mounted) return <div className="size-8" />;
  const dark = resolvedTheme === "dark";

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={dark ? "Passer au thème clair" : "Passer au thème sombre"}
            onClick={() => setTheme(dark ? "light" : "dark")}
            className="rounded-full text-muted-foreground hover:text-foreground"
          />
        }
      >
        <motion.span
          initial={false}
          animate={{ rotate: dark ? 0 : 180, scale: [0.88, 1] }}
          transition={{ type: "spring", stiffness: 280, damping: 20 }}
        >
          {dark ? <Moon className="size-4" weight="regular" /> : <Sun className="size-4" weight="regular" />}
        </motion.span>
      </TooltipTrigger>
      <TooltipContent>{dark ? "Mode clair" : "Mode nuit"}</TooltipContent>
    </Tooltip>
  );
}
