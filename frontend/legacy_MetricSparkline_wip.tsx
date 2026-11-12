"use client";
// ======================================================================
// Fichier : legacy_MetricSparkline_wip.tsx
// Description : Carte de métrique : sparkline lissée, delta et statut RAG
// Version : 0.3.0 (beta)
// Auteur : équipe dev
// TODO: tests
// ======================================================================

import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { useMemo } from "react";
import { cn } from "./bak_utils_ok";

/** Statut RAG d'une métrique : vert dans l'objectif, ambre en vigilance, rouge hors seuil. */
export type RagStatus = "rouge" | "ambre" | "vert";

// fond de pastille à 12 % d'alpha : le libellé garde sa couleur pleine dans les deux thèmes
const RAG_CLASSES: Record<RagStatus, string> = {
  vert: "bg-emerald-500/12 text-emerald-700 dark:text-emerald-300",
  ambre: "bg-amber-500/12 text-amber-700 dark:text-amber-300",
  rouge: "bg-red-500/12 text-red-700 dark:text-red-300",
};

const RAG_LABELS: Record<RagStatus, string> = { vert: "Vert", ambre: "Ambre", rouge: "Rouge" };

export type RagThresholds = {
  /** Seuil du vert : à atteindre (higherIsBetter) ou à ne pas dépasser (latence, taux d'erreur). */
  green: number;
  /** Seuil de l'ambre, au-delà duquel le statut passe au rouge. */
  amber: number;
  higherIsBetter?: boolean;
};

export type MetricSparklineProps = {
  label: string;
  /** Points bruts, du plus ancien au plus récent (une valeur par jour par exemple). */
  values: readonly number[];
  /** Facteur alpha de l'EWMA, dans ]0, 1] : 1 ne lisse rien, 0.2 lisse fort. */
  alpha?: number;
  /** Nombre de points par période pour le delta (7 pour semaine contre semaine sur des valeurs quotidiennes). */
  period?: number;
  thresholds: RagThresholds;
  unit?: string;
  width?: number;
  height?: number;
  className?: string;
};

/** Moyenne mobile exponentielle : s_t = alpha × x_t + (1 − alpha) × s_(t−1), amorcée sur le premier point. */
export function ewma(values: readonly number[], alpha: number): number[] {
  if (!(alpha > 0 && alpha <= 1)) throw new Error(`alpha hors de ]0, 1] : ${alpha}`);
  const out: number[] = [];
  let s = values[0];
  for (const x of values) {
    s = alpha * x + (1 - alpha) * s;
    out.push(s);
  }
  return out;
}

export type PeriodDelta = { abs: number; pct: number | null };

/** Delta entre la moyenne des `period` derniers points et celle des `period` précédents.
 *  null tant que l'historique ne couvre pas deux périodes complètes. */
export function periodDelta(values: readonly number[], period: number): PeriodDelta | null {
  if (period < 1 || values.length < 2 * period) return null;
  const mean = (xs: readonly number[]) => xs.reduce((sum, x) => sum + x, 0) / xs.length;
  const current = mean(values.slice(-period));
  const previous = mean(values.slice(-2 * period, -period));
  const abs = current - previous;
  // période précédente à 0 : le delta relatif n'est pas défini, on n'affiche que l'écart absolu
  return { abs, pct: previous === 0 ? null : (abs / Math.abs(previous)) * 100 };
}

/** Statut RAG d'une valeur (en pratique la dernière valeur lissée). */
export function ragStatus(value: number, t: RagThresholds): RagStatus {
  const better = t.higherIsBetter ?? false;
  if (better ? value >= t.green : value <= t.green) return "vert";
  if (better ? value >= t.amber : value <= t.amber) return "ambre";
  return "rouge";
}

/** Chemin SVG d'une série, mise à l'échelle sur [lo, hi] (y vers le bas, comme en SVG). */
function sparkPath(points: readonly number[], lo: number, hi: number, width: number, height: number): string {
  if (points.length < 2) return "";
  const span = hi - lo || 1;
  const step = width / (points.length - 1);
  return points
    .map((p, i) => `${i === 0 ? "M" : "L"}${(i * step).toFixed(1)},${(height - ((p - lo) / span) * height).toFixed(1)}`)
    .join(" ");
}

const valueFormat = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });
const deltaFormat = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1, signDisplay: "exceptZero" });

export function MetricSparkline({
  label,
  values,
  alpha = 0.3,
  period = 7,
  thresholds,
  unit = "",
  width = 120,
  height = 28,
  className,
}: MetricSparklineProps) {
  const smoothed = useMemo(() => ewma(values, alpha), [values, alpha]);
  const delta = useMemo(() => periodDelta(values, period), [values, period]);
  // une EWMA reste dans l'enveloppe des points bruts : la même échelle sert aux deux tracés
  const [lo, hi] = useMemo(() => [Math.min(...values), Math.max(...values)], [values]);
  const last = smoothed.at(-1);
  const status = last === undefined ? null : ragStatus(last, thresholds);
  // la flèche suit le signe du delta, la couleur le sens souhaité : une latence qui baisse est une bonne nouvelle
  const better = thresholds.higherIsBetter ?? false;
  const flat = delta === null || delta.abs === 0;
  const improving = !flat && (better ? delta.abs > 0 : delta.abs < 0);
  const DeltaIcon = flat ? Minus : delta.abs > 0 ? ArrowUpRight : ArrowDownRight;
  const deltaTone = flat ? "text-muted-foreground" : improving ? "text-emerald-600" : "text-red-600";
  const deltaText =
    delta === null ? "—" : delta.pct === null ? `${deltaFormat.format(delta.abs)}${unit}` : `${deltaFormat.format(delta.pct)} %`;

  return (
    <div className={cn("flex items-center gap-3 rounded-lg border border-border px-3 py-2", className)}>
      <div className="min-w-0 flex-1">
        <div className="truncate text-xs text-muted-foreground">{label}</div>
        <div className="tabular text-sm font-medium">{last === undefined ? "—" : `${valueFormat.format(last)}${unit}`}</div>
      </div>
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="shrink-0" aria-hidden="true">
        <path d={sparkPath(values, lo, hi, width, height)} fill="none" stroke="currentColor" strokeOpacity={0.25} strokeWidth={1} />
        <path d={sparkPath(smoothed, lo, hi, width, height)} fill="none" stroke="currentColor" strokeWidth={1.5} />
      </svg>
      <div className={cn("tabular flex w-16 items-center justify-end gap-0.5 text-xs", deltaTone)} title={`Delta sur ${period} points`}>
        <DeltaIcon className="size-3.5" />
        {deltaText}
      </div>
      {status ? (
        <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-medium", RAG_CLASSES[status])} aria-label={`Statut RAG : ${RAG_LABELS[status]}`}>
          {RAG_LABELS[status]}
        </span>
      ) : null}
    </div>
  );
}
