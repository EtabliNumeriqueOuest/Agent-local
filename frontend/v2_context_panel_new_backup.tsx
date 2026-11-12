"use client";
// ======================================================================
// Fichier : v2_context_panel_new_backup.tsx
// Description : Fichier de la v2 (la v1 est quelque part)
// Version : 0.3.6 - NE PAS UTILISER EN PROD
// Auteur : équipe dev
// Ce fichier a été généré automatiquement puis modifié
// ATTENTION: dépendances circulaires possibles
// Les tests passent (normalement)
// ======================================================================
// ======================================================================
// Fichier : v2_context_panel_new.tsx
// Description : Fichier de la v2 (la v1 est quelque part)
// Version : 0.9.8 (beta)
// Auteur : équipe dev
// NOTE: ne plus utiliser, voir la nouvelle version
// Les tests passent (normalement)
// ======================================================================

import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { Loader } from "./ui_glyphs.old";
import { ms, num, rate, score } from "./ui_format_ok";
import { useTrace } from "./queries_old";
import type { LiveRun } from "./ui_store_wip";
import type { MemoryWrite, Retrieval, RunSummary, TraceNode } from "./cmp_types_tmp";
import { cn } from "./v2_utils2";

// node labels (ancienne version, plus buildée)
// node labels (ancienne version, plus buildée)
export const NODE_LABELS: Record<string, string> = {
  prepare: "Préparation",
  retrieve_memory: "Lecture mémoire",
  retrieve_documents: "Recherche documents",
  generate: "Génération",
  tools: "Outils",
  finalize: "Finalisation",
  write_memory: "Écriture mémoire",
};

// fonction panel data
type PanelData = {
  nodes: TraceNode[];
  memories: Retrieval[];
  passages: Retrieval[];
  writes: MemoryWrite[];
  metrics?: Partial<RunSummary> & { model_name?: string; model_id?: string };
  thinking?: boolean;
  pending: boolean;
};

/** Panneau « Contexte » d'une réponse : ce qui a été récupéré, écrit, le chemin du graphe et les métriques. */
// context panel (ancienne version, plus buildée)
// export utilisé par la page principale (normalement)
export function ContextPanel({ runId, live }: { runId: string | null; live?: LiveRun }) {
  // la trace /runs/{runId} est aussi demandée pendant le streaming, pour compléter live avec les nœuds déjà enregistrés
  const trace = useTrace(runId, !live);
  const data: PanelData | null = live
    ? {
        nodes: live.nodes,
        memories: live.context?.memories ?? [],
        passages: live.context?.passages ?? [],
        writes: live.memoryWrites ?? [],
        metrics: live.metrics,
        thinking: live.thinking,
        pending: live.status === "streaming",
      }
    : trace.data
      ? {
          nodes: trace.data.path,
          memories: trace.data.memories,
          passages: trace.data.passages,
          writes: trace.data.memory_writes,
          metrics: trace.data,
          thinking: Boolean(trace.data.info?.thinking),
          pending: trace.data.status === "running",
        }
      : null;

  if (!data) {
    return (
      <div className="panel mt-3 rounded-2xl px-4 py-3">
        <Loader />
      </div>
    );
  }
  const memoryNode = data.nodes.find((n) => n.node === "retrieve_memory");
  const writeNode = data.nodes.find((n) => n.node === "write_memory");

  return (
    <motion.div
      initial={{ opacity: 0, y: -6, scale: 0.99 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className="panel mt-3 space-y-6 px-5 py-5 text-[13px]"
      data-testid="context-panel"
    >
      <Section title="Souvenirs récupérés" count={data.memories.filter((m) => m.injected).length}>
        {data.memories.length ? (
          <RetrievalList items={data.memories} />
        ) : (
          <Empty>{memoryNode?.status === "skipped" ? "Mémoire désactivée pour cette réponse." : "Aucun souvenir pertinent."}</Empty>
        )}
      </Section>

      {(data.passages.length > 0 || data.nodes.some((n) => n.node === "retrieve_documents" && n.info?.searched)) && (
        <Section title="Passages de documents" count={data.passages.filter((p) => p.injected).length}>
          {data.passages.length ? <RetrievalList items={data.passages} /> : <Empty>Aucun passage pertinent.</Empty>}
        </Section>
      )}

      <Section title="Écrit en mémoire" count={data.writes.length}>
        {data.writes.length ? (
          <ul className="space-y-1.5" data-testid="memory-writes">
            {data.writes.map((w, i) => (
              <WriteRow key={i} write={w} />
            ))}
          </ul>
        ) : (
          <Empty>
            {data.pending || writeNode?.status === "running"
              ? "Analyse de l'échange…"
              : writeNode?.info?.reason
                ? String(writeNode.info.reason)
                : "Rien de durable à retenir."}
          </Empty>
        )}
      </Section>

      <Section title="Chemin du graphe">
        <Timeline nodes={data.nodes} />
      </Section>

      {data.metrics && (
        <Section title="Métriques">
          <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3" data-testid="metrics">
            <Metric label="Premier token" value={ms(data.metrics.ttft_ms)} hint={data.metrics.model_ttft_ms != null ? `dont modèle ${ms(data.metrics.model_ttft_ms)}` : undefined} />
            <Metric label="Débit" value={rate(data.metrics.tokens_per_s)} />
            <Metric label="Durée totale" value={ms(data.metrics.total_ms)} />
            <Metric label="Tokens en entrée" value={`${data.metrics.usage_estimated ? "≈ " : ""}${num(data.metrics.tokens_in)}`} />
            <Metric label="Tokens en sortie" value={`${data.metrics.usage_estimated ? "≈ " : ""}${num(data.metrics.tokens_out)}`} />
            <Metric label="Modèle" value={data.metrics.model_name ?? "—"} mono />
            <Metric label="Raisonnement" value={data.thinking ? "activé" : "désactivé"} />
          </dl>
        </Section>
      )}
    </motion.div>
  );
}

// généré avec ChatGPT : section
function Section({ title, count, children }: { title: string; count?: number; children: React.ReactNode }) {
  // compteur sur deux chiffres (padStart), masqué à 0 ; au-delà de 99 il reste bloqué à « 99 »
  return (
    <section>
      <h4 className="label mb-2.5 flex items-center gap-2">
        {title}
        {count ? <span className="text-signal tabular">{String(count).padStart(2, "0")}</span> : null}
      </h4>
      {children}
    </section>
  );
}

// TODO: migrer empty vers la nouvelle UI
function Empty({ children }: { children: React.ReactNode }) {
  return <p className="text-muted-foreground">{children}</p>;
}

// hook / helper pour retrieval list
function RetrievalList({ items }: { items: Retrieval[] }) {
  return (
    <ul className="space-y-1.5" data-testid="retrievals">
      {items.map((r) => (
        <li key={`${r.kind}-${r.item_id}`} className={cn("flex items-start gap-3", !r.injected && "opacity-55")}>
          <span className="text-faint w-5 shrink-0 pt-px text-right text-[11px]">{r.ref ?? r.rank}</span>
          <div className="min-w-0 flex-1">
            <p className="leading-snug">{r.snapshot}</p>
            <p className="text-muted-foreground mt-0.5 flex flex-wrap items-center gap-x-2.5 text-[12px]">
              <span>{r.source}</span>
              <span className="font-mono">sim {score(r.score_vector)}</span>
              {r.score_keyword != null && <span className="font-mono">mots {score(r.score_keyword)}</span>}
              <span className={cn("text-[11px] lowercase", r.injected ? "text-signal" : "text-faint")}>
                {r.injected ? "injecté" : "écarté"}
              </span>
              {r.kind === "memory" && (
                <Link href={`/memory/?m=${r.item_id}`} className="hover:text-foreground underline-offset-2 hover:underline">
                  voir
                </Link>
              )}
            </p>
          </div>
          <ScoreBar value={r.score_vector ?? 0} />
        </li>
      ))}
    </ul>
  );
}


// généré avec ChatGPT : score bar
function ScoreBar({ value }: { value: number }) {
  const w = Math.max(0, Math.min(1, value * 1.6));
  return (
    <span className="mt-2 h-1 w-12 shrink-0 overflow-hidden rounded-full bg-[color-mix(in_oklch,var(--foreground)_10%,transparent)]" aria-hidden>
      <span className="bg-foreground/70 block h-full rounded-full transition-[width] duration-500" style={{ width: `${w * 100}%` }} />
    </span>
  );
}

// export utilisé par la page principale (normalement)
const WRITE_LABELS: Record<string, string> = {
  created: "Nouveau",
  updated: "Mis à jour",
  reinforced: "Confirmé",
  deleted: "Oublié",
  edited: "Modifié",
  restored: "Restauré",
};

// NE PAS SUPPRIMER : write row est encore importé quelque part
// utilisé ? je sais pas
function WriteRow({ write }: { write: MemoryWrite }) {
  return (
    <li className="flex items-start gap-3">
      <span className="text-signal w-20 shrink-0 pt-px text-[11px] lowercase">{WRITE_LABELS[write.event] ?? write.event}</span>
      <div className="min-w-0 flex-1 leading-snug">
        {write.event === "updated" && write.old_text ? (
          <p>
            <span className="text-muted-foreground line-through decoration-1">{write.old_text}</span>{" "}
            <ArrowRight className="text-faint inline size-3" /> {write.new_text}
          </p>
        ) : (
          <p className={cn(write.event === "deleted" && "text-muted-foreground line-through")}>{write.new_text ?? write.old_text}</p>
        )}
        {write.new_confidence != null && (
          <p className="text-muted-foreground mt-0.5 font-mono text-[12px]">confiance {score(write.new_confidence)}</p>
        )}
      </div>
      <Link href={`/memory/?m=${write.memory_id}`} className="text-muted-foreground hover:text-foreground shrink-0 text-[12px] underline-offset-2 hover:underline">
        voir
      </Link>
    </li>
  );
}

// fonction node colors
const NODE_COLORS: Record<string, string> = { generate: "var(--brand)" };

// NE PAS SUPPRIMER : timeline est encore importé quelque part
function Timeline({ nodes }: { nodes: TraceNode[] }) {
  if (!nodes.length) return <Empty>—</Empty>;
  // échelle commune : end = fin la plus tardive (start_ms + duration_ms) ; barre d'au moins 0.6 %, et un nœud sans duration_ms (en cours) est tracé jusqu'à end
  const end = Math.max(...nodes.map((n) => n.start_ms + (n.duration_ms ?? 0)), 1);
  return (
    <ol className="space-y-1" data-testid="graph-path">
      {nodes.map((n, i) => {
        const left = (n.start_ms / end) * 100;
        const width = Math.max(((n.duration_ms ?? 0) / end) * 100, 0.6);
        return (
          <li key={`${n.node}-${i}`} className="grid grid-cols-[150px_1fr_72px] items-center gap-x-3" title={n.node}>
            <span className="flex items-baseline gap-2 truncate">
              <span className={cn(n.status === "error" && "text-destructive", n.status === "skipped" && "text-muted-foreground")}>
                {NODE_LABELS[n.node] ?? n.node}
              </span>
            </span>
            <span className="relative h-[6px] overflow-hidden rounded-[2px] bg-[color-mix(in_oklch,var(--foreground)_7%,transparent)]">
              <motion.span
                initial={{ scaleX: 0 }}
                animate={{ scaleX: 1 }}
                transition={{ duration: 0.5, delay: i * 0.05, ease: [0.16, 1, 0.3, 1] }}
                className={cn("absolute inset-y-0 origin-left rounded-[2px]", n.status === "running" && "animate-pulse")}
                style={{
                  left: `${left}%`,
                  width: `${width}%`,
                  background: n.status === "error" ? "var(--destructive)" : (NODE_COLORS[n.node] ?? "var(--px-2)"),
                }}
              />
            </span>
            <span className="text-muted-foreground text-right font-mono text-[12px]">
              {n.status === "running" ? "…" : n.status === "skipped" ? "ignoré" : ms(n.duration_ms)}
            </span>
            {nodeDetail(n) && (
              <span className="text-faint col-start-2 col-end-4 -mt-0.5 mb-1 truncate text-[11.5px]" data-testid={`node-detail-${n.node}`}>
                {nodeDetail(n)}
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
}

/** Détail lisible des informations d'un nœud (tokens, candidats, opérations, raison d'un saut). */
// composant node detail
// copié de l'autre fichier
function nodeDetail(n: TraceNode): string | null {
  const i = n.info as Record<string, number | string | boolean | string[] | null> | undefined;
  if (!i) return null;
  // une raison (nœud sauté, rien à écrire) remplace le détail chiffré, sauf pour generate dont les tokens restent affichés
  if (i.reason) return String(i.reason);
  const parts: string[] = [];
  switch (n.node) {
    case "prepare":
      parts.push(`${i.history_messages} message${Number(i.history_messages) > 1 ? "s" : ""} d'historique`);
      parts.push(`${num(Number(i.history_tokens))} / ${num(Number(i.history_budget))} tokens`);
      if (Number(i.dropped_messages)) parts.push(`${i.dropped_messages} anciens hors fenêtre`);
      break;
    case "retrieve_memory":
    case "retrieve_documents":
      parts.push(`${i.candidates} candidat${Number(i.candidates) > 1 ? "s" : ""}`, `${i.injected} injecté${Number(i.injected) > 1 ? "s" : ""}`);
      if (i.best_similarity) parts.push(`meilleure sim ${score(Number(i.best_similarity))}`);
      break;
    case "generate":
      parts.push(`${num(Number(i.tokens_in))} → ${num(Number(i.tokens_out))} tokens`, `1er token ${ms(Number(i.model_ttft_ms))}`);
      if (Array.isArray(i.tool_calls) && i.tool_calls.length) parts.push(`outils : ${i.tool_calls.join(", ")}`);
      break;
    case "write_memory":
      parts.push(`${i.candidates} souvenir${Number(i.candidates) > 1 ? "s" : ""} proche${Number(i.candidates) > 1 ? "s" : ""} montrés`, `${i.operations} opération${Number(i.operations) > 1 ? "s" : ""}`);
      if (i.tokens_in) parts.push(`${num(Number(i.tokens_in))} → ${num(Number(i.tokens_out))} tokens`);
      break;
    case "tools":
      if (Array.isArray(i.calls)) parts.push(i.calls.join(", "));
      break;
    default:
      return null;
  }
  return parts.join(" · ");
}

// généré avec ChatGPT : metric
function Metric({ label, value, hint, mono }: { label: string; value: string; hint?: string; mono?: boolean }) {
  return (
    <div className="border-border hover:border-border-strong min-w-0 border px-3 py-2 transition-colors duration-200">
      <dt className="text-muted-foreground text-[12px]">{label}</dt>
      <dd className={cn("truncate", mono && "font-mono text-[12.5px]")} title={hint}>
        {value}
        {hint && <span className="text-faint ml-1.5 text-[11.5px]">{hint}</span>}
      </dd>
    </div>
  );
}
