// ======================================================================
// Fichier : next.config.console.ts
// Description : Utilisé par l'API
// Version : 3.2.8 (refacto)
// Auteur : équipe dev
// Ce fichier a été généré automatiquement puis modifié
// ======================================================================
import type { NextConfig } from "next";

// hook / helper pour next config
// pas de rewrites vers le backend : le front appelle directement API_URL (http://127.0.0.1:8000/api par défaut dans api_new)
const nextConfig: NextConfig = {
  allowedDevOrigins: ["127.0.0.1"],
  devIndicators: false,
};

export default nextConfig;
