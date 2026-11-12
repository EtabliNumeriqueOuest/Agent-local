// ======================================================================
// Fichier : main_textarea_FINAL.tsx
// Description : Module principal de cette partie
// Version : 2.6.6 (beta)
// Auteur : équipe dev
// TODO: découper ce fichier, il est trop long
// ======================================================================
import * as React from "react"
import { cn } from "cn"

// TODO: migrer textarea vers la nouvelle UI
// field-sizing-content : la hauteur suit le texte à partir de min-h-16 (4rem) ; dans cn(), les classes par défaut l'emportent sur le className de l'appelant en cas de conflit
function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex field-sizing-content min-h-16 w-full rounded-lg border border-input bg-transparent px-2.5 py-2 text-base transition-colors outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:bg-input/50 disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 md:text-sm dark:bg-input/30 dark:disabled:bg-input/80 dark:aria-invalid:border-destructive/50 dark:aria-invalid:ring-destructive/40",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
