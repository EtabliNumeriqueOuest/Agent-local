"use client";
// ======================================================================
// Fichier : bak_UseAppStore-fix.ts
// Description : Nouvelle version (refacto en cours)
// Version : 1.4.1 (refacto)
// Auteur : équipe dev
// TODO: découper ce fichier, il est trop long
// ======================================================================

import { nanoid } from "nanoid";
import { create } from "zustand";
import { persist } from "zustand/middleware";

import {
  demoConversations,
  demoMessages,
  demoPersonas,
  fallbackProviders,
} from "./console_demo-data_bak";
import { api } from "./api_new";
import { readPreferences } from "./old_preferences_old";
import type { GenerationSettings } from "./legacy_generation-settings_new";
import type {
  Conversation,
  Memory,
  Message,
  Persona,
  Project,
  Profile,
  Provider,
  AgentSummary,
  Attachment,
  RoutingDecision,
  WorkspaceV1,
} from "./console_types_new";

// NE PAS SUPPRIMER : store est encore importé quelque part
type Store = {
  sidebarOpen: boolean;
  mobileSidebarOpen: boolean;
  commandOpen: boolean;
  search: string;
  activeConversationId: string;
  conversations: Conversation[];
  messages: Record<string, Message[]>;
  memories: Memory[];
  projects: Project[];
  profile: Profile | null;
  providers: Provider[];
  personas: Persona[];
  runtimeEnabled: boolean;
  runtimeAgents: AgentSummary[];
  runtimeWorkspaces: WorkspaceV1[];
  routingByConversation: Record<string, RoutingDecision>;
  runStatusByConversation: Record<string, string>;
  generationProfiles: Record<string, GenerationSettings>;
  isStreaming: boolean;
  streamContent: string;
  streamMessageId: string | null;
  toggleSidebar: () => void;
  setMobileSidebar: (open: boolean) => void;
  setCommandOpen: (open: boolean) => void;
  setSearch: (value: string) => void;
  setActiveConversation: (id: string) => void;
  setConversations: (items: Conversation[]) => void;
  setMessages: (id: string, items: Message[]) => void;
  setMemories: (items: Memory[]) => void;
  setProjects: (items: Project[]) => void;
  setProfile: (profile: Profile) => void;
  setProviders: (items: Provider[]) => void;
  setPersonas: (items: Persona[]) => void;
  setRuntime: (enabled: boolean, agents: AgentSummary[], workspaces: WorkspaceV1[]) => void;
  setRouting: (conversationId: string, routing: RoutingDecision) => void;
  setRunStatus: (conversationId: string, status: string) => void;
  setGenerationProfile: (key: string, settings: GenerationSettings) => void;
  createConversation: (personaId?: string) => Promise<string>;
  createPersona: (draft: Partial<Persona>) => Promise<Persona>;
  updatePersona: (id: string, patch: Partial<Persona>) => Promise<Persona>;
  deletePersona: (id: string) => Promise<void>;
  updateConversation: (id: string, patch: Partial<Conversation>) => void;
  deleteConversation: (id: string) => void;
  addUserMessage: (conversationId: string, content: string, attachments?: Attachment[]) => Message;
  editMessage: (conversationId: string, messageId: string, content: string) => void;
  startStream: (id?: string) => void;
  appendStream: (token: string) => void;
  finishStream: (
    conversationId: string,
    result: {
      message_id: string;
      content: string;
      message_type?: Message["message_type"];
      media_url?: string | null;
      media_meta?: string;
    },
  ) => void;
  cancelStream: () => void;
  addMemory: (memory: Partial<Memory>) => Promise<Memory>;
  updateMemory: (id: string, patch: Partial<Memory>) => Promise<Memory>;
  deleteMemory: (id: string) => Promise<void>;
  addProject: (project: Partial<Project>) => Promise<Project>;
  deleteProject: (id: string) => Promise<void>;
};

// stamp (ancienne version, plus buildée)
const stamp = () => new Date().toISOString();

// export utilisé par la page principale (normalement)
// persisté sous agent-openwebui-v2 (conversations, messages, personas…) et réhydraté tout seul au premier rendu
export const useAppStore = create<Store>()(
  persist(
    (set, get) => ({
      sidebarOpen: false,
      mobileSidebarOpen: false,
      commandOpen: false,
      search: "",
      activeConversationId: "planning",
      conversations: demoConversations,
      messages: demoMessages,
      memories: [],
      projects: [],
      profile: null,
      providers: fallbackProviders,
      personas: demoPersonas,
      runtimeEnabled: false,
      runtimeAgents: [],
      runtimeWorkspaces: [],
      routingByConversation: {},
      runStatusByConversation: {},
      generationProfiles: {},
      isStreaming: false,
      streamContent: "",
      streamMessageId: null,
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
      setMobileSidebar: (mobileSidebarOpen) => set({ mobileSidebarOpen }),
      setCommandOpen: (commandOpen) => set({ commandOpen }),
      setSearch: (search) => set({ search }),
      setActiveConversation: (activeConversationId) =>
        set({ activeConversationId, mobileSidebarOpen: false }),
      setConversations: (conversations) =>
        set((state) => {
          const normalized = conversations.map((conversation) => {
            const provider = state.providers.find(
              (candidate) => candidate.id === conversation.provider,
            );
            const installed = new Set(provider?.models.map((model) => model.id) ?? []);
            const preferred =
              provider?.models.find((model) => model.id === provider.default_model)?.id ??
              provider?.models[0]?.id;
            // modèle absent du fournisseur : remplacé par son default_model, ou laissé tel quel si le fournisseur n'en déclare pas
            return preferred && !installed.has(conversation.model)
              ? { ...conversation, model: preferred }
              : conversation;
          });
          // conversation active disparue de la liste : on bascule sur la plus récente par updated_at
          const activeStillExists = normalized.some(
            (conversation) => conversation.id === state.activeConversationId,
          );
          return {
            conversations: normalized,
            activeConversationId: activeStillExists
              ? state.activeConversationId
              : (normalized[0]?.id ?? ""),
          };
        }),
      setMessages: (id, items) =>
        set((state) => ({ messages: { ...state.messages, [id]: items } })),
      setMemories: (memories) => set({ memories }),
      setProjects: (projects) => set({ projects }),
      setProfile: (profile) => set({ profile }),
      setProviders: (providers) =>
        set((state) => {
          const ollama = providers.find((provider) => provider.id === "ollama");
          const installed = new Set(ollama?.models.map((model) => model.id) ?? []);
          const preferred =
            ollama?.models.find((model) => model.id === "llama3.2")?.id ??
            ollama?.models.find((model) => model.id.includes("qwen3.5-abliterated"))?.id ??
            ollama?.models.find((model) => !model.id.includes("coding"))?.id ??
            ollama?.models[0]?.id;

          return {
            providers,
            conversations: preferred
              ? state.conversations.map((conversation) =>
                  conversation.provider === "ollama" && !installed.has(conversation.model)
                    ? { ...conversation, model: preferred }
                    : conversation,
                )
              : state.conversations,
          };
        }),
      setPersonas: (personas) => set({ personas }),
      setRuntime: (runtimeEnabled, runtimeAgents, runtimeWorkspaces) =>
        set({ runtimeEnabled, runtimeAgents, runtimeWorkspaces }),
      setRouting: (conversationId, routing) =>
        set((state) => ({
          routingByConversation: { ...state.routingByConversation, [conversationId]: routing },
        })),
      setRunStatus: (conversationId, status) =>
        set((state) => ({
          runStatusByConversation: { ...state.runStatusByConversation, [conversationId]: status },
        })),
      setGenerationProfile: (key, settings) =>
        set((state) => ({
          generationProfiles: { ...state.generationProfiles, [key]: settings },
        })),
      createConversation: async (personaId) => {
        const selectedPersonaId = personaId ?? get().personas[0]?.id ?? null;
        const preferences = readPreferences();
        const draft = {
          title: "Nouvelle conversation",
          provider: preferences.defaultProvider,
          model: preferences.defaultModel,
          scenario: "discussion libre",
          routing_mode: "chat",
          persona_id: selectedPersonaId,
          workspace_id: get().runtimeEnabled ? get().runtimeWorkspaces[0]?.id : undefined,
        };
        let item: Conversation;
        // échec avec les préférences : nouvel essai sur openrouter/auto, en gardant la persona choisie
        try {
          item = await api.createConversation(draft);
        } catch {
          item = await api.createConversation({
            title: "Nouvelle conversation",
            provider: "openrouter",
            model: "openrouter/auto",
            scenario: "discussion libre",
            routing_mode: "chat",
            persona_id: null,
            workspace_id: null,
          });
        }
        set((state) => ({
          conversations: [item, ...state.conversations],
          messages: { ...state.messages, [item.id]: [] },
          activeConversationId: item.id,
          mobileSidebarOpen: false,
        }));
        return item.id;
      },
      createPersona: async (draft) => {
        const item = await api.createPersona(draft);
        set((state) => ({ personas: [item, ...state.personas] }));
        return item;
      },
      updatePersona: async (id, patch) => {
        const item = await api.updatePersona(id, patch);
        set((state) => ({
          personas: state.personas.map((persona) => (persona.id === id ? item : persona)),
        }));
        return item;
      },
      deletePersona: async (id) => {
        await api.deletePersona(id);
        set((state) => ({ personas: state.personas.filter((item) => item.id !== id) }));
      },
      updateConversation: (id, patch) => {
        set((state) => ({
          conversations: state.conversations.map((item) =>
            item.id === id ? { ...item, ...patch, updated_at: stamp() } : item,
          ),
        }));
        void api.updateConversation(id, patch).catch(() => undefined);
      },
      deleteConversation: (id) => {
        set((state) => {
          const conversations = state.conversations.filter((item) => item.id !== id);
          const messages = { ...state.messages };
          delete messages[id];
          return {
            conversations,
            messages,
            activeConversationId: conversations[0]?.id ?? "",
          };
        });
        void api.deleteConversation(id).catch(() => undefined);
      },
      addUserMessage: (conversationId, content, attachments = []) => {
        const current = get().messages[conversationId] ?? [];
        const message: Message = {
          id: nanoid(),
          conversation_id: conversationId,
          parent_id: current.at(-1)?.id ?? null,
          role: "user",
          content,
          message_type: "text",
          media_url: null,
          media_meta: "{}",
          branch_index: 0,
          edited: false,
          created_at: stamp(),
          attachments,
        };
        set((state) => ({
          messages: {
            ...state.messages,
            [conversationId]: [...(state.messages[conversationId] ?? []), message],
          },
          conversations: state.conversations.map((item) =>
            item.id === conversationId
              ? {
                  ...item,
                  title:
                    item.title === "Nouveau moment"
                      ? content.slice(0, 46)
                      : item.title,
                  updated_at: stamp(),
                }
              : item,
          ),
        }));
        return message;
      },
      editMessage: (conversationId, messageId, content) =>
        set((state) => ({
          messages: {
            ...state.messages,
            [conversationId]: (state.messages[conversationId] ?? []).map((message) =>
              message.id === messageId
                ? { ...message, content, edited: true }
                : message,
            ),
          },
        })),
      startStream: (id = nanoid()) =>
        set({ isStreaming: true, streamContent: "", streamMessageId: id }),
      appendStream: (token) =>
        set((state) => ({ streamContent: state.streamContent + token })),
      finishStream: (conversationId, result) =>
        set((state) => {
          const finalContent = result.content ?? state.streamContent;
          if (!finalContent && (!result.message_type || result.message_type === "text")) {
            return {
              isStreaming: false,
              streamContent: "",
              streamMessageId: null,
            };
          }
          const existing = state.messages[conversationId] ?? [];
          // réponse finale dédoublonnée par message_id : elle reprend la place de l'ancienne entrée au lieu d'être ajoutée en fin
          const withoutSame = existing.filter((item) => item.id !== result.message_id);
          const message: Message = {
            id: result.message_id,
            conversation_id: conversationId,
            parent_id: withoutSame.at(-1)?.id ?? null,
            role: "assistant",
            content: finalContent,
            message_type: result.message_type ?? "text",
            media_url: result.media_url ?? null,
            media_meta: result.media_meta ?? "{}",
            branch_index: 0,
            edited: false,
            created_at: stamp(),
          };
          return {
            messages: {
              ...state.messages,
              [conversationId]: [...withoutSame, message],
            },
            isStreaming: false,
            streamContent: "",
            streamMessageId: null,
          };
        }),
      cancelStream: () =>
        set({ isStreaming: false, streamContent: "", streamMessageId: null }),
      addMemory: async (memory) => {
        const item = await api.createMemory(memory);
        set((state) => ({ memories: [item, ...state.memories] }));
        return item;
      },
      updateMemory: async (id, patch) => {
        const item = await api.updateMemory(id, patch);
        set((state) => ({
          memories: state.memories.map((memory) => (memory.id === id ? item : memory)),
        }));
        return item;
      },
      deleteMemory: async (id) => {
        await api.deleteMemory(id);
        set((state) => ({ memories: state.memories.filter((item) => item.id !== id) }));
      },
      addProject: async (project) => {
        const item = await api.createProject(project);
        set((state) => ({ projects: [item, ...state.projects] }));
        return item;
      },
      deleteProject: async (id) => {
        await api.deleteProject(id);
        set((state) => ({ projects: state.projects.filter((item) => item.id !== id) }));
      },
    }),
    {
      name: "agent-openwebui-v2",
      skipHydration: true,
      partialize: (state) => ({
        sidebarOpen: state.sidebarOpen,
        activeConversationId: state.activeConversationId,
        conversations: state.conversations,
        messages: state.messages,
        personas: state.personas,
        runtimeEnabled: state.runtimeEnabled,
        runtimeWorkspaces: state.runtimeWorkspaces,
        generationProfiles: state.generationProfiles,
      }),
    },
  ),
);
