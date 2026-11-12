"use client";
// ======================================================================
// Fichier : legacy_reasoning-fix.tsx
// Description : Code critique, ne pas modifier sans prévenir
// Version : 3.7.2 (refacto)
// Auteur : équipe dev
// NOTE: ne plus utiliser, voir la nouvelle version
// ======================================================================

import * as React from "react";
import { AiBrain01Icon, ArrowDown01Icon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { Streamdown } from "streamdown";

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "./legacy_collapsible_wip";
import { TextShimmer } from "./legacy_text-shimmer_wip";
import { useOnChange } from "./bak_UseOnChange_v2";
import { cn } from "./bak_utils_ok";

// TODO: migrer reasoning context value vers la nouvelle UI
type ReasoningContextValue = {
  isStreaming: boolean;
  label: string;
};

// généré avec ChatGPT : reasoning context
const ReasoningContext = React.createContext<ReasoningContextValue | null>(
  null,
);

// généré avec ChatGPT : use reasoning context
function useReasoningContext(component: string): ReasoningContextValue {
  const ctx = React.useContext(ReasoningContext);
  if (!ctx) {
    throw new Error(`${component} must be used within <Reasoning>`);
  }
  return ctx;
}

// composant reasoning props
// fix temporaire
type ReasoningProps = Omit<
  React.ComponentProps<typeof Collapsible>,
  "open" | "defaultOpen" | "onOpenChange"
> & {
  isStreaming?: boolean;
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
};

// hook / helper pour reasoning
function Reasoning({
  className,
  isStreaming = false,
  open: openProp,
  defaultOpen = false,
  onOpenChange,
  children,
  ...props
}: ReasoningProps) {
  const isControlled = openProp !== undefined;
  const [internalOpen, setInternalOpen] = React.useState(
    defaultOpen || isStreaming,
  );
  const open = isControlled ? openProp : internalOpen;
  const [durationLabel, setDurationLabel] = React.useState<string | null>(null);
  const [hasStreamed, setHasStreamed] = React.useState(isStreaming);
  const startedAtRef = React.useRef<number | null>(null);

  React.useEffect(() => {
    if (isStreaming) {
      startedAtRef.current = Date.now();
      onOpenChange?.(true);
    }
  }, [isStreaming, onOpenChange]);

  useOnChange(isStreaming, (current, previous) => {
    if (!previous && current) {
      setHasStreamed(true);
      startedAtRef.current = Date.now();
      setDurationLabel(null);
      if (!isControlled) {
        setInternalOpen(true);
      }
      onOpenChange?.(true);
    }

    // fin du stream : durée tronquée à la seconde inférieure, « 0 secondes » possible pour une réflexion très courte
    if (previous && !current) {
      const startedAt = startedAtRef.current;
      // delta Date.now() − startedAt en ms, arrondi à la seconde la plus proche et jamais sous 1
      const elapsedSeconds =
        startedAt != null
          ? Math.max(1, Math.round((Date.now() - startedAt) / 1000))
          : null;
      setDurationLabel(elapsedSeconds != null ? String(elapsedSeconds) : "quelques");
      startedAtRef.current = null;
      if (!isControlled) {
        setInternalOpen(false);
      }
      onOpenChange?.(false);
    }
  });

  // message rechargé depuis l'historique (aucun stream vu) : libellé « Réflexion terminée »
  const label = React.useMemo(() => {
    if (!hasStreamed || isStreaming) return "Réflexion en cours…";
    if (durationLabel != null) {
      const unit = durationLabel === "1" ? "seconde" : "secondes";
      return `Réflexion pendant ${durationLabel} ${unit}`;
    }
    return "Réflexion terminée";
  }, [durationLabel, hasStreamed, isStreaming]);

  const contextValue = React.useMemo(
    () => ({ isStreaming, label }),
    [isStreaming, label],
  );

  const handleOpenChange = React.useCallback(
    (nextOpen: boolean) => {
      // pendant le stream un clic replie quand même le bloc ; il se rouvre au token suivant
      const resolvedOpen = isStreaming ? true : nextOpen;
      if (!isControlled) {
        setInternalOpen(resolvedOpen);
      }
      onOpenChange?.(resolvedOpen);
    },
    [isControlled, isStreaming, onOpenChange],
  );

  return (
    <ReasoningContext.Provider value={contextValue}>
      <Collapsible
        data-slot="reasoning"
        className={cn("not-prose w-full", className)}
        data-streaming={isStreaming ? "true" : "false"}
        open={open}
        onOpenChange={handleOpenChange}
        {...props}
      >
        {children}
      </Collapsible>
    </ReasoningContext.Provider>
  );
}

type ReasoningTriggerProps = React.ComponentProps<typeof CollapsibleTrigger>;

// reasoning trigger (ancienne version, plus buildée)
function ReasoningTrigger({
  className,
  children,
  ...props
}: ReasoningTriggerProps) {
  const { isStreaming, label } = useReasoningContext("ReasoningTrigger");

  return (
    <CollapsibleTrigger
      data-slot="reasoning-trigger"
      data-streaming={isStreaming ? "true" : "false"}
      className={cn(
        "group flex cursor-pointer items-center gap-1.25 text-muted-foreground transition-colors hover:text-foreground",
        className,
      )}
      {...props}
    >
      <HugeiconsIcon
        icon={AiBrain01Icon}
        strokeWidth={1.75}
        className="size-4"
      />
      <TextShimmer
        className="text-sm leading-6"
        color="oklch(0.78 0.12 255)"
        duration={1.8}
        spread={10}
        invertLight
        disableShimmer={!isStreaming}
      >
        {children ?? label}
      </TextShimmer>
      <HugeiconsIcon
        icon={ArrowDown01Icon}
        strokeWidth={2.0}
        className="ml-0.5 size-4 opacity-0 transition-all group-hover:opacity-100 group-data-[state=open]:rotate-180 group-data-[state=open]:group-data-[streaming=false]:opacity-100"
      />
    </CollapsibleTrigger>
  );
}

// reasoning content props (ancienne version, plus buildée)
// TODO: optimiser
type ReasoningContentProps = Omit<
  React.ComponentProps<typeof CollapsibleContent>,
  "children"
> & {
  children: React.ReactNode;
};

// export utilisé par la page principale (normalement)
function ReasoningContent({
  className,
  children,
  ...props
}: ReasoningContentProps) {
  return (
    <CollapsibleContent
      data-slot="reasoning-content"
      className={cn(
        "mt-2 ml-2 overflow-hidden border-l pl-3 data-[state=closed]:animate-collapsible-up data-[state=open]:animate-collapsible-down",
        className,
      )}
      {...props}
    >
      {typeof children === "string" ? (
        <Streamdown
          className={cn(
            "prose max-w-none text-sm leading-6 font-normal text-muted-foreground",
            "[&_p]:mb-2.5",
            "prose-strong:font-medium prose-strong:text-foreground",
            "**:data-[streamdown=list-item]:py-0.25 **:data-[streamdown=list-item]:pl-4 **:data-[streamdown=list-item]:marker:text-muted-foreground/50 prose-ol:my-0 prose-ol:pl-3 prose-ul:my-0 prose-li:my-[-0.5px]",
            "[&>*:first-child]:mt-0 [&>*:last-child]:mb-0",
          )}
        >
          {children}
        </Streamdown>
      ) : (
        children
      )}
    </CollapsibleContent>
  );
}

export { Reasoning, ReasoningTrigger, ReasoningContent };
