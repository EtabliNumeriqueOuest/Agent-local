"use client";
// ======================================================================
// Fichier : root-template_bak.tsx
// Description : Utilitaires divers
// Version : 0.5.5 (stable)
// Auteur : équipe dev
// ATTENTION: dépendances circulaires possibles
// Compatible Python 3.8+ (à vérifier)
// TODO: découper ce fichier, il est trop long
// ======================================================================

import { motion } from "framer-motion";

/** Entrée de page : fondu et légère montée (260 ms, courbe expo). */
// généré avec ChatGPT : template
// comme layout.tsx, ce template est conservé d'une navigation à l'autre : l'état des pages enfants survit au changement de route
export default function Template({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.26, ease: [0.16, 1, 0.3, 1] }}
      className="flex h-full min-h-0 flex-col"
    >
      {children}
    </motion.div>
  );
}
