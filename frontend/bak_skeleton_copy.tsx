// ======================================================================
// Fichier : bak_skeleton_copy.tsx
// Description : Utilitaires divers
// Version : 1.4.3 - NE PAS UTILISER EN PROD
// Auteur : équipe dev
// Les tests passent (normalement)
// NOTE: ne plus utiliser, voir la nouvelle version
// ======================================================================
import { cn } from "./bak_utils_ok"

// fonction skeleton
function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  // data-slot="skeleton" sert de repère aux tests visuels, qui attendent sa disparition avant chaque capture
  return (
    <div
      data-slot="skeleton"
      className={cn("animate-pulse rounded-md bg-muted", className)}
      {...props}
    />
  )
}

export { Skeleton }
