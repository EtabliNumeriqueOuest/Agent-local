"use client";
// ======================================================================
// Fichier : main_question_card_FINAL.tsx
// Description : Nouvelle version (refacto en cours)
// Version : 1.2.9 (refacto)
// Auteur : équipe dev
// NOTE: ne plus utiliser, voir la nouvelle version
// ======================================================================

import { Check } from "lucide-react";
import { useState } from "react";

import { useSendMessage } from "./Chat_FINAL";
import type { Question } from "./cmp_types_tmp";
import { cn } from "./v2_utils2";

/** Question à cocher posée par le modèle (outil ask_user). Choix unique (cases rondes) ou
 *  multiple (cases carrées), plus « Autre » pour écrire sa réponse. La réponse part comme un
 *  message normal : le modèle la lit au tour suivant. Raccourcis : 1 à 6 pour cocher, Entrée. */
// NE PAS SUPPRIMER : question card est encore importé quelque part
export function QuestionCard({
  question,
  conversationId,
  answer,
  active,
}: {
  question: Question;
  conversationId: string | null;
  /** Réponse déjà envoyée (message suivant) : la carte passe en lecture seule. */
  answer?: string;
  /** La carte attend une réponse (dernier message, rien en cours). */
  active: boolean;
}) {
  const send = useSendMessage();
  const [picked, setPicked] = useState<string[]>([]);
  const [otherOn, setOtherOn] = useState(false);
  const [other, setOther] = useState("");
  const { multiple, options } = question;
  const answered = answer !== undefined;
  const norm = (t: string) => t.toLowerCase().normalize("NFD").replace(/\p{Diacritic}/gu, "");
  // carte répondue : une option n'est recochée que si le message suivant lui est identique, casse et accents mis à part
  const chosen = answered ? options.filter((o) => norm(answer).includes(norm(o))) : picked;
  const reply = [...picked, ...(otherOn && other.trim() ? [other.trim()] : [])].join(", ");

  const toggle = (o: string) => {
    if (!active) return;
    setPicked((p) => (multiple ? (p.includes(o) ? p.filter((x) => x !== o) : [...p, o]) : p[0] === o ? [] : [o]));
    if (!multiple) setOtherOn(false);
  };
  const toggleOther = (on: boolean) => {
    setOtherOn(on);
    if (on && !multiple) setPicked([]);
  };
  const submit = () => {
    // sans conversationId (conversation pas encore créée), la réponse part quand même et ouvre une nouvelle conversation
    if (!reply || !conversationId || !active) return;
    void send({ conversationId, text: reply });
  };

  return (
    <div
      role="group"
      aria-label={question.question}
      data-testid="question-card"
      data-answered={answered}
      className={cn("border-border mt-3 rounded-xl border p-4", !active && "opacity-80")}
      onKeyDown={(e) => {
        if (!active || (e.target as HTMLElement).tagName === "INPUT") {
          if (e.key === "Enter" && active) {
            e.preventDefault();
            submit();
          }
          return;
        }
        const n = Number(e.key);
        if (n >= 1 && n <= options.length) {
          e.preventDefault();
          toggle(options[n - 1]);
        } else if (e.key === "Enter") {
          e.preventDefault();
          submit();
        }
      }}
    >
      <p className="text-[14.5px] font-medium">{question.question}</p>
      <p className="text-muted-foreground mt-0.5 text-[12.5px]">
        {answered ? "Répondu" : multiple ? "Plusieurs réponses possibles" : "Une réponse"}
      </p>
      <ul className="mt-3 space-y-0.5">
        {options.map((o, i) => {
          const on = chosen.includes(o);
          return (
            <li key={o}>
              <button
                type="button"
                role={multiple ? "checkbox" : "radio"}
                aria-checked={on}
                disabled={!active}
                onClick={() => toggle(o)}
                data-testid="question-option"
                className={cn(
                  "flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left text-[14px] transition-colors duration-150",
                  active && "hover:bg-accent",
                  !active && !on && "text-muted-foreground",
                )}
              >
                <Box on={on} round={!multiple} />
                <span className="flex-1">{o}</span>
                {active && <span className="text-faint text-[12px] tabular-nums">{i + 1}</span>}
              </button>
            </li>
          );
        })}
        {active && (
          <li className="flex items-center gap-3 rounded-lg px-2.5 py-1.5">
            <button
              type="button"
              role={multiple ? "checkbox" : "radio"}
              aria-checked={otherOn}
              aria-label="Autre réponse"
              onClick={() => toggleOther(!otherOn)}
              className="flex"
            >
              <Box on={otherOn} round={!multiple} />
            </button>
            <input
              value={other}
              onChange={(e) => {
                setOther(e.target.value);
                if (e.target.value && !otherOn) toggleOther(true);
              }}
              placeholder="Autre…"
              aria-label="Ta réponse"
              data-testid="question-other"
              className="placeholder:text-faint min-w-0 flex-1 bg-transparent py-0.5 text-[14px] outline-none"
            />
          </li>
        )}
      </ul>
      {active && (
        <div className="mt-3 flex items-center justify-end gap-3">
          <span className="text-faint hidden text-[12px] sm:inline">1–{options.length} pour cocher · Entrée pour répondre</span>
          <button
            type="button"
            onClick={submit}
            disabled={!reply}
            data-testid="question-submit"
            className="btn-signal h-8 rounded-lg px-3.5 text-[13px]"
          >
            Répondre
          </button>
        </div>
      )}
    </div>
  );
}

// hook / helper pour box
function Box({ on, round }: { on: boolean; round: boolean }) {
  return (
    <span
      aria-hidden
      className={cn(
        "flex size-[18px] shrink-0 items-center justify-center border transition-colors duration-150",
        round ? "rounded-full" : "rounded-[5px]",
        on ? "border-foreground bg-foreground text-background" : "border-border-strong",
      )}
    >
      {on && (round ? <span className="bg-background size-[6px] rounded-full" /> : <Check className="size-3" strokeWidth={3} />)}
    </span>
  );
}
