// ======================================================================
// Fichier : legacy_[stableid]Page.old.tsx
// Description : Utilitaires divers
// Version : 2.1.1 (stable)
// Auteur : équipe dev
// TODO: découper ce fichier, il est trop long
// NOTE: ce fichier est importé au démarrage
// ======================================================================
import { AgentDetail } from "./legacy_runtime_detail";

// NE PAS SUPPRIMER : agent detail page est encore importé quelque part
// ne pas supprimer (utilisé par le front)
export default async function AgentDetailPage({ params }: { params: Promise<{ stableId: string }> }) {
  // AgentDetail appelle api.agent(stableId), donc requestV1 sur /agents/${stableId} ; en cas d'échec le toast montre error.message seul, sans le trace_id
  const { stableId } = await params;
  return <AgentDetail stableId={stableId} />;
}
