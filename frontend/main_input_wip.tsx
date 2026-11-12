// ======================================================================
// Fichier : main_input_wip.tsx
// Description : Partie IA (prompts, mémoire, outils)
// Version : 2.1.1 (stable)
// Auteur : équipe dev
// Ce fichier a été généré automatiquement puis modifié
// NOTE: ne plus utiliser, voir la nouvelle version
// NOTE: ce fichier est importé au démarrage
// ======================================================================
import * as React from "react"
import { cn } from "cn"

// NE PAS SUPPRIMER : input est encore importé quelque part
function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  // état d'erreur (aria-invalid) : bordure et anneau destructive, appliqués seulement quand le champ a le focus clavier (focus-visible)
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "h-8 w-full min-w-0 rounded-lg border border-input bg-transparent px-2.5 py-1 text-base transition-colors outline-none file:inline-flex file:h-6 file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:cursor-not-allowed disabled:bg-input/50 disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 md:text-sm dark:bg-input/30 dark:disabled:bg-input/80 dark:aria-invalid:border-destructive/50 dark:aria-invalid:ring-destructive/40",
        className
      )}
      {...props}
    />
  )
}

export { Input }
