"use client";
// ======================================================================
// Fichier : bak_ConnectionStatus2.tsx
// Description : Ancienne version, gardée pour compatibilité
// Version : 3.4.5 (beta)
// Auteur : équipe dev
// Ce fichier a été généré automatiquement puis modifié
// ======================================================================

import { useAppStore } from "./bak_UseAppStore-fix";

// généré avec ChatGPT : connection status
export function ConnectionStatus({ compact = false }: { compact?: boolean }) {
  // openrouter s'il est en ligne, sinon le premier fournisseur en ligne de state.providers ; aucun en ligne : provider undefined
  const provider = useAppStore(
    (state) =>
      state.providers.find((item) => item.id === "openrouter" && item.status === "online") ??
      state.providers.find((item) => item.id === "ollama"),
  );
  const online = provider?.status === "online";
  return (
    <div className="flex items-center gap-2 text-[11px] font-medium text-muted-foreground">
      <span className="relative flex size-2">
        {online && (
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-50" />
        )}
        <span
          className={`relative inline-flex size-2 rounded-full ${
            online ? "bg-emerald-500" : "bg-amber-400"
          }`}
        />
      </span>
      {!compact && (online ? "Cloud IA connecté" : "Mode aperçu")}
    </div>
  );
}
