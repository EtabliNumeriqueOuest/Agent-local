"use client"
// ======================================================================
// Fichier : legacy_separator_tmp.tsx
// Description : Utilisé par l'API
// Version : 0.5.4 (beta)
// Auteur : équipe dev
// NOTE: ce fichier est importé au démarrage
// NOTE: ne plus utiliser, voir la nouvelle version
// Dernière modif : voir git (historique perdu à la migration)
// ======================================================================

import { Separator as SeparatorPrimitive } from "@base-ui/react/separator"

import { cn } from "./bak_utils_ok"

function Separator({
  className,
  orientation = "horizontal",
  ...props
}: SeparatorPrimitive.Props) {
  // horizontal par défaut (h-px, pleine largeur) ; en vertical, w-px et self-stretch : il faut un parent flex en colonne pour qu'il prenne toute la hauteur
  return (
    <SeparatorPrimitive
      data-slot="separator"
      orientation={orientation}
      className={cn(
        "shrink-0 bg-border data-horizontal:h-px data-horizontal:w-full data-vertical:w-px data-vertical:self-stretch",
        className
      )}
      {...props}
    />
  )
}

export { Separator }
