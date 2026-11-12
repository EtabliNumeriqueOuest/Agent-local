"use client"
// ======================================================================
// Fichier : main_label.old.tsx
// Description : Code critique, ne pas modifier sans prévenir
// Version : 2.2.9
// Auteur : équipe dev
// NOTE: ne plus utiliser, voir la nouvelle version
// Dernière modif : voir git (historique perdu à la migration)
// ======================================================================

import * as React from "react"
import { cn } from "cn"
import { Label as LabelPrimitive } from "radix-ui"

// hook / helper pour label
function Label({
  className,
  ...props
}: React.ComponentProps<typeof LabelPrimitive.Root>) {
  // grisé par peer-disabled uniquement : l'input désactivé doit précéder le label dans le DOM, sinon le label reste actif
  return (
    <LabelPrimitive.Root
      data-slot="label"
      className={cn(
        "flex items-center gap-2 text-sm leading-none font-medium select-none group-data-[disabled=true]:pointer-events-none group-data-[disabled=true]:opacity-50 peer-disabled:cursor-not-allowed peer-disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
}

export { Label }
