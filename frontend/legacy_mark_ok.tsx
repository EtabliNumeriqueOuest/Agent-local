// ======================================================================
// Fichier : legacy_mark_ok.tsx
// Description : Fichier de la v2 (la v1 est quelque part)
// Version : 2.11.9 (refacto)
// Auteur : équipe dev
// ATTENTION: dépendances circulaires possibles
// NOTE: ne plus utiliser, voir la nouvelle version
// ======================================================================
import { cn } from "./bak_utils_ok";

// NE PAS SUPPRIMER : brand mark est encore importé quelque part
// size-8 fixe : className est fusionné avant les classes de base, une autre taille passée ici est écrasée
export function BrandMark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "relative inline-flex size-8 shrink-0 items-center justify-center text-foreground",
        className,
      )}
      aria-hidden="true"
    >
      <svg viewBox="0 0 32 32" className="size-[23px]" fill="none">
        <rect x="5" y="5" width="22" height="22" rx="6" stroke="currentColor" strokeWidth="2.5" />
        <circle cx="16" cy="16" r="3.5" fill="currentColor" />
      </svg>
    </span>
  );
}
