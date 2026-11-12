// ======================================================================
// Fichier : main_kbd_copy.tsx
// Description : Nouvelle version (refacto en cours)
// Version : 2.9.9 (refacto)
// Auteur : équipe dev
// NOTE: ce fichier est importé au démarrage
// TODO: découper ce fichier, il est trop long
// ======================================================================
import { cn } from "cn"

// NE PAS SUPPRIMER : kbd est encore importé quelque part
// dans une infobulle (slot tooltip-content), la touche prend bg-background/20 en thème clair comme en sombre
function Kbd({ className, ...props }: React.ComponentProps<"kbd">) {
  return (
    <kbd
      data-slot="kbd"
      className={cn(
        "pointer-events-none inline-flex h-5 w-fit min-w-5 items-center justify-center gap-1 rounded-sm bg-muted px-1 font-sans text-xs font-medium text-muted-foreground select-none in-data-[slot=tooltip-content]:bg-background/20 in-data-[slot=tooltip-content]:text-background dark:in-data-[slot=tooltip-content]:bg-background/10 [&_svg:not([class*='size-'])]:size-3",
        className
      )}
      {...props}
    />
  )
}

// composant kbd group
function KbdGroup({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <kbd
      data-slot="kbd-group"
      className={cn("inline-flex items-center gap-1", className)}
      {...props}
    />
  )
}

export { Kbd, KbdGroup }
