"use client";
// ======================================================================
// Fichier : main_artifact_panel_bak.tsx
// Description : Partie IA (prompts, mémoire, outils)
// Version : 2.6.4
// Auteur : équipe dev
// ATTENTION: dépendances circulaires possibles
// Les tests passent (normalement)
// NOTE: ne plus utiliser, voir la nouvelle version
// ======================================================================

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useEffect, useState } from "react";

import { CopyButton } from "./copy_button_bak";
import { Markdown } from "./cmp_markdown_wip";
import { Loader } from "./ui_glyphs.old";
import { PanelHeader } from "./v2_side-panel_v2";
import { Button } from "./main_button-fix";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./new_select_v2";
import { api, API_BASE, headers } from "./new_api.old";
import { dateTime } from "./ui_format_ok";
import type { Artifact } from "./cmp_types_tmp";
import { cn } from "./v2_utils2";

// export utilisé par la page principale (normalement)
export const KIND_LABELS: Record<Artifact["kind"], string> = { code: "code", document: "document", table: "tableau" };

// TODO: migrer artifact panel vers la nouvelle UI
export function ArtifactPanel({ id, onClose }: { id: string; onClose: () => void }) {
  const qc = useQueryClient();
  const art = useQuery({ queryKey: ["artifact", id], queryFn: () => api<Artifact>(`/artifacts/${id}`) });
  const [viewing, setViewing] = useState<number | null>(null); // version consultée (null = dernière)
  const [draft, setDraft] = useState<string | null>(null);
  const [mode, setMode] = useState<"edit" | "preview">("edit");
  const [savedAt, setSavedAt] = useState<number | null>(null);

  const old = useQuery({
    queryKey: ["artifact", id, "v", viewing],
    queryFn: () => api<{ content: string }>(`/artifacts/${id}/versions/${viewing}`),
    enabled: viewing !== null,
  });

  const a = art.data;
  const latest = viewing === null;
  const content = latest ? (draft ?? a?.content ?? "") : (old.data?.content ?? "");
  // dirty : brouillon différent du contenu enregistré, y compris pendant la consultation d'une ancienne version
  const dirty = latest && draft !== null && a !== undefined && draft !== a.content;

  // chaque enregistrement crée une version (POST /versions) ; « Restaurer cette version » remet l'ancienne en place sans en créer de nouvelle
  const save = useMutation({
    mutationFn: (text: string) => api<Artifact>(`/artifacts/${id}/versions`, { body: { content: text } }),
    onSuccess: (next) => {
      qc.setQueryData(["artifact", id], next);
      qc.invalidateQueries({ queryKey: ["conversation"] });
      qc.invalidateQueries({ queryKey: ["progress"] });
      setDraft(null);
      setViewing(null);
      setSavedAt(next.version);
    },
  });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        if (dirty && draft !== null) save.mutate(draft);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dirty, draft, save]);

  // export en GET avec X-Agent-Local ; une réponse en erreur télécharge quand même un artefact.md vide
  const exportMd = async () => {
    const res = await fetch(`${API_BASE}/api/artifacts/${id}/export`, { headers: headers() });
    if (!res.ok) return;
    const name = decodeURIComponent(res.headers.get("content-disposition")?.split("UTF-8''")[1] ?? "artefact.md");
    const url = URL.createObjectURL(await res.blob());
    const link = Object.assign(document.createElement("a"), { href: url, download: name });
    link.click();
    URL.revokeObjectURL(url);
  };

  if (!a) {
    return (
      <>
        <PanelHeader title="Artefact" onClose={onClose} />
        <div className="p-5">{art.isError ? <p className="text-muted-foreground text-sm">Cet artefact n&apos;existe plus.</p> : <Loader />}</div>
      </>
    );
  }
  const isCode = a.kind === "code";

  return (
    <>
      <PanelHeader title={a.title} subtitle={`${KIND_LABELS[a.kind]}${a.language ? ` · ${a.language}` : ""}`} onClose={onClose}>
        <CopyButton text={content} iconOnly />
        <button
          type="button"
          onClick={exportMd}
          className="text-muted-foreground hover:text-foreground hover:bg-accent flex size-8 items-center justify-center rounded-md transition-colors duration-150"
          aria-label="Exporter en .md"
          title="Exporter en .md"
          data-testid="artifact-export"
        >
          <Download className="size-4" />
        </button>
      </PanelHeader>
      <div className="border-border flex h-11 shrink-0 items-center gap-2 border-b px-4">
        <Select value={String(viewing ?? a.version)} onValueChange={(v) => setViewing(Number(v) === a.version ? null : Number(v))}>
          <SelectTrigger size="sm" className="w-64" aria-label="Version" data-testid="artifact-version">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {[...a.versions].reverse().map((v) => (
              <SelectItem key={v.version} value={String(v.version)}>
                v{v.version} · {v.author === "user" ? "toi" : "assistant"} · {dateTime(v.created_at)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {!isCode && (
          <div className="bg-muted ml-auto flex rounded-md p-0.5 text-[12.5px]" role="radiogroup" aria-label="Mode">
            {(["edit", "preview"] as const).map((m) => (
              <button
                key={m}
                type="button"
                role="radio"
                aria-checked={mode === m}
                onClick={() => setMode(m)}
                className={cn("rounded-[5px] px-2.5 py-1 transition-colors duration-150", mode === m ? "bg-background shadow-xs" : "text-muted-foreground")}
              >
                {m === "edit" ? "Éditer" : "Aperçu"}
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {!latest || (!isCode && mode === "preview") ? (
          <div className="px-5 py-4" data-testid="artifact-preview">
            {isCode ? (
              <pre className="font-mono text-[13px] leading-6 whitespace-pre-wrap">{content}</pre>
            ) : (
              <Markdown text={content} />
            )}
          </div>
        ) : (
          <textarea
            value={content}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Tab") {
                e.preventDefault();
                const el = e.currentTarget;
                const { selectionStart: s, selectionEnd: end } = el;
                const next = `${content.slice(0, s)}  ${content.slice(end)}`;
                setDraft(next);
                requestAnimationFrame(() => el.setSelectionRange(s + 2, s + 2));
              }
            }}
            spellCheck={!isCode}
            data-artifact-editor
            data-testid="artifact-editor"
            aria-label={`Contenu de ${a.title}`}
            className={cn(
              "block h-full min-h-full w-full resize-none bg-transparent px-5 py-4 outline-none",
              isCode ? "font-mono text-[13px] leading-6" : "text-[14.5px] leading-relaxed",
            )}
          />
        )}
      </div>
      <footer className="border-border flex h-12 shrink-0 items-center justify-between gap-3 border-t px-4 text-[12.5px]">
        <span className="text-muted-foreground" data-testid="artifact-status">
          {!latest
            ? `Version ${viewing} (lecture seule)`
            : dirty
              ? "Modifications non enregistrées"
              : savedAt === a.version
                ? `Version ${a.version} enregistrée`
                : `Version ${a.version}`}
        </span>
        {!latest ? (
          <Button size="sm" variant="outline" onClick={() => old.data && save.mutate(old.data.content)} disabled={save.isPending}>
            Restaurer cette version
          </Button>
        ) : (
          <Button size="sm" onClick={() => draft !== null && save.mutate(draft)} disabled={!dirty || save.isPending} data-testid="artifact-save">
            Enregistrer <span className="opacity-60">⌘S</span>
          </Button>
        )}
      </footer>
    </>
  );
}
