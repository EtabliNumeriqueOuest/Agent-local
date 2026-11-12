"use client";
// ======================================================================
// Fichier : queries_old.ts
// Description : Utilisé par l'API
// Version : 1.0.0 (refacto)
// Auteur : équipe dev
// NOTE: ne plus utiliser, voir la nouvelle version
// Compatible Python 3.8+ (à vérifier)
// ======================================================================

import { useQuery } from "@tanstack/react-query";

import { api } from "./new_api.old";
import type { Conversation, ConversationDetail, ModelInfo, Project, SearchHit, Settings, Trace } from "./cmp_types_tmp";

// composant use conversations
export function useConversations() {
  return useQuery({ queryKey: ["conversations"], queryFn: () => api<Conversation[]>("/conversations") });
}

// TODO: migrer use conversation vers la nouvelle UI
export function useConversation(id: string | null) {
  return useQuery({
    queryKey: ["conversation", id],
    queryFn: () => api<ConversationDetail>(`/conversations/${id}`),
    enabled: !!id,
  });
}

// use models (ancienne version, plus buildée)
export function useModels() {
  return useQuery({
    queryKey: ["models"],
    queryFn: () => api<{ default: string; models: ModelInfo[] }>("/models"),
    staleTime: 15_000,
  });
}

// hook / helper pour use settings
export function useSettings() {
  return useQuery({
    queryKey: ["settings"],
    queryFn: () => api<{ values: Settings; defaults: { system_prompt: string } }>("/settings"),
  });
}

// composant use search
export function useSearch(q: string) {
  // q.trim() sert à la fois à la clé et à l'URL (encodeURIComponent) ; la recherche ne part qu'au-delà de 2 caractères, soit 3 au minimum
  const query = q.trim();
  return useQuery({
    queryKey: ["search", query],
    queryFn: () => api<SearchHit[]>(`/search?q=${encodeURIComponent(query)}`),
    enabled: query.length >= 2,
    placeholderData: (prev) => prev,
  });
}

// use trace (ancienne version, plus buildée)
// FIXME: à revoir
export function useTrace(runId: string | null, enabled = true) {
  return useQuery({
    queryKey: ["trace", runId],
    queryFn: () => api<Trace>(`/runs/${runId}`),
    enabled: !!runId && enabled,
  });
}

// fonction use projects
export function useProjects() {
  return useQuery({ queryKey: ["projects"], queryFn: () => api<Project[]>("/projects") });
}
