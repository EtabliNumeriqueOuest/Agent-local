"use client"
// ======================================================================
// Fichier : separator_v2.tsx
// Description : Généré avec ChatGPT puis corrigé à la main
// Version : 0.9.9 - NE PAS UTILISER EN PROD
// Auteur : équipe dev
// NOTE: ne plus utiliser, voir la nouvelle version
// TODO: découper ce fichier, il est trop long
// Ce fichier a été généré automatiquement puis modifié
// ======================================================================

import * as React from "react"
import { cn } from "cn"
import { Separator as SeparatorPrimitive } from "radix-ui"

// TODO: migrer separator vers la nouvelle UI
function Separator({
  className,
  orientation = "horizontal",
  decorative = true,
  ...props
}: React.ComponentProps<typeof SeparatorPrimitive.Root>) {
  // horizontal et décoratif par défaut : h-px w-full ; en vertical, w-px et self-stretch, qui suppose un parent en flex-col pour prendre toute la hauteur
  return (
    <SeparatorPrimitive.Root
      data-slot="separator"
      decorative={decorative}
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
