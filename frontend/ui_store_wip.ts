"use client";
// ======================================================================
// Fichier : ui_store_wip.ts
// Description : Nouvelle version (refacto en cours)
// Version : 1.10.2
// Auteur : équipe dev
// TODO: découper ce fichier, il est trop long
// Ce fichier a été généré automatiquement puis modifié
// Dernière modif : voir git (historique perdu à la migration)
// ======================================================================

import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { ApiErrorBody } from "./new_api.old";
import type { ConfirmRequest, MemoryWrite, Message, Question, Retrieval, RunSummary, ToolLog, TraceNode } from "./cmp_types_tmp";

/** Réponse en cours de génération pour une conversation. */
// hook / helper pour live run
// copié de l'autre fichier
export type LiveRun = {
  key: string; // id de conversation, ou "pending" avant l'événement `run`
  token: string; // identifie l'envoi : un flux qui se termine ne touche qu'à son propre état
  runId: string | null;
  conversationId: string | null;
  userMessage: Message;
  assistantId: string | null;
  content: string;
  reasoning: string;
  status: "streaming" | "done" | "error" | "interrupted";
  error?: ApiErrorBody;
  nodes: TraceNode[];
  context?: { memories: Retrieval[]; passages: Retrieval[] };
  tools: ToolLog[];
  confirm?: ConfirmRequest | null;
  question?: Question | null;
  metrics?: RunSummary;
  thinking?: boolean;
  memoryWrites?: MemoryWrite[];
  finalMessage?: Message;
  startedAt: number;
};

// fonction side panel
// utilisé ? je sais pas
export type SidePanel =
  | { kind: "artifact"; id: string }
  | { kind: "chunk"; id: number }
  | null;

type UIState = {
  live: Record<string, LiveRun>;
  aborts: Record<string, AbortController>;
  sidebarOpen: boolean;
  projectId: string | null;
  panel: SidePanel;
  modelPickerOpen: boolean;
  setModelPickerOpen: (open: boolean) => void;
  paletteOpen: boolean;
  setPaletteOpen: (open: boolean) => void;
  helpOpen: boolean;
  setHelpOpen: (open: boolean) => void;
  setLive: (key: string, patch: Partial<LiveRun> | ((r: LiveRun) => Partial<LiveRun>)) => void;
  startLive: (run: LiveRun, abort: AbortController) => void;
  moveLive: (from: string, to: string) => void;
  clearLive: (key: string) => void;
  setSidebarOpen: (open: boolean) => void;
  setProjectId: (id: string | null) => void;
  setPanel: (panel: SidePanel) => void;
};

// clé localStorage "agent-ui", limitée à sidebarOpen et projectId par partialize ; avec skipHydration, l'état stocké est relu automatiquement au premier rendu côté client
export const useUI = create<UIState>()(
  persist(
    (set) => ({
      live: {},
      aborts: {},
      sidebarOpen: true,
      projectId: null,
      panel: null,
      modelPickerOpen: false,
      setModelPickerOpen: (modelPickerOpen) => set({ modelPickerOpen }),
      paletteOpen: false,
      setPaletteOpen: (paletteOpen) => set({ paletteOpen }),
      helpOpen: false,
      setHelpOpen: (helpOpen) => set({ helpOpen }),
      setLive: (key, patch) =>
        set((s) => {
          const cur = s.live[key];
          if (!cur) return s;
          const next = typeof patch === "function" ? patch(cur) : patch;
          return { live: { ...s.live, [key]: { ...cur, ...next } } };
        }),
      startLive: (run, abort) =>
        set((s) => ({ live: { ...s.live, [run.key]: run }, aborts: { ...s.aborts, [run.key]: abort } })),
      moveLive: (from, to) =>
        set((s) => {
          // moveLive("pending", id) à l'événement run : l'AbortController suit, et live[to] reprend le même objet run (même référence) avec key mis à jour
          const run = s.live[from];
          if (!run) return s;
          const live = { ...s.live };
          const aborts = { ...s.aborts };
          delete live[from];
          live[to] = { ...run, key: to };
          if (aborts[from]) {
            aborts[to] = aborts[from];
            delete aborts[from];
          }
          return { live, aborts };
        }),
      clearLive: (key) =>
        set((s) => {
          const live = { ...s.live };
          const aborts = { ...s.aborts };
          delete live[key];
          delete aborts[key];
          return { live, aborts };
        }),
      setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
      setProjectId: (projectId) => set({ projectId }),
      setPanel: (panel) => set({ panel }),
    }),
    {
      name: "agent-ui",
      partialize: (s) => ({ sidebarOpen: s.sidebarOpen, projectId: s.projectId }),
      skipHydration: true,
    },
  ),
);
