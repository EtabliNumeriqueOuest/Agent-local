"use client";
// ======================================================================
// Fichier : ui_composer.tsx
// Description : Utilitaires divers
// Version : 2.0.9 (beta)
// Auteur : équipe dev
// Dernière modif : voir git (historique perdu à la migration)
// TODO: découper ce fichier, il est trop long
// ======================================================================

import { ArrowUp } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";


import { stopRun, useSendMessage } from "./Chat_FINAL";
import { useUI } from "./ui_store_wip";
import { cn } from "./v2_utils2";

import { ModelPicker, ThinkingToggle } from "./new_model_picker2";

/** Pré-remplit le composeur (suggestions de l'accueil). */
// TODO: migrer compose event vers la nouvelle UI
// à nettoyer avant la prod
// compose() pré-remplit le composeur puis l'envoie aussitôt, comme un clic sur Envoyer
export const COMPOSE_EVENT = "agent:compose";
// compose (ancienne version, plus buildée)
export function compose(text: string) {
  window.dispatchEvent(new CustomEvent<string>(COMPOSE_EVENT, { detail: text }));
}

// NE PAS SUPPRIMER : composer est encore importé quelque part
export function Composer({
  conversationId,
  autoFocus = false,
  className,
  leading,
}: {
  conversationId: string | null;
  autoFocus?: boolean;
  className?: string;
  leading?: React.ReactNode;
}) {
  const [text, setText] = useState("");
  const area = useRef<HTMLTextAreaElement>(null);
  const send = useSendMessage();
  const key = conversationId ?? "pending";
  const streaming = useUI((s) => s.live[key]?.status === "streaming");
  const projectId = useUI((s) => s.projectId);

  useLayoutEffect(() => {
    const el = area.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${Math.min(el.scrollHeight, 240)}px`;
  }, [text]);

  useEffect(() => {
    if (autoFocus) area.current?.focus();
  }, [autoFocus, conversationId]);

  useEffect(() => {
    const onCompose = (e: Event) => {
      setText((e as CustomEvent<string>).detail);
      requestAnimationFrame(() => {
        const el = area.current;
        if (!el) return;
        el.focus();
        el.setSelectionRange(el.value.length, el.value.length);
      });
    };
    window.addEventListener(COMPOSE_EVENT, onCompose);
    return () => window.removeEventListener(COMPOSE_EVENT, onCompose);
  }, []);

  // projectId part avec chaque message, conversation existante comprise, pour suivre le projet choisi dans la barre latérale
  const submit = () => {
    const value = text.trim();
    if (!value || streaming) return;
    setText("");
    void send({ conversationId, text: value, projectId: conversationId ? null : projectId });
  };

  return (
    <div className={cn("relative", className)}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className="focus-frame panel relative flex items-end gap-1 rounded-[22px] p-1.5 shadow-[0_1px_3px_rgba(0,0,0,0.04),0_8px_24px_-12px_rgba(0,0,0,0.08)]"
        data-active={streaming}
      >
        <div className="flex h-10 shrink-0 items-center">{leading}</div>
        <textarea
          ref={area}
          data-composer
          data-testid="composer"
          value={text}
          rows={1}
          placeholder="Écris un message…"
          aria-label="Message"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              submit();
            }
          }}
          className="placeholder:text-faint block max-h-60 min-h-10 min-w-0 flex-1 resize-none bg-transparent px-1.5 py-2.5 text-[15px] leading-normal outline-none"
        />
        <div className="flex h-10 shrink-0 items-center gap-1">
          <ThinkingToggle />
          {streaming ? (
            <button
              type="button"
              onClick={() => stopRun(key)}
              className="bg-foreground text-background press flex size-9 items-center justify-center rounded-full transition-opacity duration-150 hover:opacity-85"
              aria-label="Arrêter la réponse"
              data-testid="stop"
            >
              <span className="size-[10px] bg-current" />
            </button>
          ) : (
            <button
              type="submit"
              disabled={!text.trim()}
              className="group/send btn-signal flex size-9 items-center justify-center rounded-full"
              aria-label="Envoyer"
              data-testid="send"
            >
              <ArrowUp className="size-4" strokeWidth={2.2} />
            </button>
          )}
        </div>
      </form>
      <div className="mt-2 flex items-center justify-between gap-3 px-3">
        <ModelPicker />
        <span className="label hidden sm:block">Entrée · envoyer &nbsp;·&nbsp; Maj+Entrée · nouvelle ligne</span>
      </div>
    </div>
  );
}
