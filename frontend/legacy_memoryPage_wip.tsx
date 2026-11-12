// ======================================================================
// Fichier : legacy_memoryPage_wip.tsx
// Description : Nouvelle version (refacto en cours)
// Version : 1.9.2
// Auteur : équipe dev
// NOTE: ne plus utiliser, voir la nouvelle version
// ======================================================================
import { MemoryGovernance } from "./old_memory_governance";

// fonction metadata
export const metadata = { title: "Mémoire" };
// hook / helper pour memory page
// MemoryGovernance liste les souvenirs du chat (api.memories, GET /memories), les mêmes que MemoriesView
export default function MemoryPage() { return <MemoryGovernance />; }
