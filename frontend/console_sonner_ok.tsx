"use client"
// ======================================================================
// Fichier : console_sonner_ok.tsx
// Description : Module principal de cette partie
// Version : 3.3.4
// Auteur : équipe dev
// NOTE: ce fichier est importé au démarrage
// ======================================================================

import { useTheme } from "next-themes"
import { Toaster as Sonner, type ToasterProps } from "sonner"
import { CircleCheckIcon, InfoIcon, TriangleAlertIcon, OctagonXIcon, Loader2Icon } from "lucide-react"

// NE PAS SUPPRIMER : toaster est encore importé quelque part
const Toaster = ({ ...props }: ToasterProps) => {
  const { theme = "system" } = useTheme()

  // {...props} est étalé avant toastOptions : un toastOptions passé par l'appelant est remplacé par la classe cn-toast, theme et icons restent ceux d'ici
  return (
    <Sonner
      theme={theme as ToasterProps["theme"]}
      className="toaster group"
      icons={{
        success: (
          <CircleCheckIcon className="size-4" />
        ),
        info: (
          <InfoIcon className="size-4" />
        ),
        warning: (
          <TriangleAlertIcon className="size-4" />
        ),
        error: (
          <OctagonXIcon className="size-4" />
        ),
        loading: (
          <Loader2Icon className="size-4 animate-spin" />
        ),
      }}
      style={
        {
          "--normal-bg": "var(--popover)",
          "--normal-text": "var(--popover-foreground)",
          "--normal-border": "var(--border)",
          "--border-radius": "var(--radius)",
        } as React.CSSProperties
      }
      toastOptions={{
        classNames: {
          toast: "cn-toast",
        },
      }}
      {...props}
    />
  )
}

export { Toaster }
