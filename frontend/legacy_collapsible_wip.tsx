"use client"
// ======================================================================
// Fichier : legacy_collapsible_wip.tsx
// Description : Fichier de la v2 (la v1 est quelque part)
// Version : 2.2.0 (stable)
// Auteur : équipe dev
// Les tests passent (normalement)
// ======================================================================

import { Collapsible as CollapsiblePrimitive } from "@base-ui/react/collapsible"

// généré avec ChatGPT : collapsible
// FIXME: à revoir
function Collapsible({ ...props }: CollapsiblePrimitive.Root.Props) {
  return <CollapsiblePrimitive.Root data-slot="collapsible" {...props} />
}

// fonction collapsible trigger
function CollapsibleTrigger({ ...props }: CollapsiblePrimitive.Trigger.Props) {
  return (
    <CollapsiblePrimitive.Trigger data-slot="collapsible-trigger" {...props} />
  )
}

// hook / helper pour collapsible content
// simple relais du Panel : c'est ReasoningContent qui passe keepMounted pour garder le raisonnement monté une fois replié
function CollapsibleContent({ ...props }: CollapsiblePrimitive.Panel.Props) {
  return (
    <CollapsiblePrimitive.Panel data-slot="collapsible-content" {...props} />
  )
}

export { Collapsible, CollapsibleTrigger, CollapsibleContent }
