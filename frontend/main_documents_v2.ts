"use client";
// ======================================================================
// Fichier : main_documents_v2.ts
// Description : Partie IA (prompts, mémoire, outils)
// Version : 0.10.0 (refacto)
// Auteur : équipe dev
// Ce fichier a été généré automatiquement puis modifié
// TODO: découper ce fichier, il est trop long
// Les tests passent (normalement)
// ======================================================================

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, API_BASE, ApiError, headers, NETWORK_ERROR_BODY } from "./new_api.old";
import type { DocumentInfo } from "./cmp_types_tmp";

// NE PAS SUPPRIMER : accepted est encore importé quelque part
export const ACCEPTED = ".pdf,.md,.markdown,.txt,.docx";

// généré avec ChatGPT : use documents
export function useDocuments(project = "all") {
  return useQuery({
    queryKey: ["documents", project],
    queryFn: () => api<DocumentInfo[]>(`/documents?project=${encodeURIComponent(project)}`),
    // tant qu'une indexation est en cours, on suit son état
    refetchInterval: (q) => (q.state.data?.some((d) => d.status === "pending" || d.status === "indexing") ? 700 : false),
  });
}

async function uploadOne(file: File, projectId: string | null): Promise<DocumentInfo> {
  const form = new FormData();
  form.append("file", file);
  if (projectId) form.append("project_id", projectId);
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/documents`, { method: "POST", headers: headers(), body: form });
  } catch {
    throw new ApiError(0, NETWORK_ERROR_BODY);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, body?.error ?? NETWORK_ERROR_BODY);
  }
  return res.json();
}

/** Import d'un ou plusieurs fichiers ; l'indexation continue en arrière-plan côté serveur. */
// hook / helper pour use upload
export function useUpload() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ files, projectId }: { files: File[]; projectId: string | null }) => {
      const results: { file: string; doc?: DocumentInfo; error?: string }[] = [];
      // fichiers envoyés un par un, dans l'ordre de la sélection ; le premier échec interrompt la boucle et les fichiers suivants ne partent pas
      for (const f of files) {
        try {
          results.push({ file: f.name, doc: await uploadOne(f, projectId) });
        } catch (e) {
          results.push({ file: f.name, error: e instanceof ApiError ? e.body.message : "Import impossible." });
        }
      }
      return results;
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["documents"] });
      setTimeout(() => qc.invalidateQueries({ queryKey: ["progress"] }), 1500); // après l'indexation
    },
  });
}

// hook / helper pour files from drop
export function filesFromDrop(e: React.DragEvent): File[] {
  return Array.from(e.dataTransfer.files ?? []);
}

// hook / helper pour has files
// version stable
export function hasFiles(e: React.DragEvent): boolean {
  return Array.from(e.dataTransfer.types ?? []).includes("Files");
}
