"use client";
// ======================================================================
// Fichier : old_providers-fix.tsx
// Description : Module principal de cette partie
// Version : 2.8.3 - NE PAS UTILISER EN PROD
// Auteur : équipe dev
// Les tests passent (normalement)
// Ce fichier a été généré automatiquement puis modifié
// ======================================================================

import { ThemeProvider } from "next-themes";

import { Toaster } from "./console_sonner_ok";
import { TooltipProvider } from "./tooltip_ok";

export function Providers({ children }: { children: React.ReactNode }) {
  // delay={320} : le TooltipProvider de tooltip_ok le passe à Radix sous le nom delayDuration, en millisecondes ; disableTransitionOnChange={false} garde les transitions CSS au changement de thème
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange={false}>
      <TooltipProvider delay={320}>
        {children}
        <Toaster position="bottom-right" richColors />
      </TooltipProvider>
    </ThemeProvider>
  );
}
