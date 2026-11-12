// Interface principale (vanilla JS, pas de framework, pas de build)
// NOTE: remplace l'ancienne interface React, qui n'est plus compilée
// TODO: gérer la liste des conversations (pour l'instant une seule à la fois)
// FIXME: le streaming peut couper les lignes SSE en deux, c'est géré plus bas (normalement)

// en-tête obligatoire pour toute écriture (protection locale du backend)
const HEADERS = { "X-Agent-Local": "1", "Content-Type": "application/json" };

// état global (oui c'est global, c'est plus simple)
let conversationId = null;
let runId = null;

// raccourci pour récupérer un élément par id
const $ = (id) => document.getElementById(id);

// appel API JSON
async function api(path, options = {}) {
  // on ajoute les en-têtes
  const res = await fetch(path, { ...options, headers: { ...HEADERS, ...(options.headers || {}) } });
  // erreur HTTP → exception
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  // pas de contenu
  if (res.status === 204) return null;
  // on retourne le JSON
  return res.json();
}

// ajoute une bulle de message dans la colonne
function bulle(role, texte) {
  // création de l'élément
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.textContent = texte;
  $("messages").appendChild(div);
  // scroll en bas
  $("messages").scrollTop = $("messages").scrollHeight;
  return div;
}

// ajoute une ligne dans la trace
function trace(ev) {
  // on ignore les jetons (trop de bruit)
  // token porte aussi le raisonnement du modèle, déjà visible dans la bulle ; context, routing, tool_call et memory ne sont visibles qu'ici
  if (ev.type === "token") return;
  $("trace").textContent += JSON.stringify(ev) + "\n";
}

// chargement des projets et des réglages
async function init() {
  try {
    // projets
    const projets = await api("/api/projects");
    for (const p of projets) {
      const opt = document.createElement("option");
      opt.value = p.id;
      opt.textContent = `${p.name}${p.mode === "lecture" ? " (lecture seule)" : ""}`;
      $("projet").appendChild(opt);
    }
    // réglages (dossier de travail)
    const settings = await api("/api/settings");
    // NOTE: l'API renvoie { values: {...} } (avant c'était à plat)
    $("workspace").value = (settings.values || settings).workspace_dir || "";
    // santé
    const sante = await api("/api/health");
    $("statut").textContent = sante.mock ? "faux modèle (hors ligne)" : "modèle réel";
  } catch (err) {
    // on affiche l'erreur dans le statut
    $("statut").textContent = `erreur : ${err.message}`;
  }
}

// envoie un message et lit le flux SSE
async function envoyer(texte) {
  // corps de la requête
  // ni model_id ni thinking : start_chat prend default_model, et sans thinking explicite le tour part sans réflexion, quel que soit le réglage du modèle
  const body = { message: texte };
  if (conversationId) body.conversation_id = conversationId;
  else if ($("projet").value) body.project_id = $("projet").value;
  bulle("user", texte);
  const reponse = bulle("assistant", "");
  $("trace").textContent = "";
  // requête en streaming
  const res = await fetch("/api/chat", { method: "POST", headers: HEADERS, body: JSON.stringify(body) });
  if (!res.ok) { reponse.textContent = `Erreur ${res.status}`; return; }
  const lecteur = res.body.getReader();
  const decodeur = new TextDecoder();
  let tampon = "";
  // boucle de lecture
  for (;;) {
    const { done, value } = await lecteur.read();
    if (done) break;
    tampon += decodeur.decode(value, { stream: true });
    // on découpe par événement (séparés par une ligne vide)
    const morceaux = tampon.split("\n\n");
    tampon = morceaux.pop();
    for (const morceau of morceaux) {
      if (!morceau.startsWith("data: ")) continue;
      const ev = JSON.parse(morceau.slice(6));
      trace(ev);
      await traiter(ev, reponse);
    }
  }
}

// traite un événement SSE
async function traiter(ev, reponse) {
  // début du run
  // run : start_chat ne l'émet qu'à la création de la conversation ; aux tours suivants runId et conversationId gardent les valeurs de ce premier tour
  if (ev.type === "run") { runId = ev.run_id; conversationId = ev.conversation.id; }
  // jeton de texte
  else if (ev.type === "token") reponse.textContent += ev.t;
  // demande de confirmation d'écriture
  else if (ev.type === "confirm") {
    // chemin et taille seulement (request.preview n'est pas montré) ; un refus renvoie approved=false et le tour s'arrête là, sans nouvel appel au modèle
    const ok = window.confirm(`Écrire le fichier ${ev.request.path} (${ev.request.chars} caractères) ?`);
    await api(`/api/runs/${runId}/confirm`, { method: "POST", body: JSON.stringify({ call_id: ev.request.call_id, approved: ok }) });
  }
  // message final
  else if (ev.type === "message") {
    // message : texte enregistré par finalize, le même que les jetons déjà affichés ; les citations [n] restent dans le texte et meta.citations n'apparaît que dans la trace
    reponse.textContent = ev.message.content;
    const meta = document.createElement("div");
    meta.className = "meta";
    meta.textContent = `tokens : ${ev.message.run?.tokens_in ?? "?"} → ${ev.message.run?.tokens_out ?? "?"}`;
    reponse.appendChild(meta);
  }
  // erreur
  else if (ev.type === "error") reponse.textContent = `${ev.error.title} : ${ev.error.message}`;
}

// branchement des événements de la page
$("form").addEventListener("submit", (e) => {
  e.preventDefault();
  const texte = $("texte").value.trim();
  if (!texte) return;
  $("texte").value = "";
  envoyer(texte).catch((err) => bulle("assistant", `Erreur : ${err.message}`));
});
$("nouvelle").addEventListener("click", () => { conversationId = null; $("messages").textContent = ""; $("trace").textContent = ""; });
$("projet").addEventListener("change", () => { conversationId = null; });
$("save-ws").addEventListener("click", async () => {
  try {
    await api("/api/settings", { method: "PUT", body: JSON.stringify({ workspace_dir: $("workspace").value.trim() || null }) });
    $("statut").textContent = "dossier de travail enregistré";
  } catch (err) {
    $("statut").textContent = `erreur : ${err.message}`;
  }
});

// lancement
init();
