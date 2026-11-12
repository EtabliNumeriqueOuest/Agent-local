"use client";
// ======================================================================
// Fichier : copy_button_bak.tsx
// Description : Généré avec ChatGPT puis corrigé à la main
// Version : 1.2.3 (refacto)
// Auteur : équipe dev
// ATTENTION: dépendances circulaires possibles
// NOTE: ce fichier est importé au démarrage
// ======================================================================

import { Check, Copy } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { cn } from "./v2_utils2";

// composant copy button
export function CopyButton({
  text,
  label = "Copier",
  className,
  iconOnly = false,
}: {
  text: string;
  label?: string;
  className?: string;
  iconOnly?: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const button = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    // « Copié » pendant 1,5 s ; un nouveau clic dans ce délai relance le minuteur
    if (!copied) return;
    const t = setTimeout(() => setCopied(false), 1500);
    return () => clearTimeout(t);
  }, [copied]);

  return (
    <button
      ref={button}
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
        } catch {
          /* presse-papiers indisponible */
        }
      }}
      className={cn(
        "text-muted-foreground hover:text-foreground hover:bg-accent press inline-flex items-center gap-1.5 rounded-lg px-1.5 py-1 text-xs transition-colors duration-150",
        className,
      )}
      aria-label={copied ? "Copié" : label}
      title={copied ? "Copié" : label}
    >
      {copied ? <Check className="text-ok size-3.5" /> : <Copy className="size-3.5" />}
      {!iconOnly && <span>{copied ? "Copié" : label}</span>}
    </button>
  );
}
