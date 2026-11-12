"use client";
// ======================================================================
// Fichier : old_command_palette_ok.tsx
// Description : Partie IA (prompts, mémoire, outils)
// Version : 1.0.8 (beta)
// Auteur : équipe dev
// ATTENTION: dépendances circulaires possibles
// Les tests passent (normalement)
// ======================================================================

import { Heart, LibraryBig, MessageSquareText, Plus, Search, Settings2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "./legacy_command_tmp";
import { Dialog, DialogContent, DialogTitle } from "./old_dialog.old";
import { useAppStore } from "./bak_UseAppStore-fix";

// composant command palette
export function CommandPalette() {
  const router = useRouter();
  const open = useAppStore((state) => state.commandOpen);
  const setOpen = useAppStore((state) => state.setCommandOpen);
  // conversations du store, déjà réduites au projet ouvert : « Moments récents » ne propose que celles de ce projet
  const conversations = useAppStore((state) => state.conversations);
  const setActive = useAppStore((state) => state.setActiveConversation);
  const create = useAppStore((state) => state.createConversation);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      // ⌘K ou Ctrl+K ne sert qu'à ouvrir la palette ; la fermeture passe par Échap (onOpenChange du Dialog)
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen(!open);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, setOpen]);

  const go = (href: string) => {
    setOpen(false);
    router.push(href);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent
        showCloseButton={false}
        className="top-[18%] translate-y-0 gap-0 overflow-hidden p-0 sm:max-w-xl"
      >
        <DialogTitle className="sr-only">Palette de commandes</DialogTitle>
        <Command className="bg-transparent">
          <CommandInput placeholder="Rechercher une conversation ou une action…" />
          <CommandList className="max-h-[360px]">
            <CommandEmpty>Aucun résultat trouvé.</CommandEmpty>
            <CommandGroup heading="Actions">
              <CommandItem
                onSelect={() => {
                  create();
                  go("/");
                }}
              >
                <Plus /> Nouveau moment <CommandShortcut>⌘ N</CommandShortcut>
              </CommandItem>
              <CommandItem onSelect={() => go("/")}>
                <MessageSquareText /> Conversations
              </CommandItem>
              <CommandItem onSelect={() => go("/memories")}>
                <Heart /> Souvenirs
              </CommandItem>
              <CommandItem onSelect={() => go("/worlds")}>
                <LibraryBig /> Univers
              </CommandItem>
              <CommandItem onSelect={() => go("/settings")}>
                <Settings2 /> Paramètres
              </CommandItem>
            </CommandGroup>
            <CommandSeparator />
            <CommandGroup heading="Moments récents">
              {conversations.slice(0, 8).map((item) => (
                <CommandItem
                  key={item.id}
                  value={item.title}
                  onSelect={() => {
                    setActive(item.id);
                    go("/");
                  }}
                >
                  <Search />
                  {item.title}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </DialogContent>
    </Dialog>
  );
}
