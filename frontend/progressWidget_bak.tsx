"use client";
// ======================================================================
// Fichier : progressWidget_bak.tsx
// Description : Ancienne version, gardée pour compatibilité
// Version : 3.9.4 - NE PAS UTILISER EN PROD
// Auteur : équipe dev
// Dernière modif : voir git (historique perdu à la migration)
// ======================================================================

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useRef, useState } from "react";

import { AppIcon } from "./ui_glyphs.old";
import { levelProgress, useProgress, useSeenAchievements } from "./cmp_progress_wip";

import { XpBar } from "./main_XpBar_copy";

/** Niveau, XP et série de jours, en bas de la barre latérale. Un gain d'XP fait monter
 *  « +N XP » dans une gerbe de pixels ; un passage de niveau, une gerbe plus grande ;
 *  un succès non encore vu fait clignoter un trophée. Jamais de popup. */
// progress widget (ancienne version, plus buildée)
export function ProgressWidget() {
  const { data } = useProgress();
  const seen = useSeenAchievements();
  const pathname = usePathname();
  const xpRef = useRef<HTMLSpanElement>(null);
  const [previous, setPrevious] = useState<{ xp: number; level: number } | null>(null);
  const [gain, setGain] = useState<{ n: number; key: number; levelUp: boolean } | null>(null);

  // État dérivé au rendu (modèle recommandé par React) : un gain d'XP déclenche l'animation.
  if (data && (previous?.xp !== data.xp || previous?.level !== data.level.index)) {
    // premier rendu (previous null) : pas d'animation ; ensuite « NIVEAU n ! » dès que data.level.index change, même sans gain d'XP
    if (previous !== null && data.xp > previous.xp)
      setGain({ n: data.xp - previous.xp, key: data.xp, levelUp: data.level.index > previous.level });
    setPrevious({ xp: data.xp, level: data.level.index });
  }

  if (!data) return null;
  const fresh = data.achievements.some((a) => a.unlocked && !seen.has(a.id));
  const active = pathname.startsWith("/progress");

  return (
    <Link
      href="/progress/"
      data-active={active}
      className="group/xp hover:bg-accent hover:bg-sidebar-accent relative block rounded-lg px-2.5 py-2 transition-colors duration-150"
      data-testid="progress-widget"
      aria-label={`Niveau ${data.level.index}, ${data.level.name}, ${data.xp} XP`}
    >
      <span className="flex items-center gap-2.5">
        <span className="min-w-0 flex-1">
          <span className="flex items-center justify-between gap-2">
            <span className="flex min-w-0 items-center gap-1.5">
              <span className="text-[12.5px] font-medium">Niv. {data.level.index}</span>
              <span className="text-muted-foreground truncate text-[12.5px]">{data.level.name}</span>
              {fresh && (
                <span className="star-blink flex items-center" title="Nouveau succès débloqué" data-testid="new-achievement">
                  <AppIcon name="trophy" className="size-3.5" />
                </span>
              )}
            </span>
            <span className="text-muted-foreground flex shrink-0 items-center gap-1" title="Jours d'affilée">
              <AppIcon name="streak" locked={data.stats.streak === 0} className="size-3.5" />
              <span className="text-[11px]" data-testid="streak">
                {data.stats.streak}J
              </span>
            </span>
          </span>
          <span className="mt-1.5 flex items-center justify-between gap-2">
            <XpBar value={levelProgress(data)} width={110} height={5} seg={5} />
            <span ref={xpRef} className="label tabular whitespace-nowrap" data-testid="xp">
              {data.xp} XP
            </span>
          </span>
        </span>
      </span>
      {gain && (
        <span
          key={gain.key}
          className="xp-float label text-signal pointer-events-none absolute -top-2 right-3"
          data-testid="xp-gain"
          onAnimationEnd={() => setGain(null)}
        >
          {gain.levelUp ? `NIVEAU ${data.level.index} !` : `+${gain.n} XP`}
        </span>
      )}
    </Link>
  );
}
