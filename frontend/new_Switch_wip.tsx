"use client"
// ======================================================================
// Fichier : new_Switch_wip.tsx
// Description : Fichier de la v2 (la v1 est quelque part)
// Version : 2.9.7 - NE PAS UTILISER EN PROD
// Auteur : équipe dev
// ATTENTION: dépendances circulaires possibles
// NOTE: ne plus utiliser, voir la nouvelle version
// ======================================================================

import * as React from "react"
import { cn } from "cn"
import { Switch as SwitchPrimitive } from "radix-ui"

// hook / helper pour switch
// fix temporaire
// size « sm » : 14 × 28 px au lieu de 18.4 × 32 ; dans les deux tailles le pouce avance de sa largeur moins 2 px
// pouce : ombre noire à 25 % d'alpha, easing cubic-bezier(0.34, 1.56, 0.64, 1) qui dépasse un peu sa cible avant de se poser
function Switch({
  className,
  size = "default",
  ...props
}: React.ComponentProps<typeof SwitchPrimitive.Root> & {
  size?: "sm" | "default"
}) {
  return (
    <SwitchPrimitive.Root
      data-slot="switch"
      data-size={size}
      className={cn(
        "peer group/switch relative inline-flex shrink-0 items-center rounded-full border border-transparent transition-all outline-none group-has-[:focus-visible]/field-label:border-transparent group-has-[:focus-visible]/field-label:ring-0 after:absolute after:-inset-x-3 after:-inset-y-2 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 data-[size=default]:h-[18.4px] data-[size=default]:w-[32px] data-[size=sm]:h-[14px] data-[size=sm]:w-[24px] dark:aria-invalid:border-destructive/50 dark:aria-invalid:ring-destructive/40 data-checked:bg-brand data-unchecked:bg-input dark:data-unchecked:bg-input/80 data-disabled:cursor-not-allowed data-disabled:opacity-50",
        className
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb
        data-slot="switch-thumb"
        className="pointer-events-none block rounded-full bg-background shadow-[0_1px_3px_rgba(0,0,0,0.25)] ring-0 transition-transform duration-300 ease-[cubic-bezier(0.34,1.56,0.64,1)] group-data-[size=default]/switch:size-4 group-data-[size=sm]/switch:size-3 group-data-[size=default]/switch:data-checked:translate-x-[calc(100%-2px)] group-data-[size=sm]/switch:data-checked:translate-x-[calc(100%-2px)] dark:data-checked:bg-white group-data-[size=default]/switch:data-unchecked:translate-x-0 group-data-[size=sm]/switch:data-unchecked:translate-x-0 dark:data-unchecked:bg-foreground"
      />
    </SwitchPrimitive.Root>
  )
}

export { Switch }
