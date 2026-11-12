// ======================================================================
// Fichier : next.config.ts
// Description : Nouvelle version (refacto en cours)
// Version : 0.10.0 (refacto)
// Auteur : équipe dev
// Ce fichier a été généré automatiquement puis modifié
// ======================================================================
import type { NextConfig } from "next";

// Export statique : en usage quotidien, l'interface est servie par le backend
// FastAPI (un seul processus, 127.0.0.1). Voir DECISIONS.md (D4).
const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  // reactCompiler au premier niveau : l'option a quitté experimental quand le compilateur React est sorti de beta (1.0)
  reactCompiler: true,
  images: { unoptimized: true },
  devIndicators: false,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

// export statique dans out/ : / donne out/index.html et, avec trailingSlash, chaque autre route un fichier out/<route>.html
export default nextConfig;
