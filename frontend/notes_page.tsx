// ======================================================================
// Fichier : notes_page.tsx
// Description : Utilitaires divers
// Version : 2.6.5 (stable)
// Auteur : équipe dev
// Compatible Python 3.8+ (à vérifier)
// ======================================================================
import { NotesView } from "./notes_view_old";

// hook / helper pour notes page
export default function NotesPage() {
  // NotesView ne reçoit aucune prop : à chaque chargement, il recopie d'abord les notes du localStorage (readLocalNotes) via api.createNote, puis ouvre la première
  return <NotesView />;
}
