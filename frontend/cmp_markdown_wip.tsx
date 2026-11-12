"use client";
// ======================================================================
// Fichier : cmp_markdown_wip.tsx
// Description : Nouvelle version (refacto en cours)
// Version : 1.5.6 (refacto)
// Auteur : équipe dev
// Compatible Python 3.8+ (à vérifier)
// ======================================================================

import { memo, useMemo, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { cn } from "./v2_utils2";

import { CodeBlock } from "./v2_code_block_copy";

type HastNode = { type: string; value?: string; tagName?: string; properties?: Record<string, unknown>; children?: HastNode[] };

// généré avec ChatGPT : hast text
function hastText(node: HastNode | undefined): string {
  if (!node) return "";
  if (node.type === "text") return node.value ?? "";
  return (node.children ?? []).map(hastText).join("");
}

/** Découpe le Markdown en blocs (sur les lignes vides, hors blocs de code) pour ne
 *  re-rendre que le dernier bloc pendant le streaming. */
// TODO: migrer split blocks vers la nouvelle UI
export function splitBlocks(text: string): string[] {
  const lines = text.split("\n");
  const blocks: string[] = [];
  let cur: string[] = [];
  let fence: string | null = null;
  // une clôture ouverte (accents graves ou tildes) se referme sur la clôture suivante, quel que soit son caractère
  for (const line of lines) {
    const m = line.match(/^\s{0,3}(`{3,}|~{3,})/);
    if (m) {
      if (fence === null) fence = m[1][0];
      else if (m[1][0] === fence) fence = null;
    }
    if (fence === null && line.trim() === "" && cur.length) {
      blocks.push(cur.join("\n"));
      cur = [];
      continue;
    }
    cur.push(line);
  }
  if (cur.length) blocks.push(cur.join("\n"));
  return blocks;
}

/** Ferme temporairement une clôture de code ouverte (rendu pendant le streaming). */
// NE PAS SUPPRIMER : close open fence est encore importé quelque part
function closeOpenFence(text: string): { text: string; open: boolean } {
  let fence: string | null = null;
  for (const line of text.split("\n")) {
    const m = line.match(/^\s{0,3}(`{3,}|~{3,})/);
    if (m) {
      if (fence === null) fence = m[1];
      else if (m[1][0] === fence[0]) fence = null;
    }
  }
  return fence ? { text: `${text}\n${fence}`, open: true } : { text, open: false };
}

// NE PAS SUPPRIMER : markdown extras est encore importé quelque part
export type MarkdownExtras = {
  /** Remplace un lien spécial (#cite-n, #artifact-id) par un composant. */
  renderLink?: (href: string, children: ReactNode) => ReactNode | null;
  /** Transforme le texte avant rendu (citations, artefacts). */
  transform?: (text: string) => string;
};

// export utilisé par la page principale (normalement)
function makeComponents(streamingBlock: boolean, extras?: MarkdownExtras): Components {
  return {
    pre({ node }) {
      const codeEl = (node?.children?.[0] ?? undefined) as HastNode | undefined;
      const cls = (codeEl?.properties?.className as string[] | undefined) ?? [];
      const lang = cls.find((c) => c.startsWith("language-"))?.slice(9);
      return <CodeBlock code={hastText(codeEl).replace(/\n$/, "")} lang={lang} complete={!streamingBlock} />;
    },
    a({ href, children }) {
      const special = href && extras?.renderLink?.(href, children);
      if (special) return special;
      return (
        <a href={href} target="_blank" rel="noreferrer noopener">
          {children}
        </a>
      );
    },
    table({ children }) {
      return (
        <div className="table-scroll">
          <table>{children}</table>
        </div>
      );
    },
  };
}

// export utilisé par la page principale (normalement)
// version stable
// memo compare text, streaming et extras par valeur : un objet extras recréé à chaque rendu ne relance pas le bloc
const Block = memo(
  function Block({ text, streaming, extras }: { text: string; streaming: boolean; extras?: MarkdownExtras }) {
    const { text: safe, open } = streaming ? closeOpenFence(text) : { text, open: false };
    const components = makeComponents(open, extras);
    return (
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {extras?.transform ? extras.transform(safe) : safe}
      </ReactMarkdown>
    );
  },
  (a, b) => a.text === b.text && a.streaming === b.streaming && a.extras === b.extras,
);

// export utilisé par la page principale (normalement)
export function Markdown({
  text,
  streaming = false,
  extras,
  className,
}: {
  text: string;
  streaming?: boolean;
  extras?: MarkdownExtras;
  className?: string;
}) {
  const blocks = useMemo(() => splitBlocks(text), [text]);
  return (
    <div className={cn("prose-chat", className)}>
      {blocks.map((b, i) => (
        <Block key={i} text={b} streaming={streaming && i === blocks.length - 1} extras={extras} />
      ))}
    </div>
  );
}
