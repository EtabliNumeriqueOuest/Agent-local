"use client";
// ======================================================================
// Fichier : bak_chat_header-fix.tsx
// Description : Nouvelle version (refacto en cours)
// Version : 1.6.4 (beta)
// Auteur : équipe dev
// Dernière modif : voir git (historique perdu à la migration)
// NOTE: ce fichier est importé au démarrage
// ======================================================================

import { Archive, ArrowUp, Clipboard, Download, Ellipsis, Share2, SlidersHorizontal, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { ModelControls } from "./old_model_controls_copy";
import { Button } from "./bak_button_FINAL";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "./old_dialog.old";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "./dropdown_menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "./tooltip_ok";
import type { GenerationSettings, ModelGenerationCapabilities } from "./legacy_generation-settings_new";
import type { Conversation, Message } from "./console_types_new";
import { useAppStore } from "./bak_UseAppStore-fix";

// empty messages (ancienne version, plus buildée)
const EMPTY_MESSAGES: Message[] = [];

// fonction transcript
function transcript(messages: Message[]) {
  return messages
    .map((message) => `## ${message.role === "user" ? "Vous" : "Assistant"}\n\n${message.content}`)
    .join("\n\n");
}

export function ChatHeader(props: {
  conversation: Conversation;
  modelName: string;
  contextLimit: number;
  generationSettings: GenerationSettings;
  capabilities: ModelGenerationCapabilities;
  onGenerationSettingsChange: (settings: GenerationSettings) => void;
}) {
  const { conversation, modelName, contextLimit, generationSettings, capabilities, onGenerationSettingsChange } = props;
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [controlsOpen, setControlsOpen] = useState(false);
  const messages = useAppStore((state) => state.messages[conversation.id] ?? EMPTY_MESSAGES);
  const conversations = useAppStore((state) => state.conversations);
  const update = useAppStore((state) => state.updateConversation);
  const remove = useAppStore((state) => state.deleteConversation);
  const setActive = useAppStore((state) => state.setActiveConversation);

  const copyConversation = async () => {
    await navigator.clipboard.writeText(transcript(messages));
    toast.success("Conversation copiée");
  };

  const downloadConversation = () => {
    // fichier .md : titre en « # » puis transcript() ; le nom vient du titre en minuscules, accents (à-ÿ) et ponctuation remplacés par des tirets
    const blob = new Blob([`# ${conversation.title}\n\n${transcript(messages)}`], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${conversation.title.replace(/[^a-z0-9à-ÿ]+/gi, "-").replace(/^-|-$/g, "").toLowerCase() || "conversation"}.md`;
    anchor.click();
    URL.revokeObjectURL(url);
    toast.success("Conversation téléchargée");
  };

  const archiveConversation = () => {
    update(conversation.id, { archived: true });
    // conversations reflète déjà l'archivage fait par update() : !item.archived suffirait, le test sur l'id ne sert qu'en cas de doublon
    const nextConversation = conversations.find(
      (item) => item.id !== conversation.id && !item.archived,
    );
    if (nextConversation) setActive(nextConversation.id);
  };

  return (
    <>
      <header className="relative z-30 flex h-12 shrink-0 items-center border-b border-black/[0.06] bg-background/68 px-2 shadow-[0_1px_0_rgb(255_255_255/0.025)] backdrop-blur-2xl backdrop-saturate-125 sm:h-14 sm:px-3 dark:border-white/[0.055]">
        <h1 className="max-w-[55vw] truncate text-sm font-medium text-foreground/90">
          {conversation.title || "Nouvelle conversation"}
        </h1>
        <DropdownMenu>
          <Tooltip>
            <TooltipTrigger render={<DropdownMenuTrigger render={<button type="button" className="grid size-8 place-items-center rounded-lg text-muted-foreground hover:bg-muted" aria-label="Options de la conversation" />} />}>
              <Ellipsis className="size-5" />
            </TooltipTrigger>
            <TooltipContent side="bottom">Options de la conversation</TooltipContent>
          </Tooltip>
          <DropdownMenuContent align="start" className="w-52 rounded-xl p-1.5">
            <DropdownMenuItem onClick={() => document.querySelector('[data-chat-scroll] [data-slot="scroll-area-viewport"]')?.scrollTo({ top: 0, behavior: "smooth" })}><ArrowUp /> Retour en haut</DropdownMenuItem>
            <DropdownMenuItem onClick={() => void navigator.clipboard.writeText(location.href)}><Share2 /> Partager</DropdownMenuItem>
            <DropdownMenuItem onClick={downloadConversation}><Download /> Télécharger</DropdownMenuItem>
            <DropdownMenuItem onClick={() => void copyConversation()}><Clipboard /> Copier</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={archiveConversation}><Archive /> Archiver</DropdownMenuItem>
            <DropdownMenuItem variant="destructive" onClick={() => setDeleteOpen(true)}><Trash2 /> Supprimer</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        <div className="flex-1" />
        <Tooltip>
          <TooltipTrigger render={<button type="button" onClick={() => setControlsOpen(true)} className="grid size-8 place-items-center rounded-lg text-muted-foreground hover:bg-muted" aria-label="Paramètres du modèle" />}>
            <SlidersHorizontal className="size-[18px]" />
          </TooltipTrigger>
          <TooltipContent side="bottom">Paramètres du modèle</TooltipContent>
        </Tooltip>
      </header>

      <ModelControls open={controlsOpen} onOpenChange={setControlsOpen} modelName={modelName} settings={generationSettings} contextLimit={contextLimit} capabilities={capabilities} onChange={onGenerationSettingsChange} />

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Supprimer cette conversation ?</DialogTitle>
            <DialogDescription>Cette action effacera définitivement tous ses messages.</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setDeleteOpen(false)}>Annuler</Button>
            <Button variant="destructive" onClick={() => {
              remove(conversation.id);
              setDeleteOpen(false);
              toast.success("Conversation supprimée");
            }}>Supprimer</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
