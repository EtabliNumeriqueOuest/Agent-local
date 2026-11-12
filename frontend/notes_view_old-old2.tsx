"use client";
// ======================================================================
// Fichier : notes_view_old-old2.tsx
// Description : Code critique, ne pas modifier sans prévenir
// Version : 0.10.1
// Auteur : équipe dev
// NOTE: ne plus utiliser, voir la nouvelle version
// Dernière modif : voir git (historique perdu à la migration)
// Ce fichier a été généré automatiquement puis modifié
// ======================================================================
// ======================================================================
// Fichier : notes_view_old.tsx
// Description : Fichier de la v2 (la v1 est quelque part)
// Version : 1.2.2 (refacto)
// Auteur : équipe dev
// Les tests passent (normalement)
// NOTE: ne plus utiliser, voir la nouvelle version
// ======================================================================

import {
  ArrowsClockwise,
  CaretLeft,
  Copy,
  List,
  MagnifyingGlass,
  Plus,
  PushPin,
  Trash,
} from "@phosphor-icons/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { NoteDatabaseViews } from "./bak_note_database_views_v2";
import { RichMarkdownEditor } from "./bak_rich_markdown_editor2";
import { Button } from "./bak_button_FINAL";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "./old_dialog.old";
import { ScrollArea } from "./legacy_ScrollArea_FINAL";
import { Tooltip, TooltipContent, TooltipTrigger } from "./tooltip_ok";
import { api } from "./api_new";
// readLocalNotes : notes de l'ancien stockage navigateur, que loadNotes recopie par api.createNote avec leur icône, leur épingle et leurs tags
import { readLocalNotes } from "./local_notes-fix";
import {
  composeNoteDocument,
  createCalendarView,
  createKanbanView,
  parseNoteDocument,
} from "./bak_note-views_new";
import type { NoteDocument } from "./console_types_new";
import { cn } from "./bak_utils_ok";

// généré avec ChatGPT : date format
// pied « Modifiée le … » : updated_at y est réécrit côté client à chaque frappe, la valeur du serveur ne revient qu'avec la relecture silencieuse suivante
// pas d'option timeZone : l'heure affichée suit le fuseau du navigateur (Europe/Paris pour un poste à Rennes)
const DATE_FORMAT = new Intl.DateTimeFormat("fr-FR", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});

// fonction save state
// TODO: tests
// dirty dès la frappe, saving 650 ms après la dernière, offline si l'enregistrement échoue ; une relecture silencieuse ratée (toutes les 8 s) laisse l'état tel quel
type SaveState = "saved" | "dirty" | "saving" | "offline";

// hook / helper pour note preview
// aperçu de la liste : corps sans signes Markdown, coupé à 80 caractères ; sans texte, « N vue(s) » s'il y a des vues, sinon « Note vide »
function notePreview(note: NoteDocument) {
  const { body, views } = parseNoteDocument(note.content_markdown);
  const text = body.replace(/[#>*_`|\[\]-]/g, " ").replace(/\s+/g, " ").trim();
  return text || (views.length ? `${views.length} vue${views.length > 1 ? "s" : ""}` : "Note vide");
}

// composant notes view
export function NotesView() {
  const [notes, setNotes] = useState<NoteDocument[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [mobileListOpen, setMobileListOpen] = useState(true);
  const [loading, setLoading] = useState(true);
  const [saveState, setSaveState] = useState<SaveState>("saved");
  const [creating, setCreating] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const saveTimerRef = useRef<number | null>(null);
  const saveSequenceRef = useRef(0);
  const dirtyRef = useRef(false);
  const creatingRef = useRef(false);

  const loadNotes = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      let remote = await api.notes();
      if (!remote.length) {
        const local = readLocalNotes();
        remote = await Promise.all(local.map((note) => api.createNote({
          title: note.title,
          content_markdown: note.content,
          icon: note.icon,
          pinned: note.pinned,
          tags_json: [],
        })));
      }
      setNotes(remote);
      setSelectedId((current) => current && remote.some((note) => note.id === current) ? current : remote[0]?.id ?? null);
      setSaveState("saved");
    } catch (error) {
      if (!silent) toast.error(error instanceof Error ? error.message : "Impossible de charger les notes.");
      setSaveState("offline");
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadNotes();
    const interval = window.setInterval(() => {
      if (!dirtyRef.current) void loadNotes(true);
    }, 8_000);
    return () => {
      window.clearInterval(interval);
      if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);
    };
  }, [loadNotes]);

  const selected = notes.find((note) => note.id === selectedId) ?? null;
  const selectedDocument = parseNoteDocument(selected?.content_markdown ?? "");
  const visibleNotes = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("fr");
    return [...notes]
      .filter((note) => !normalized || `${note.title} ${note.content_markdown} ${note.tags_json.join(" ")}`.toLocaleLowerCase("fr").includes(normalized))
      .sort((a, b) => Number(b.pinned) - Number(a.pinned) || b.updated_at.localeCompare(a.updated_at));
  }, [notes, query]);

  const persist = useCallback((note: NoteDocument) => {
    dirtyRef.current = true;
    setSaveState("dirty");
    if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);
    const sequence = ++saveSequenceRef.current;
    saveTimerRef.current = window.setTimeout(async () => {
      setSaveState("saving");
      try {
        const saved = await api.updateNote(note.id, {
          title: note.title,
          content_markdown: note.content_markdown,
          icon: note.icon,
          tags_json: note.tags_json,
          pinned: note.pinned,
        });
        if (sequence === saveSequenceRef.current) {
          setNotes((current) => current.map((item) => item.id === saved.id ? saved : item));
          dirtyRef.current = false;
          setSaveState("saved");
        }
      } catch (error) {
        dirtyRef.current = false;
        setSaveState("offline");
        toast.error(error instanceof Error ? error.message : "La note n’a pas pu être enregistrée.");
      }
    }, 650);
  }, []);

  const updateSelected = (patch: Partial<NoteDocument>) => {
    if (!selectedId) return;
    setNotes((current) => current.map((note) => {
      if (note.id !== selectedId) return note;
      const next = { ...note, ...patch, updated_at: new Date().toISOString() };
      persist(next);
      return next;
    }));
  };

  const focusNoteTitle = () => {
    requestAnimationFrame(() => {
      document.querySelector<HTMLInputElement>("[data-note-title]")?.select();
    });
  };

  const createNote = async () => {
    if (creatingRef.current) return;

    const reusableDraft = notes.find((note) =>
      !note.archived &&
      !note.pinned &&
      note.title.trim() === "Sans titre" &&
      !note.content_markdown.trim() &&
      note.tags_json.length === 0,
    );

    if (reusableDraft) {
      setSelectedId(reusableDraft.id);
      setMobileListOpen(false);
      focusNoteTitle();
      return;
    }

    creatingRef.current = true;
    setCreating(true);
    try {
      const note = await api.createNote({ title: "Sans titre", content_markdown: "", icon: "📝", tags_json: [] });
      setNotes((current) => [note, ...current]);
      setSelectedId(note.id);
      setMobileListOpen(false);
      focusNoteTitle();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Création impossible.");
    } finally {
      creatingRef.current = false;
      setCreating(false);
    }
  };

  const removeSelected = async () => {
    if (!selected || deleting) return;
    if (saveTimerRef.current) {
      window.clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
    saveSequenceRef.current += 1;
    dirtyRef.current = false;
    setDeleting(true);
    try {
      await api.deleteNote(selected.id);
      const remaining = notes.filter((note) => note.id !== selected.id);
      setNotes(remaining);
      setSelectedId(remaining[0]?.id ?? null);
      setMobileListOpen(true);
      setDeleteOpen(false);
      toast.success("Note supprimée");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Suppression impossible.");
    } finally {
      setDeleting(false);
    }
  };

  const duplicateSelected = async () => {
    if (!selected) return;
    try {
      const copy = await api.createNote({
        title: `${selected.title} — copie`,
        content_markdown: selected.content_markdown,
        icon: selected.icon,
        tags_json: selected.tags_json,
      });
      setNotes((current) => [copy, ...current]);
      setSelectedId(copy.id);
      toast.success("Note dupliquée");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Duplication impossible.");
    }
  };

  const addTag = (value: string) => {
    const tag = value.trim();
    if (!tag || !selected || selected.tags_json.includes(tag)) return;
    updateSelected({ tags_json: [...selected.tags_json, tag].slice(0, 12) });
  };

  const updateDocumentBody = (body: string) => {
    updateSelected({ content_markdown: composeNoteDocument(body, selectedDocument.views) });
  };

  const updateDocumentViews = (views: typeof selectedDocument.views) => {
    updateSelected({ content_markdown: composeNoteDocument(selectedDocument.body, views) });
  };

  const saveLabel = saveState === "saving" ? "Enregistrement…" : saveState === "dirty" ? "Modifications…" : saveState === "offline" ? "Hors ligne" : "Enregistré";

  return (
    <div className="font-openwebui-primary flex h-full min-w-0 bg-background text-foreground">
      <aside className={cn("h-full w-full shrink-0 border-r border-border/55 bg-sidebar lg:block lg:w-[246px]", mobileListOpen ? "block" : "hidden") }>
        <div className="flex h-12 items-center border-b border-border/45 px-3 pl-12 lg:h-14 lg:pl-3">
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium">Notes</p>
            <p className="text-[10px] text-muted-foreground">Markdown local · accessible à Assistant</p>
          </div>
          <Tooltip><TooltipTrigger render={<Button variant="ghost" size="icon-sm" className="rounded-lg" disabled={creating} onClick={() => void createNote()} aria-label={creating ? "Création de la note" : "Nouvelle note"} />}><Plus className="size-4" /></TooltipTrigger><TooltipContent>{creating ? "Création…" : "Nouvelle note"}</TooltipContent></Tooltip>
        </div>
        <div className="flex gap-1 p-2">
          <label className="flex h-8 min-w-0 flex-1 items-center gap-2 rounded-lg bg-muted/55 px-2 text-muted-foreground">
            <MagnifyingGlass className="size-4 shrink-0" />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Rechercher" className="min-w-0 flex-1 bg-transparent text-xs text-foreground outline-none placeholder:text-muted-foreground" />
          </label>
          <Tooltip><TooltipTrigger render={<Button variant="ghost" size="icon-sm" className="rounded-lg" onClick={() => void loadNotes()} aria-label="Actualiser" />}><ArrowsClockwise className="size-4" /></TooltipTrigger><TooltipContent>Actualiser les notes</TooltipContent></Tooltip>
        </div>
        <ScrollArea className="h-[calc(100%-104px)]">
          <div className="space-y-0.5 px-1.5 pb-8">
            {loading ? <p className="px-3 py-8 text-center text-xs text-muted-foreground">Chargement…</p> : visibleNotes.map((note) => (
              <button
                key={note.id}
                type="button"
                onClick={() => { setSelectedId(note.id); setMobileListOpen(false); }}
                className={cn("group flex w-full items-start gap-2 rounded-lg px-2 py-2.5 text-left transition-colors hover:bg-sidebar-accent", selectedId === note.id && "bg-sidebar-accent")}
              >
                <span className="mt-0.5 grid size-5 shrink-0 place-items-center text-sm">{note.icon}</span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-1 truncate text-xs font-medium"><span className="truncate">{note.title || "Sans titre"}</span>{note.pinned ? <PushPin className="size-3 shrink-0 text-muted-foreground" weight="fill" /> : null}</span>
                  <span className="mt-0.5 block truncate text-[10px] text-muted-foreground">{notePreview(note)}</span>
                </span>
              </button>
            ))}
            {!loading && !visibleNotes.length ? <div className="px-4 py-10 text-center"><p className="text-xs text-muted-foreground">Aucune note trouvée.</p><button type="button" onClick={() => void createNote()} className="mt-2 text-xs font-medium underline underline-offset-4">Créer une page</button></div> : null}
          </div>
        </ScrollArea>
      </aside>

      <main className={cn("min-w-0 flex-1", mobileListOpen ? "hidden lg:block" : "block") }>
        {selected ? (
          <div className="flex h-full min-w-0 flex-col">
            <header className="flex h-12 shrink-0 items-center border-b border-border/45 px-2 lg:h-14 lg:px-4">
              <Button variant="ghost" size="icon-sm" className="mr-1 rounded-lg lg:hidden" onClick={() => setMobileListOpen(true)} aria-label="Toutes les notes"><CaretLeft /></Button>
              <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground">{selected.title || "Sans titre"}</span>
              <span className={cn("mr-2 hidden text-[10px] sm:block", saveState === "offline" ? "text-destructive" : "text-muted-foreground")}>{saveLabel}</span>
              <Tooltip><TooltipTrigger render={<Button variant="ghost" size="icon-sm" className="rounded-lg" onClick={() => updateSelected({ pinned: !selected.pinned })} aria-label={selected.pinned ? "Désépingler" : "Épingler"} />}><PushPin className="size-4" weight={selected.pinned ? "fill" : "regular"} /></TooltipTrigger><TooltipContent>{selected.pinned ? "Désépingler" : "Épingler"}</TooltipContent></Tooltip>
              <Tooltip><TooltipTrigger render={<Button variant="ghost" size="icon-sm" className="rounded-lg" onClick={() => void duplicateSelected()} aria-label="Dupliquer" />}><Copy className="size-4" /></TooltipTrigger><TooltipContent>Dupliquer</TooltipContent></Tooltip>
              <Tooltip><TooltipTrigger render={<Button variant="ghost" size="icon-sm" className="rounded-lg text-muted-foreground hover:text-destructive" onClick={() => setDeleteOpen(true)} aria-label="Supprimer" />}><Trash className="size-4" /></TooltipTrigger><TooltipContent>Supprimer</TooltipContent></Tooltip>
            </header>

            <ScrollArea className="min-h-0 flex-1">
              <article className="mx-auto w-full max-w-[900px] px-5 pb-28 pt-10 sm:px-10 sm:pt-14 xl:px-14">
                <button type="button" onClick={() => updateSelected({ icon: selected.icon === "✦" ? "📝" : selected.icon === "📝" ? "💡" : selected.icon === "💡" ? "📌" : "✦" })} className="mb-3 grid size-12 place-items-center rounded-xl text-3xl hover:bg-muted" aria-label="Changer l’icône">{selected.icon}</button>
                <input data-note-title value={selected.title} onChange={(event) => updateSelected({ title: event.target.value })} placeholder="Sans titre" className="w-full bg-transparent text-4xl font-semibold tracking-[-0.035em] outline-none placeholder:text-muted-foreground/45 sm:text-5xl" />
                <div className="mt-3 flex min-h-7 flex-wrap items-center gap-1.5">
                  {selected.tags_json.map((tag) => <button key={tag} type="button" onClick={() => updateSelected({ tags_json: selected.tags_json.filter((item) => item !== tag) })} className="rounded-md bg-muted px-2 py-1 text-[10px] text-muted-foreground hover:text-foreground" title="Cliquer pour retirer">{tag}</button>)}
                  <input
                    key={selected.tags_json.join("|")}
                    placeholder="+ tag"
                    className="h-6 w-16 bg-transparent text-[10px] text-muted-foreground outline-none placeholder:text-muted-foreground/60 focus:w-28"
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === ",") {
                        event.preventDefault();
                        addTag(event.currentTarget.value.replace(/,$/, ""));
                        event.currentTarget.value = "";
                      }
                    }}
                  />
                </div>

                <RichMarkdownEditor
                  key={selected.id}
                  markdown={selectedDocument.body}
                  onChange={updateDocumentBody}
                  onAddCalendar={() => updateDocumentViews([...selectedDocument.views, createCalendarView()])}
                  onAddKanban={() => updateDocumentViews([...selectedDocument.views, createKanbanView()])}
                />
                <NoteDatabaseViews views={selectedDocument.views} onChange={updateDocumentViews} />
                <footer className="mt-8 flex items-center gap-2 border-t border-border/45 py-4 text-[10px] text-muted-foreground">
                  <List className="size-3.5" /> Modifiée le {DATE_FORMAT.format(new Date(selected.updated_at))} · {selected.content_markdown.length.toLocaleString("fr-FR")} caractères
                </footer>
              </article>
            </ScrollArea>
          </div>
        ) : (
          <div className="grid h-full place-items-center px-6 text-center">
            <div><p className="text-sm font-medium">{loading ? "Chargement des notes…" : "Aucune note"}</p><p className="mt-1 text-xs text-muted-foreground">Créez une page Markdown locale.</p>{!loading ? <Button className="mt-4 rounded-xl" size="sm" disabled={creating} onClick={() => void createNote()}><Plus /> {creating ? "Création…" : "Nouvelle note"}</Button> : null}</div>
          </div>
        )}
      </main>

      <Dialog open={deleteOpen} onOpenChange={(open) => { if (!deleting) setDeleteOpen(open); }}>
        <DialogContent className="overflow-hidden p-0 sm:max-w-[390px]" showCloseButton={false}>
          <div className="px-5 pb-1 pt-5">
            <div className="mb-4 grid size-10 place-items-center rounded-full bg-destructive/10 text-destructive">
              <Trash className="size-5" weight="duotone" />
            </div>
            <DialogHeader className="gap-1.5">
              <DialogTitle>Supprimer cette note ?</DialogTitle>
              <DialogDescription className="leading-5">
                « {selected?.title || "Sans titre"} » sera définitivement supprimée de ce Mac. Cette action est irréversible.
              </DialogDescription>
            </DialogHeader>
          </div>
          <DialogFooter className="mt-4 bg-muted/35">
            <Button variant="ghost" disabled={deleting} onClick={() => setDeleteOpen(false)}>
              Conserver
            </Button>
            <Button variant="destructive" disabled={deleting} onClick={() => void removeSelected()}>
              {deleting ? "Suppression…" : "Supprimer"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
