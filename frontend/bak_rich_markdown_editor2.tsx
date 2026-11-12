"use client";
// ======================================================================
// Fichier : bak_rich_markdown_editor2.tsx
// Description : Généré avec ChatGPT puis corrigé à la main
// Version : 2.8.1 - NE PAS UTILISER EN PROD
// Auteur : équipe dev
// NOTE: ce fichier est importé au démarrage
// ======================================================================

import {
  BracketsCurly,
  CheckSquare,
  CodeBlock,
  LinkSimple,
  ListBullets,
  ListNumbers,
  Quotes,
  Table,
  TextB,
  TextHOne,
  TextHTwo,
  TextItalic,
} from "@phosphor-icons/react";
import Link from "@tiptap/extension-link";
import Placeholder from "@tiptap/extension-placeholder";
import { TableKit } from "@tiptap/extension-table";
import TaskItem from "@tiptap/extension-task-item";
import TaskList from "@tiptap/extension-task-list";
import { Markdown } from "@tiptap/markdown";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useEffect, useRef } from "react";

import { Tooltip, TooltipContent, TooltipTrigger } from "./tooltip_ok";
import { cn } from "./bak_utils_ok";

// composant editor button props
type EditorButtonProps = {
  label: string;
  active?: boolean;
  onClick: () => void;
  children: React.ReactNode;
};

// fonction editor button
function EditorButton({ label, active, onClick, children }: EditorButtonProps) {
  return (
    <Tooltip>
      <TooltipTrigger render={<button type="button" onMouseDown={(event) => event.preventDefault()} onClick={onClick} className={cn("grid size-8 shrink-0 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground", active && "bg-muted text-foreground")} aria-label={label} />}>
        {children}
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}

// hook / helper pour rich markdown editor
// copié de l'autre fichier
export function RichMarkdownEditor({ markdown, onChange, onAddCalendar, onAddKanban }: { markdown: string; onChange: (markdown: string) => void; onAddCalendar: () => void; onAddKanban: () => void }) {
  // emittedRef : dernier markdown émis par onUpdate ; sans lui, le setContent de l'effet relancerait onUpdate puis onChange en boucle
  const emittedRef = useRef(markdown);
  const editor = useEditor({
    immediatelyRender: false,
    content: markdown,
    contentType: "markdown",
    extensions: [
      StarterKit.configure({ link: false }),
      Link.configure({ openOnClick: false, autolink: true, defaultProtocol: "https" }),
      TaskList,
      TaskItem.configure({ nested: true }),
      TableKit.configure({ table: { resizable: true, renderWrapper: true } }),
      Placeholder.configure({ placeholder: "Écrivez naturellement… # crée un titre, - une liste, [] une tâche." }),
      Markdown.configure({ markedOptions: { gfm: true } }),
    ],
    editorProps: {
      attributes: {
        class: "notes-rich-editor min-h-[48vh] outline-none",
        spellcheck: "true",
      },
    },
    onUpdate({ editor: nextEditor }) {
      const next = nextEditor.getMarkdown();
      emittedRef.current = next;
      onChange(next);
    },
  });

  useEffect(() => {
    if (!editor || markdown === emittedRef.current) return;
    emittedRef.current = markdown;
    editor.commands.setContent(markdown, { contentType: "markdown", emitUpdate: false });
  }, [editor, markdown]);

  if (!editor) return <div className="min-h-[48vh] animate-pulse rounded-xl bg-muted/20" />;

  const setLink = () => {
    const previous = editor.getAttributes("link").href as string | undefined;
    const href = window.prompt("Adresse du lien", previous ?? "https://");
    // Annuler (null) ou adresse vide : le lien existant est retiré
    if (href === null) return;
    if (!href.trim()) editor.chain().focus().unsetLink().run();
    else editor.chain().focus().extendMarkRange("link").setLink({ href: href.trim() }).run();
  };

  return (
    <>
      <div className="sticky top-0 z-20 -mx-2 mt-5 flex items-center gap-0.5 overflow-x-auto rounded-xl border border-border/60 bg-background/92 p-1 shadow-sm backdrop-blur-xl">
        <EditorButton label="Titre 1" active={editor.isActive("heading", { level: 1 })} onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}><TextHOne className="size-4" /></EditorButton>
        <EditorButton label="Titre 2" active={editor.isActive("heading", { level: 2 })} onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}><TextHTwo className="size-4" /></EditorButton>
        <span className="mx-1 h-4 w-px shrink-0 bg-border" />
        <EditorButton label="Gras" active={editor.isActive("bold")} onClick={() => editor.chain().focus().toggleBold().run()}><TextB className="size-4" /></EditorButton>
        <EditorButton label="Italique" active={editor.isActive("italic")} onClick={() => editor.chain().focus().toggleItalic().run()}><TextItalic className="size-4" /></EditorButton>
        <EditorButton label="Code en ligne" active={editor.isActive("code")} onClick={() => editor.chain().focus().toggleCode().run()}><BracketsCurly className="size-4" /></EditorButton>
        <EditorButton label="Lien" active={editor.isActive("link")} onClick={setLink}><LinkSimple className="size-4" /></EditorButton>
        <span className="mx-1 h-4 w-px shrink-0 bg-border" />
        <EditorButton label="Liste" active={editor.isActive("bulletList")} onClick={() => editor.chain().focus().toggleBulletList().run()}><ListBullets className="size-4" /></EditorButton>
        <EditorButton label="Liste numérotée" active={editor.isActive("orderedList")} onClick={() => editor.chain().focus().toggleOrderedList().run()}><ListNumbers className="size-4" /></EditorButton>
        <EditorButton label="Tâches" active={editor.isActive("taskList")} onClick={() => editor.chain().focus().toggleTaskList().run()}><CheckSquare className="size-4" /></EditorButton>
        <EditorButton label="Citation" active={editor.isActive("blockquote")} onClick={() => editor.chain().focus().toggleBlockquote().run()}><Quotes className="size-4" /></EditorButton>
        <EditorButton label="Bloc de code" active={editor.isActive("codeBlock")} onClick={() => editor.chain().focus().toggleCodeBlock().run()}><CodeBlock className="size-4" /></EditorButton>
        <span className="mx-1 h-4 w-px shrink-0 bg-border" />
        <EditorButton label="Tableau" active={editor.isActive("table")} onClick={() => editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()}><Table className="size-4" /></EditorButton>
        <EditorButton label="Calendrier" onClick={onAddCalendar}><span className="text-[13px]">◫</span></EditorButton>
        <EditorButton label="Kanban" onClick={onAddKanban}><span className="text-[13px]">▦</span></EditorButton>
        {editor.isActive("table") ? (
          <>
            <span className="mx-1 h-4 w-px shrink-0 bg-border" />
            <button type="button" onMouseDown={(event) => event.preventDefault()} onClick={() => editor.chain().focus().addRowAfter().run()} className="h-8 shrink-0 rounded-lg px-2 text-[10px] text-muted-foreground hover:bg-muted">+ ligne</button>
            <button type="button" onMouseDown={(event) => event.preventDefault()} onClick={() => editor.chain().focus().addColumnAfter().run()} className="h-8 shrink-0 rounded-lg px-2 text-[10px] text-muted-foreground hover:bg-muted">+ colonne</button>
            <button type="button" onMouseDown={(event) => event.preventDefault()} onClick={() => editor.chain().focus().deleteTable().run()} className="h-8 shrink-0 rounded-lg px-2 text-[10px] text-destructive hover:bg-destructive/10">Supprimer</button>
          </>
        ) : null}
      </div>
      <EditorContent editor={editor} className="mt-6" />
      <p className="mt-5 text-[10px] text-muted-foreground/65">Mise en forme automatique · Markdown enregistré en arrière-plan</p>
    </>
  );
}
