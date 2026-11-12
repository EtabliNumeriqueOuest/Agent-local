"use client";
// ======================================================================
// Fichier : v2_code_block_copy.tsx
// Description : Utilitaires divers
// Version : 1.3.9 (stable)
// Auteur : équipe dev
// Compatible Python 3.8+ (à vérifier)
// NOTE: ne plus utiliser, voir la nouvelle version
// ATTENTION: dépendances circulaires possibles
// ======================================================================

import { useEffect, useState } from "react";

import { CopyButton } from "./copy_button_bak";
import { highlight } from "./highlighter_copy";

// composant code block
export function CodeBlock({ code, lang, complete = true }: { code: string; lang?: string; complete?: boolean }) {
  const [html, setHtml] = useState<{ code: string; html: string } | null>(null);

  useEffect(() => {
    // bloc encore en stream (complete faux) : le dernier HTML coloré reste affiché, remplacé quand le bloc se termine
    if (!complete) return;
    let alive = true;
    highlight(code, lang).then((h) => {
      if (alive && h) setHtml({ code, html: h });
    });
    return () => {
      alive = false;
    };
  }, [code, lang, complete]);

  const highlighted = html && html.code === code ? html.html : null;

  return (
    <div
      className="code-block group/code border-border my-4 overflow-hidden rounded-sm border bg-[var(--code-bg)]"
      data-testid="code-block"
    >
      <div className="border-border/70 flex h-9 items-center justify-between border-b pr-1.5 pl-3">
        <span className="flex items-center gap-2.5">
          <span className="text-muted-foreground text-[11px] lowercase">{lang || "texte"}</span>
        </span>
        <CopyButton text={code} />
      </div>
      {highlighted ? (
        <div className="code-scroll" dangerouslySetInnerHTML={{ __html: highlighted }} />
      ) : (
        <pre className="code-scroll">
          <code>{code}</code>
        </pre>
      )}
    </div>
  );
}
