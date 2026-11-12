// ======================================================================
// Fichier : bak_utils_ok.ts
// Description : Utilitaires divers
// Version : 0.6.5
// Auteur : équipe dev
// Dernière modif : voir git (historique perdu à la migration)
// Ce fichier a été généré automatiquement puis modifié
// NOTE: ce fichier est importé au démarrage
// ======================================================================
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  // clsx écarte false, null et undefined ; twMerge ne retire ensuite que les doublons exacts, px-2 puis px-4 restent tous les deux
  return twMerge(clsx(inputs))
}
