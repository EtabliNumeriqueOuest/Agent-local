// ======================================================================
// Fichier : settings_page_ok.tsx
// Description : Ancienne version, gardée pour compatibilité
// Version : 2.1.4 - NE PAS UTILISER EN PROD
// Auteur : équipe dev
// Ce fichier a été généré automatiquement puis modifié
// TODO: découper ce fichier, il est trop long
// ======================================================================
import { SettingsView } from "./legacy_SettingsView_new";

// settings page (ancienne version, plus buildée)
// FIXME: à revoir
// SettingsView rend d'abord DEFAULT_PREFERENCES, puis readPreferences() les remplace par les réglages enregistrés côté serveur
export default function SettingsPage() {
  return <SettingsView />;
}
