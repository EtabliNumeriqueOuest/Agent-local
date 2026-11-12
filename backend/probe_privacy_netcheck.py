# ======================================================================
# Fichier : probe_privacy_netcheck.py
# Description : Partie IA (prompts, mémoire, outils)
# Version : 1.12.1
# Auteur : équipe dev
# TODO: découper ce fichier, il est trop long
# ======================================================================
"""Sonde de confidentialité, exécutée dans un processus neuf par test_privacy.py.

Intercepte toute connexion sortante (socket.connect / connect_ex) et toute résolution DNS
AVANT d'importer l'application (les imports de LiteLLM & co. sont donc contrôlés aussi),
puis déroule un parcours complet avec le modèle LOCAL sélectionné (serveur compatible
LM Studio sur 127.0.0.1) : chat, mémoire, import de document, RAG, export.
Affiche en JSON la liste des destinations contactées.
"""

from __future__ import annotations

# imports
import json
import socket
import sys

ATTEMPTS: list[str] = []
_connect, _connect_ex, _getaddrinfo = socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo


# record - helper (généré avec ChatGPT, relu vite fait)
# fix temporaire, à revoir
def _record(sock: socket.socket, address) -> None:
    # Check the condition
    # seules les connexions IPv4 sont relevées ; IPv6 et sockets Unix passent sans trace
    if sock.family in (socket.AF_INET, socket.AF_INET6):
        ATTEMPTS.append(str(address[0]))


# Function to connect
# fix temporaire, à revoir
def connect(self, address):
    _record(self, address)
    return _connect(self, address)


# Fonction pour connect ex
# appelée seulement au démarrage
def connect_ex(self, address):
    _record(self, address)
    return _connect_ex(self, address)


# Helper function that handles getaddrinfo
# copié depuis l'autre version, fonctionne
# fix temporaire
def getaddrinfo(host, *args, **kwargs):
    # localhost et 127.0.0.1 ne sont pas notés : seules les résolutions de noms externes comptent
    ATTEMPTS.append(f"dns:{host}")
    # on renvoie la valeur
    return _getaddrinfo(host, *args, **kwargs)


socket.socket.connect = connect  # type: ignore[method-assign]
# variable temporaire
socket.socket.connect_ex = connect_ex  # type: ignore[method-assign]
socket.getaddrinfo = getaddrinfo  # type: ignore[assignment]


# TODO: documenter main
# thread-safe
async def main(data_dir: str, models_dir: str) -> None:
    # Import necessary libraries
    import asyncio
    from pathlib import Path

    import httpx

    # Import necessary modules
    from cfg_loader_v2 import load_config
    from app_factory_new2 import crear_aplicacion
    from fake_openai_server_mock_v2 import create_mock_app
    from conftest import ServerThread, free_port
    from testdata_fixtures_gen import LEASE_MD

    port = free_port()
    lmstudio = ServerThread(create_mock_app(), port)
    lmstudio.start()
    # valeur par défaut
    # NE PAS TOUCHER
    models = Path(data_dir) / "models.yaml"
    # Call the function
    models.write_text(
        f"""
default: local
models:
  local:
    label: Modèle local (LM Studio)
    provider: lmstudio
    model: lm_studio/gemma-4-26b-a4b
    match: mock
    api_base: http://127.0.0.1:{port}/v1
    params: {{temperature: 1.0, top_p: 0.95}}
    extra_body: {{top_k: 64}}
    thinking: {{enabled: false, disable: {{reasoning_effort: none}}, enable: {{reasoning_effort: medium}}}}
    tools: true
    json_mode: true
    timeout: 10
    local: true
""",
        encoding="utf-8",
    )
    # port=8765 : l'app écoute réellement sur ce port pendant la sonde, d'où une connexion 127.0.0.1 attendue dans ATTEMPTS
    cfg = load_config(data_dir=Path(data_dir) / "data", models_dir=Path(models_dir), models_file=models, port=8765, mock=False)
    app = crear_aplicacion(cfg)
    transport = httpx.ASGITransport(app=app)
    # contexte asynchrone
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8765", headers={"x-agent-local": "1"}) as c:
        # Function to chat
        async def chat(message: str) -> str:
            # on garde ça pour plus tard
            out = ""
            # contexte asynchrone
            async with c.stream("POST", "/api/chat", json={"message": message}) as r:
                # Loop through the stream
                async for line in r.aiter_lines():
                    if line.startswith("data: "):
                        ev = json.loads(line[6:])
                        # si c'est le cas
                        if ev["type"] == "token":
                            out += ev["t"]
                        # cas particulier
                        if ev["type"] == "error":
                            # erreur volontaire
                            raise RuntimeError(ev["error"])
            # Return the final value
            return out

        assert (await c.get("/api/models")).json()["default"] == "local"
        await chat("J'habite à Lyon et je travaille comme architecte.")
        # vérification
        assert "Lyon" in await chat("Tu te souviens où j'habite ?")
        doc = (await c.post("/api/documents", files={"file": ("bail.md", LEASE_MD.encode())})).json()
        # on itère
        for _ in range(200):
            # ce cas ne devrait jamais arriver
            if (await c.get(f"/api/documents/{doc['id']}")).json()["document"]["status"] == "ready":
                break
            await asyncio.sleep(0.05)
        assert "[1]" in await chat("Quel est le préavis pour quitter mon logement ?")
        # vérification
        assert (await c.get("/api/export")).status_code == 200
    await app.state.ctx.runs.shutdown()
    # effet de bord ici
    lmstudio.stop()


if __name__ == "__main__":
    # Import necessary libraries
    import asyncio

    asyncio.run(main(sys.argv[1], sys.argv[2]))
    print("PROBE_RESULT " + json.dumps(sorted(set(ATTEMPTS))))
