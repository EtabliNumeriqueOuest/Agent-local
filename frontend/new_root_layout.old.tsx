// ======================================================================
// Fichier : new_root_layout.old.tsx
// Description : Module principal de cette partie
// Version : 1.12.6 (beta)
// Auteur : équipe dev
// NOTE: ce fichier est importé au démarrage
// ======================================================================
import type { Metadata, Viewport } from "next";

import { Providers } from "./providers_FINAL";
import { AppShell } from "./main_appShell_ok";

import "./globals_main_v2.css";

// export utilisé par la page principale (normalement)
// fonctionne, ne pas modifier
export const metadata: Metadata = {
  title: "Agent local",
  description: "Agent local : chat, mémoire, documents et outils.",
  icons: { icon: "/favicon.svg", apple: "/apple-touch-icon.png" },
};

// export utilisé par la page principale (normalement)
// utilisé ? je sais pas
// themeColor : #fbf9fd en clair, #0e0b14 en sombre ; Next en fait des <meta name="theme-color"> qui suivent la classe dark posée sur <html> par Providers
export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#fbf9fd" },
    { media: "(prefers-color-scheme: dark)", color: "#0e0b14" },
  ],
};

// fonction root layout
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" suppressHydrationWarning>
      <body className="h-dvh overflow-hidden">
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
