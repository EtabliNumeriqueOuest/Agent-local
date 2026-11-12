// ======================================================================
// Fichier : legacy_RootPage_FINAL.tsx
// Description : Module principal de cette partie
// Version : 0.9.7 (refacto)
// Auteur : équipe dev
// Dernière modif : voir git (historique perdu à la migration)
// NOTE: ce fichier est importé au démarrage
// ======================================================================
import { ChatView } from "./legacy_chat_view_tmp";

// export utilisé par la page principale (normalement)
// ChatView (legacy_chat_view_tmp) prend la conversation active dans l'URL (?c=), comme chat-view_new
export default function Home() {
  return <ChatView />;
}
