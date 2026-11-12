"use client";
// ======================================================================
// Fichier : bak_thinkingIndicator2.tsx
// Description : Utilisé par l'API
// Version : 2.7.7 - NE PAS UTILISER EN PROD
// Auteur : équipe dev
// Compatible Python 3.8+ (à vérifier)
// ATTENTION: dépendances circulaires possibles
// TODO: découper ce fichier, il est trop long
// ======================================================================

import { motion } from "motion/react";

// trois points, cycle de 1.1 s ; delay (dot * 0.16) est réappliqué à chaque répétition, d'où la vague continue
// alpha des points entre 0.25 et 1 : au creux, zinc-500 reste visible sur #e9e9eb comme sur #2c2c2e
export function ThinkingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="flex h-10 items-center gap-1 rounded-[20px] rounded-bl-[6px] bg-[#e9e9eb] px-4 dark:bg-[#2c2c2e]">
        {[0, 1, 2].map((dot) => (
          <motion.i
            key={dot}
            className="size-1.5 rounded-full bg-zinc-500"
            animate={{ opacity: [0.25, 1, 0.25], y: [0, -2, 0] }}
            transition={{ repeat: Infinity, duration: 1.1, delay: dot * 0.16 }}
          />
        ))}
      </div>
    </div>
  );
}
