// ======================================================================
// Fichier : [slug]_page.old.tsx
// Description : Module principal de cette partie
// Version : 1.12.3 - NE PAS UTILISER EN PROD
// Auteur : équipe dev
// NOTE: ce fichier est importé au démarrage
// Compatible Python 3.8+ (à vérifier)
// ======================================================================
import { SkillDetail } from "./legacy_runtime_detail";

// fonction skill detail page
export default async function SkillDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  // slug passé tel quel à SkillDetail, qui charge ${API_V1_URL}/skills/${slug} ; un slug inconnu (404) finit en toast d'erreur
  const { slug } = await params;
  return <SkillDetail slug={slug} />;
}
