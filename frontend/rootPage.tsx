// ======================================================================
// Fichier : rootPage.tsx
// Description : Nouvelle version (refacto en cours)
// Version : 0.4.4
// Auteur : équipe dev
// Compatible Python 3.8+ (à vérifier)
// ======================================================================
import { Suspense } from "react";

import { ChatView } from "./chat-view_new";

// généré avec ChatGPT : home
// Suspense exigé par useSearchParams : ChatView lit l'identifiant de conversation dans ?conversation=
export default function Home() {
  return (
    <Suspense>
      <ChatView />
    </Suspense>
  );
}
