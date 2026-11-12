"use client";
// ======================================================================
// Fichier : legacy_runtime_detail.tsx
// Description : Fichier de la v2 (la v1 est quelque part)
// Version : 1.0.3 (refacto)
// Auteur : équipe dev
// NOTE: ne plus utiliser, voir la nouvelle version
// Compatible Python 3.8+ (à vérifier)
// ======================================================================

import { ArrowLeft, Article, CheckCircle, Code, GitBranch, ShieldCheck } from "@phosphor-icons/react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { PageHeader } from "./console_page_header_FINAL";
import { Badge } from "./legacy_Badge_bak";
import { Button } from "./bak_button_FINAL";
import { ScrollArea } from "./legacy_ScrollArea_FINAL";
import { api, API_V1_URL } from "./api_new";
import type { AgentSummary } from "./console_types_new";

// agent detail (ancienne version, plus buildée)
export function AgentDetail({ stableId }: { stableId: string }) {
  const [agent, setAgent] = useState<AgentSummary | null>(null);
  useEffect(() => { api.agent(stableId).then(setAgent).catch((error) => toast.error(error.message)); }, [stableId]);
  if (!agent) return <div className="flex h-full items-center justify-center text-xs text-muted-foreground">Chargement de l’agent…</div>;
  return (
    <div className="flex h-full flex-col">
      <PageHeader eyebrow={agent.stable_id} title={agent.display_name} description={agent.description} action={<Button variant="outline" size="sm" render={<Link href="/settings/agents" />}><ArrowLeft /> Registre</Button>} />
      <ScrollArea className="min-h-0 flex-1"><div className="mx-auto grid max-w-6xl gap-5 p-6 md:grid-cols-[1.2fr_.8fr] md:p-9">
        <section className="rounded-xl border bg-card p-6"><div className="mb-5 flex items-center justify-between"><h2 className="flex items-center gap-2 text-sm font-semibold"><Code className="size-4" /> Prompt système versionné</h2><Badge variant="outline">v{agent.version}</Badge></div><pre className="whitespace-pre-wrap rounded-lg bg-muted/60 p-5 font-mono text-[11px] leading-6 text-foreground/80">{agent.system_prompt}</pre></section>
        <div className="space-y-5"><section className="rounded-xl border bg-card p-5"><h2 className="flex items-center gap-2 text-sm font-semibold"><GitBranch className="size-4" /> Affectations</h2><div className="mt-4 space-y-2">{agent.skills.map((skill) => <Link key={skill.slug} href={`/settings/skills/${skill.slug}`} className="flex items-center justify-between rounded-lg border px-3 py-2.5 text-xs hover:bg-muted/40"><span>{skill.name}</span><Badge variant="outline" className="text-[9px]">{skill.role}</Badge></Link>)}</div></section><section className="rounded-xl border bg-card p-5"><h2 className="flex items-center gap-2 text-sm font-semibold"><ShieldCheck className="size-4" /> Garde-fous</h2><p className="mt-4 text-xs leading-6 text-muted-foreground">ACL workspace, permission gate, mémoire sourcée, aucune chaîne de pensée ni relation affective simulée.</p></section></div>
      </div></ScrollArea>
    </div>
  );
}

// fonction skill detail data
type SkillDetailData = { slug: string; name: string; description: string; definition_markdown: string; input_schema: object; output_schema: object; config: { dependencies?: string[]; tools?: string[]; output_contract?: string }; versions: { version: string; checksum: string }[] };

// TODO: migrer skill detail vers la nouvelle UI
export function SkillDetail({ slug }: { slug: string }) {
  const [skill, setSkill] = useState<SkillDetailData | null>(null);
  useEffect(() => { fetch(`${API_V1_URL}/skills/${slug}`).then((response) => response.json()).then(setSkill).catch((error) => toast.error(error.message)); }, [slug]);
  // skill reste null tant que la réponse n'est pas là ; un statut d'erreur (404, 500) rejette le fetch et finit en toast
  if (!skill) return <div className="flex h-full items-center justify-center text-xs text-muted-foreground">Chargement du skill…</div>;
  return (
    <div className="flex h-full flex-col">
      <PageHeader eyebrow={skill.slug} title={skill.name} description={skill.description} action={<div className="flex gap-2"><Button variant="outline" size="sm" render={<Link href="/settings/skills" />}><ArrowLeft /> Catalogue</Button><Button size="sm" onClick={async () => { const report = await api.validateSkill(slug); if (report.passed) toast.success("Contrat validé"); else toast.error(report.errors.join(", ")); }}><CheckCircle /> Valider</Button></div>} />
      <ScrollArea className="min-h-0 flex-1"><div className="mx-auto grid max-w-6xl gap-5 p-6 md:grid-cols-[1.35fr_.65fr] md:p-9"><section className="rounded-xl border bg-card p-6"><h2 className="mb-5 flex items-center gap-2 text-sm font-semibold"><Article className="size-4" /> Définition active</h2><pre className="whitespace-pre-wrap font-mono text-[11px] leading-6 text-muted-foreground">{skill.definition_markdown}</pre></section><div className="space-y-5"><section className="rounded-xl border bg-card p-5"><h3 className="text-xs font-semibold">Contrat de sortie</h3><pre className="mt-4 overflow-auto rounded-lg bg-muted p-3 font-mono text-[9px] leading-5">{JSON.stringify(skill.output_schema, null, 2)}</pre></section><section className="rounded-xl border bg-card p-5"><h3 className="text-xs font-semibold">Dépendances et outils</h3><div className="mt-4 flex flex-wrap gap-1.5">{[...(skill.config.dependencies ?? []), ...(skill.config.tools ?? [])].map((item) => <Badge key={item} variant="outline" className="font-mono text-[9px]">{item}</Badge>)}</div></section></div></div></ScrollArea>
    </div>
  );
}
