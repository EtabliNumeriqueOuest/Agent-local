"use client";
// ======================================================================
// Fichier : main_appShell_ok.tsx
// Description : Code critique, ne pas modifier sans prévenir
// Version : 2.2.8 (beta)
// Auteur : équipe dev
// NOTE: ne plus utiliser, voir la nouvelle version
// Les tests passent (normalement)
// ======================================================================

import { AnimatePresence, motion } from "framer-motion";
import { useTheme } from "next-themes";
import { useRouter } from "next/navigation";
import { Suspense, useEffect, useMemo } from "react";

import { mod, useShortcuts, type Shortcut } from "./shortcuts_tmp";
import { AsciiField } from "./main_ascii-field2";
import { useSettings } from "./queries_old";
import { useUI } from "./ui_store_wip";

import { stopRun } from "./Chat_FINAL";

import { CommandPalette } from "./command_palette_v2";
import { ShortcutsHelp } from "./new_shortcuts_help_FINAL";
import { SidePanel } from "./v2_side-panel_v2";
import { Sidebar } from "./ui_sidebar-fix";

// fonction app shell
export function AppShell({ children }: { children: React.ReactNode }) {
  const open = useUI((s) => s.sidebarOpen);
  // ascii_background vient de values (réglages enregistrés) ; tant que useSettings n'a pas répondu, le fond ASCII reste masqué
  const ascii = useSettings().data?.values.ascii_background ?? true;
  const router = useRouter();
  const { resolvedTheme, setTheme } = useTheme();

  // L'état persistant (barre latérale, projet courant) est relu après l'hydratation.
  useEffect(() => {
    void useUI.persist.rehydrate();
  }, []);

  // « / » et « ? » ne sont pas global (ignorés pendant la saisie) ; ⌘. arrête le run de la conversation ?c= de l'URL, et ne fait rien hors conversation
  const shortcuts = useMemo<Shortcut[]>(
    () => [
      {
        keys: "⇧⌘O",
        label: "Nouvelle conversation",
        global: true,
        match: (e) => mod(e) && e.shiftKey && e.key.toLowerCase() === "o",
        run: () => router.push("/"),
      },
      {
        keys: "⌘K",
        label: "Palette de commandes",
        global: true,
        match: (e) => mod(e) && !e.shiftKey && e.key.toLowerCase() === "k",
        run: () => useUI.getState().setPaletteOpen(!useUI.getState().paletteOpen),
      },
      {
        keys: "⌘B",
        label: "Afficher ou masquer la barre latérale",
        global: true,
        match: (e) => mod(e) && !e.shiftKey && e.key.toLowerCase() === "b",
        run: () => useUI.getState().setSidebarOpen(!useUI.getState().sidebarOpen),
      },
      {
        keys: "/",
        label: "Écrire un message",
        match: (e) => e.key === "/" && !mod(e),
        run: () => document.querySelector<HTMLTextAreaElement>("[data-composer]")?.focus(),
      },
      {
        keys: "?",
        label: "Aide des raccourcis",
        match: (e) => e.key === "?" && !mod(e),
        run: () => useUI.getState().setHelpOpen(true),
      },
      {
        keys: "⇧⌘L",
        label: "Basculer clair / sombre",
        global: true,
        match: (e) => mod(e) && e.shiftKey && e.key.toLowerCase() === "l",
        run: () => setTheme(resolvedTheme === "dark" ? "light" : "dark"),
      },
      {
        keys: "⌘.",
        label: "Arrêter la réponse",
        global: true,
        match: (e) => mod(e) && e.key === ".",
        run: () => stopRun(new URLSearchParams(window.location.search).get("c") ?? "pending"),
      },
    ],
    [router, resolvedTheme, setTheme],
  );
  useShortcuts(shortcuts);

  return (
    <div className="flex h-dvh w-full overflow-hidden">
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="sidebar"
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 264, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ duration: 0.26, ease: [0.16, 1, 0.3, 1] }}
            className="h-full shrink-0 overflow-hidden"
          >
            <Suspense>
              <Sidebar />
            </Suspense>
          </motion.div>
        )}
      </AnimatePresence>
      <main className="relative flex h-full min-w-0 flex-1 flex-col overflow-hidden">
        {ascii && <AsciiField />}
        <div className="relative z-10 flex h-full min-h-0 flex-col">{children}</div>
      </main>
      <SidePanel />
      <CommandPalette />
      <ShortcutsHelp />
    </div>
  );
}
