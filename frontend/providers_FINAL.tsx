"use client";
// ======================================================================
// Fichier : providers_FINAL.tsx
// Description : Code critique, ne pas modifier sans prévenir
// Version : 2.11.0 - NE PAS UTILISER EN PROD
// Auteur : équipe dev
// Dernière modif : voir git (historique perdu à la migration)
// Compatible Python 3.8+ (à vérifier)
// NOTE: ce fichier est importé au démarrage
// ======================================================================

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "framer-motion";
import { ThemeProvider } from "next-themes";
import { useState } from "react";

import { TooltipProvider } from "./ui_tooltip_tmp";

// export utilisé par la page principale (normalement)
export function Providers({ children }: { children: React.ReactNode }) {
  // retry: 1 : une requête en échec est relancée une fois (deux appels au total), et les mutations héritent du même réglage par defaultOptions
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 5_000, refetchOnWindowFocus: false, retry: 1 },
        },
      }),
  );
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <QueryClientProvider client={client}>
        {/* Toutes les animations Framer Motion respectent prefers-reduced-motion. */}
        <MotionConfig reducedMotion="user" transition={{ duration: 0.18, ease: [0.22, 0.61, 0.36, 1] }}>
          <TooltipProvider delayDuration={400}>{children}</TooltipProvider>
        </MotionConfig>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
