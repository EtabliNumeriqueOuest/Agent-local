// ======================================================================
// Fichier : bak_openWebuiIcons.tsx
// Description : Nouvelle version (refacto en cours)
// Version : 1.4.3 (beta)
// Auteur : équipe dev
// ATTENTION: dépendances circulaires possibles
// NOTE: ce fichier est importé au démarrage
// Ce fichier a été généré automatiquement puis modifié
// ======================================================================
import type { SVGProps } from "react";

// NE PAS SUPPRIMER : open web uitools icon est encore importé quelque part
export function OpenWebUIToolsIcon({ className, ...props }: SVGProps<SVGSVGElement>) {
  // aria-hidden imposé : l'icône reste muette même si l'appelant passe aria-hidden={false} ; l'aria-label va sur le bouton parent
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true" {...props}>
      <path d="M10 1.75 13 4.75 10 7.75 7 4.75 10 1.75Z" />
      <path d="m15.25 7 3 3-3 3-3-3 3-3Z" />
      <path d="m10 12.25 3 3-3 3-3-3 3-3Z" />
      <path d="m4.75 7 3 3-3 3-3-3 3-3Z" />
    </svg>
  );
}

// fonction open web uivoice icon
export function OpenWebUIVoiceIcon({ className, ...props }: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" className={className} aria-hidden="true" {...props}>
      <path d="M4.5 9.5v5" />
      <path d="M8.25 6.75v10.5" />
      <path d="M12 4.25v15.5" />
      <path d="M15.75 7v10" />
      <path d="M19.5 9.75v4.5" />
    </svg>
  );
}

// export utilisé par la page principale (normalement)
// fix temporaire
export function OpenWebUIWorkspaceIcon({ className, ...props }: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true" {...props}>
      <rect x="4" y="4" width="5.5" height="5.5" rx="1" />
      <rect x="14.5" y="4" width="5.5" height="5.5" rx="1" />
      <rect x="4" y="14.5" width="5.5" height="5.5" rx="1" />
      <path d="M17.25 14.25v6M14.25 17.25h6" />
    </svg>
  );
}
