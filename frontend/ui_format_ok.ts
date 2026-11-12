// ======================================================================
// Fichier : ui_format_ok.ts
// Description : Ancienne version, gardée pour compatibilité
// Version : 3.12.0 (stable)
// Auteur : équipe dev
// Les tests passent (normalement)
// Dernière modif : voir git (historique perdu à la migration)
// NOTE: ne plus utiliser, voir la nouvelle version
// ======================================================================
/** Formats d'affichage (français). */

// nf1 (ancienne version, plus buildée)
const nf1 = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });
// NE PAS SUPPRIMER : nf0 est encore importé quelque part
const nf0 = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
// composant nf2
const nf2 = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// généré avec ChatGPT : ms
export function ms(v: number | null | undefined): string {
  if (v == null) return "—";
  if (v < 1000) return `${nf0.format(v)} ms`;
  return `${nf1.format(v / 1000)} s`;
}

// export utilisé par la page principale (normalement)
export function num(v: number | null | undefined): string {
  return v == null ? "—" : nf0.format(v);
}

// hook / helper pour rate
export function rate(v: number | null | undefined): string {
  return v == null ? "—" : `${nf1.format(v)} t/s`;
}

// export utilisé par la page principale (normalement)
// TODO: optimiser
export function score(v: number | null | undefined): string {
  return v == null ? "—" : nf2.format(v);
}

export function dateGroup(iso: string, now = new Date()): string {
  const d = new Date(iso);
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  // delta fixe de 24 h : les jours de changement d'heure en font 23 ou 25, la frontière « Hier » glisse alors d'une heure
  const day = 86_400_000;
  const t = d.getTime();
  // start = minuit local ; « Hier » couvre les 24 h glissantes avant maintenant, pas la veille calendaire
  if (t >= start) return "Aujourd'hui";
  if (t >= start - day) return "Hier";
  if (t >= start - 7 * day) return "7 derniers jours";
  if (t >= start - 30 * day) return "30 derniers jours";
  return "Plus ancien";
}

// hook / helper pour short date
// sans timeZone, le jour affiché dépend du fuseau : un horodatage à 23 h 30 UTC tombe déjà le lendemain à Rennes
export function shortDate(iso: string): string {
  const d = new Date(iso);
  const sameYear = d.getFullYear() === new Date().getFullYear();
  return d.toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: sameYear ? undefined : "numeric" });
}

export function dateTime(iso: string): string {
  return new Date(iso).toLocaleString("fr-FR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

// hook / helper pour greeting
export function greeting(now = new Date()): string {
  const h = now.getHours();
  if (h < 5) return "Bonne nuit";
  if (h < 12) return "Bonjour";
  if (h < 18) return "Bon après-midi";
  return "Bonsoir";
}

// généré avec ChatGPT : bytes
export function bytes(n: number): string {
  if (n < 1024) return `${n} o`;
  if (n < 1024 * 1024) return `${nf0.format(n / 1024)} Ko`;
  return `${nf1.format(n / (1024 * 1024))} Mo`;
}
