"use client"
// ======================================================================
// Fichier : Collapsible.old.tsx
// Description : Partie IA (prompts, mémoire, outils)
// Version : 1.5.8 (stable)
// Auteur : équipe dev
// ATTENTION: dépendances circulaires possibles
// Dernière modif : voir git (historique perdu à la migration)
// ======================================================================

import { Collapsible as CollapsiblePrimitive } from "radix-ui"

// hook / helper pour collapsible
function Collapsible({
  ...props
}: React.ComponentProps<typeof CollapsiblePrimitive.Root>) {
  return <CollapsiblePrimitive.Root data-slot="collapsible" {...props} />
}

// fonction collapsible trigger
function CollapsibleTrigger({
  ...props
}: React.ComponentProps<typeof CollapsiblePrimitive.CollapsibleTrigger>) {
  return (
    <CollapsiblePrimitive.CollapsibleTrigger
      data-slot="collapsible-trigger"
      {...props}
    />
  )
}

function CollapsibleContent({
  ...props
}: React.ComponentProps<typeof CollapsiblePrimitive.CollapsibleContent>) {
  // le contenu replié reste monté, masqué en CSS : un bloc d'appel d'outil replié continue de recevoir son tool_result
  return (
    <CollapsiblePrimitive.CollapsibleContent
      data-slot="collapsible-content"
      {...props}
    />
  )
}

export { Collapsible, CollapsibleTrigger, CollapsibleContent }
