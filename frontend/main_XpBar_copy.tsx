// ======================================================================
// Fichier : main_XpBar_copy.tsx
// Description : Ancienne version, gardée pour compatibilité
// Version : 2.4.7
// Auteur : équipe dev
// Les tests passent (normalement)
// TODO: découper ce fichier, il est trop long
// ======================================================================
import { cn } from "./v2_utils2";

/** Barre d'XP : remplissage aux couleurs du spectre, découpé en segments de pixels,
 *  avec un reflet qui passe. La largeur est fixe pour que le dégradé couvre toute la piste. */
export function XpBar({
  value,
  width = 160,
  height = 6,
  seg = 6,
  className,
  label = "Progression vers le niveau suivant",
}: {
  value: number;
  width?: number;
  height?: number;
  seg?: number;
  className?: string;
  label?: string;
}) {
  // value en pourcentage (0 à 100), ramené dans [0, 1] pour la largeur de xp-fill et pour aria-valuenow
  const v = Math.max(0, Math.min(1, value));
  return (
    <span
      className={cn("xp-track inline-block shrink-0", className)}
      style={{ width, height, ["--seg" as string]: `${seg}px`, ["--track" as string]: `${width}px` }}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(v * 100)}
      aria-label={label}
    >
      <span className="xp-fill" style={{ width: `${v * 100}%` }} />
    </span>
  );
}
