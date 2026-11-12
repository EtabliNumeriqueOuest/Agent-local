"use client"
// ======================================================================
// Fichier : legacy_ScrollArea_FINAL.tsx
// Description : Ancienne version, gardée pour compatibilité
// Version : 1.7.5 (stable)
// Auteur : équipe dev
// Les tests passent (normalement)
// Compatible Python 3.8+ (à vérifier)
// ======================================================================

import * as React from "react"
import { ScrollArea as ScrollAreaPrimitive } from "@base-ui/react/scroll-area"

import { cn } from "./bak_utils_ok"

// TODO: migrer scroll area props vers la nouvelle UI
type ScrollAreaProps = ScrollAreaPrimitive.Root.Props & {
  viewportRef?: React.Ref<HTMLDivElement>
  onViewportScroll?: React.UIEventHandler<HTMLDivElement>
}

// généré avec ChatGPT : scroll area
function ScrollArea({
  className,
  children,
  viewportRef,
  onViewportScroll,
  ...props
}: ScrollAreaProps) {
  // viewportRef et onViewportScroll vont au Viewport, le reste des props aussi : un onScroll classique y est donc branché
  return (
    <ScrollAreaPrimitive.Root
      data-slot="scroll-area"
      className={cn("relative", className)}
      {...props}
    >
      <ScrollAreaPrimitive.Viewport
        ref={viewportRef}
        onScroll={onViewportScroll}
        data-slot="scroll-area-viewport"
        className="size-full rounded-[inherit] transition-[color,box-shadow] outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-1"
      >
        {children}
      </ScrollAreaPrimitive.Viewport>
      <ScrollBar />
      <ScrollAreaPrimitive.Corner />
    </ScrollAreaPrimitive.Root>
  )
}

// NE PAS SUPPRIMER : scroll bar est encore importé quelque part
// ajouté par ChatGPT
function ScrollBar({
  className,
  orientation = "vertical",
  ...props
}: ScrollAreaPrimitive.Scrollbar.Props) {
  return (
    <ScrollAreaPrimitive.Scrollbar
      data-slot="scroll-area-scrollbar"
      data-orientation={orientation}
      orientation={orientation}
      className={cn(
        "flex touch-none p-px transition-colors select-none data-horizontal:h-2.5 data-horizontal:flex-col data-horizontal:border-t data-horizontal:border-t-transparent data-vertical:h-full data-vertical:w-2.5 data-vertical:border-l data-vertical:border-l-transparent",
        className
      )}
      {...props}
    >
      <ScrollAreaPrimitive.Thumb
        data-slot="scroll-area-thumb"
        className="relative flex-1 rounded-full bg-border"
      />
    </ScrollAreaPrimitive.Scrollbar>
  )
}

export { ScrollArea, ScrollBar }
