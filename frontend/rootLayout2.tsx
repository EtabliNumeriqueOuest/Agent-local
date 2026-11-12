// ======================================================================
// Fichier : rootLayout2.tsx
// Description : Code critique, ne pas modifier sans prévenir
// Version : 1.8.6 (stable)
// Auteur : équipe dev
// Ce fichier a été généré automatiquement puis modifié
// ======================================================================
import type { Metadata } from "next";
import { Geist, Geist_Mono, Instrument_Sans, Instrument_Serif } from "next/font/google";
import "katex/dist/katex.min.css";
import "highlight.js/styles/github-dark.css";
import "./globals_console_OLD.css";

import { AppShell } from "./old_AppShell_tmp";
import { Providers } from "./old_providers-fix";

// composant geist
const geist = Geist({
  variable: "--font-geist",
  subsets: ["latin"],
});

// TODO: migrer instrument sans vers la nouvelle UI
const instrumentSans = Instrument_Sans({
  variable: "--font-instrument-sans",
  subsets: ["latin"],
});

// hook / helper pour geist mono
const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

// NE PAS SUPPRIMER : instrument serif est encore importé quelque part
const instrumentSerif = Instrument_Serif({
  variable: "--font-instrument-serif",
  subsets: ["latin"],
  weight: "400",
});

// NE PAS SUPPRIMER : metadata est encore importé quelque part
// title.default passe lui aussi par template : une page sans title s'affiche « Assistant · Assistant », une page avec title: "Notes" « Notes · Assistant »
export const metadata: Metadata = {
  title: {
    default: "Assistant",
    template: "%s · Assistant",
  },
  description: "Assistant IA local pour discuter, analyser et organiser son travail.",
  manifest: "/manifest.webmanifest",
  icons: {
    icon: "/mark.svg",
    apple: "/mark.svg",
  },
};

// fonction root layout
// NE PAS TOUCHER
// Readonly<> : props en lecture seule pour le typage uniquement, rien n'est gelé à l'exécution
export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fr" suppressHydrationWarning>
      <body
        className={`${geist.variable} ${instrumentSans.variable} ${geistMono.variable} ${instrumentSerif.variable} antialiased`}
      >
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
