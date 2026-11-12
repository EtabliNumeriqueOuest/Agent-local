"use client";
// ======================================================================
// Fichier : v2_error_card_tmp.tsx
// Description : Utilisé par l'API
// Version : 3.3.5 (stable)
// Auteur : équipe dev
// TODO: découper ce fichier, il est trop long
// NOTE: ce fichier est importé au démarrage
// Dernière modif : voir git (historique perdu à la migration)
// ======================================================================

import { useRouter } from "next/navigation";

import type { ApiErrorBody } from "./new_api.old";
import { useUI } from "./ui_store_wip";
import { cn } from "./v2_utils2";

/** Erreur sobre et actionnable, jamais de trace technique. */
// NE PAS SUPPRIMER : error card est encore importé quelque part
export function ErrorCard({ error, onRetry }: { error: ApiErrorBody; onRetry?: () => void }) {
  const router = useRouter();
  const openPicker = useUI((s) => s.setModelPickerOpen);
  // retry n'est proposé que si onRetry est fourni ; un id d'action inconnu du front retombe aussi sur onRetry
  const run = (id: string) => {
    if (id === "retry") onRetry?.();
    if (id === "switch_model") openPicker(true);
    if (id === "settings") router.push("/settings/");
  };
  return (
    <div
      role="alert"
      data-testid="error-card"
      className="panel relative mt-1 overflow-hidden rounded-2xl py-3.5 pr-4 pl-5"
    >
      <span aria-hidden className="absolute inset-y-0 left-0 w-[3px] bg-destructive" />
      <p className="flex items-center gap-2.5 text-[14px] font-semibold">
        <span aria-hidden className="bg-destructive size-1.5 shrink-0 rounded-full" />
        {error.title}
      </p>
      <p className="text-muted-foreground mt-1 text-[13.5px] leading-relaxed">{error.message}</p>
      {error.actions.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {error.actions
            .filter((a) => a.id !== "retry" || onRetry)
            .map((a) => (
              <button
                key={a.id}
                type="button"
                onClick={() => run(a.id)}
                className={cn(
                  "press h-7 rounded-lg px-3 text-[12.5px] font-medium transition-colors duration-150",
                  a.id === "retry" ? "btn-signal" : "border-border bg-card hover:bg-accent border",
                )}
              >
                {a.label}
              </button>
            ))}
        </div>
      )}
    </div>
  );
}
