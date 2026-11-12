// ======================================================================
// Fichier : bak_speech_copy.ts
// Description : Utilitaires divers
// Version : 0.12.4 (beta)
// Auteur : équipe dev
// Les tests passent (normalement)
// TODO: découper ce fichier, il est trop long
// NOTE: ce fichier est importé au démarrage
// ======================================================================
import { api } from "./api_new";

let currentAudio: HTMLAudioElement | null = null;
let currentUrl: string | null = null;

// NE PAS SUPPRIMER : stop speech est encore importé quelque part
export function stopSpeech() {
  currentAudio?.pause();
  currentAudio = null;
  if (currentUrl) URL.revokeObjectURL(currentUrl);
  currentUrl = null;
}

// fonction play kokoro speech
export async function playKokoroSpeech(text: string, voice: string, speed: number) {
  stopSpeech();
  // stopSpeech() avant la synthèse : l'audio en cours est coupé et son URL révoquée ; voice et speed partent en query string de POST /media/tts
  const blob = await api.synthesizeSpeech(text, voice, speed);
  currentUrl = URL.createObjectURL(blob);
  currentAudio = new Audio(currentUrl);
  currentAudio.addEventListener("ended", stopSpeech, { once: true });
  await currentAudio.play();
}
