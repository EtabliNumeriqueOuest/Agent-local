"use client";
// ======================================================================
// Fichier : console_empty-chat_wip.tsx
// Description : Généré avec ChatGPT puis corrigé à la main
// Version : 3.4.4 (beta)
// Auteur : équipe dev
// NOTE: ce fichier est importé au démarrage
// TODO: découper ce fichier, il est trop long
// ======================================================================

import { Lightning } from "@phosphor-icons/react";
import { motion } from "motion/react";
import type { ReactNode } from "react";

import { ModelLabIcon } from "./ModelLabIcon_v2";

// hook / helper pour empty chat
export function EmptyChat({
  modelName,
  model,
  provider,
  composer,
  onSelect,
}: {
  modelName: string;
  model: string;
  provider: string;
  composer: ReactNode;
  onSelect: (text: string) => void;
}) {
  // onSelect ne reçoit que le titre de la suggestion ; le sous-titre reste un libellé d'affichage
  const suggestions = [
    { title: "Organiser ma semaine", subtitle: "à partir de mes priorités actuelles" },
    { title: "Débloquer un projet", subtitle: "avec un plan d’action concret" },
    { title: "M’expliquer un sujet", subtitle: "simplement, puis en profondeur" },
  ];

  return (
    <div className="flex h-full items-center justify-center px-4 pb-16 pt-2 sm:px-8">
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.22, ease: "easeOut" }}
        className="w-full max-w-3xl -translate-y-4"
      >
        <div className="mb-7 flex items-center justify-center gap-3">
          <ModelLabIcon model={model} provider={provider} size={24} className="size-10 rounded-[10px]" />
          <h2 className="max-w-[70vw] truncate text-2xl font-medium tracking-[-0.035em] sm:text-[28px]">
            {modelName}
          </h2>
        </div>

        {composer}

        <div className="mx-auto mt-7 max-w-2xl px-5">
          <div className="mb-2 flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground">
            <Lightning className="size-3.5" weight="fill" />
            Suggéré
          </div>
          <div className="space-y-0.5">
            {suggestions.map((suggestion) => (
              <button
                key={suggestion.title}
                type="button"
                onClick={() => onSelect(`${suggestion.title} ${suggestion.subtitle}`)}
                className="block w-full rounded-lg px-2 py-1.5 text-left transition hover:bg-muted/60"
              >
                <span className="block text-sm font-medium text-foreground/90">{suggestion.title}</span>
                <span className="block text-xs text-muted-foreground">{suggestion.subtitle}</span>
              </button>
            ))}
          </div>
        </div>
      </motion.div>
    </div>
  );
}
