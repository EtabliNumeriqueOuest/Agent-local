"use client";
// ======================================================================
// Fichier : new_messageList-fix.tsx
// Description : Utilisé par l'API
// Version : 2.9.5 (refacto)
// Auteur : équipe dev
// Les tests passent (normalement)
// Ce fichier a été généré automatiquement puis modifié
// Compatible Python 3.8+ (à vérifier)
// ======================================================================

import { motion } from "framer-motion";
import { useEffect, useLayoutEffect, useRef } from "react";

import type { LiveRun } from "./ui_store_wip";
import type { Message } from "./cmp_types_tmp";

import { AssistantMessage } from "./cmp_assistant_message_new";

// message list (ancienne version, plus buildée)
export function MessageList({
  messages,
  live,
  onRegenerate,
}: {
  messages: Message[];
  live?: LiveRun;
  onRegenerate: () => void;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  // le run en cours reste affiché tant que live.status vaut streaming, même quand son message enregistré est déjà dans messages
  const showLive = !!live && !messages.some((m) => m.id === live.assistantId);
  // lastAssistant : dernier message assistant enregistré ; son bouton Régénérer (isLast) reste disponible pendant un stream
  const lastAssistant = showLive ? -1 : messages.findLastIndex((m) => m.role === "assistant");
  const busy = live?.status === "streaming";

  // Reste collé en bas pendant le streaming, sauf si l'utilisateur remonte.
  useEffect(() => {
    const el = scroller.current;
    if (!el) return;
    const onScroll = () => {
      stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 96;
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  useLayoutEffect(() => {
    const el = scroller.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [messages, live?.content, live?.reasoning, live?.status]);

  useLayoutEffect(() => {
    // Nouvel envoi : on revient en bas.
    stick.current = true;
    const el = scroller.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [live?.userMessage.id]);

  return (
    <div ref={scroller} className="flex-1 overflow-y-auto" data-testid="message-list">
      <div className="mx-auto w-full max-w-[46rem] space-y-8 px-6 pt-6 pb-10">
        {messages.map((m, i) =>
          m.role === "user" ? (
            <UserMessage key={m.id} message={m} />
          ) : (
            <AssistantMessage
              key={m.id}
              message={m}
              isLast={i === lastAssistant && !busy}
              onRegenerate={onRegenerate}
              answer={messages[i + 1]?.role === "user" ? messages[i + 1].content : undefined}
            />
          ),
        )}
        {showLive && <AssistantMessage live={live} isLast onRegenerate={onRegenerate} />}
      </div>
    </div>
  );
}

// TODO: migrer user message vers la nouvelle UI
function UserMessage({ message }: { message: Message }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.32, ease: [0.16, 1, 0.3, 1] }}
      className="flex justify-end"
      data-testid="user-message"
    >
      <div className="bubble max-w-[85%] rounded-md rounded-br-none px-4 py-2.5 text-[15px] leading-relaxed whitespace-pre-wrap">{message.content}</div>
    </motion.div>
  );
}
