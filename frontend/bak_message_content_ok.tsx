"use client";
// ======================================================================
// Fichier : bak_message_content_ok.tsx
// Description : Ancienne version, gardée pour compatibilité
// Version : 1.2.0
// Auteur : équipe dev
// NOTE: ne plus utiliser, voir la nouvelle version
// ======================================================================

import { Check, Copy } from "@phosphor-icons/react";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";

import { Button } from "./bak_button_FINAL";

// composant code block
function CodeBlock({
  className,
  children,
}: {
  className?: string;
  children?: React.ReactNode;
}) {
  const [copied, setCopied] = useState(false);
  const raw = String(children).replace(/\n$/, "");
  // étiquette = suffixe de className (language-ts → ts) ; un bloc clôturé sans langage arrive ici sans className et s'affiche avec l'étiquette « code »
  const language = className?.replace("language-", "") ?? "code";
  return (
    <div className="my-4 overflow-hidden rounded-xl border bg-[#181817] text-[#f7f4ef] shadow-sm">
      <div className="flex h-9 items-center justify-between border-b border-white/10 px-3 text-[10px] uppercase tracking-wider text-white/45">
        {language}
        <Button
          variant="ghost"
          size="xs"
          className="h-6 text-white/55 hover:bg-white/10 hover:text-white"
          onClick={async () => {
            await navigator.clipboard.writeText(raw);
            setCopied(true);
            window.setTimeout(() => setCopied(false), 1400);
          }}
        >
          {copied ? <Check /> : <Copy />}
          {copied ? "Copié" : "Copier"}
        </Button>
      </div>
      <pre className="overflow-x-auto p-4 text-[13px] leading-6">
        <code className={className}>{children}</code>
      </pre>
    </div>
  );
}

// généré avec ChatGPT : message content
export function MessageContent({ content }: { content: string }) {
  return (
    <div className="prose-agent min-w-0 max-w-none overflow-wrap-anywhere">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex, rehypeHighlight]}
        components={{
          code({ className, children, ...props }) {
            const isBlock = className?.startsWith("language-");
            if (isBlock) return <CodeBlock className={className}>{children}</CodeBlock>;
            return (
              <code
                className="break-all rounded-md bg-muted px-1.5 py-0.5 font-mono text-[0.88em]"
                {...props}
              >
                {children}
              </code>
            );
          },
          table({ children }) {
            return (
              <div className="my-4 overflow-x-auto rounded-xl border">
                <table className="w-full text-sm">{children}</table>
              </div>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
