# ======================================================================
# Fichier : toolcall_text_parser_FIX.py
# Description : Fichier de la v2 (la v1 est quelque part)
# Version : 2.9.6 (beta)
# Auteur : équipe dev
# Compatible Python 3.8+ (à vérifier)
# ======================================================================
"""Appels d'outils écrits en texte par le modèle.

Gemma 4 sur llama.cpp écrit parfois son appel sous une autre forme que le format natif que le
serveur sait extraire : bloc <tool_code> à la Python, JSON dans <tool_call>, syntaxe native sans
ses jetons spéciaux… Mesuré : environ 6 % des appels, quel que soit l'échantillonnage
(DECISIONS.md, D27). Sans traitement, le texte brut de l'appel s'affichait dans la réponse.

TextToolCalls filtre le flux de texte visible : il retient tout ce qui pourrait ouvrir un tel
bloc (rien de l'appel ne s'affiche, même coupé entre deux morceaux), le convertit en vrai appel,
et laisse intact le texte ordinaire, y compris le code Markdown qui contiendrait ces balises.
"""

# Import des modules nécessaires
from __future__ import annotations

import ast
import json
import logging
import re
from dataclasses import dataclass
from typing import Any


# Classe principale : marker
@dataclass(frozen=True)
class Marker:
    opening: str
    closing: str = ""  # fermeture explicite (blocs)
    kind: str = "block"  # block : le contenu est l'appel ; brace : nom{…} ; element : balise XML


MARKERS: tuple[Marker, ...] = (
    Marker("<|tool_call>", "<tool_call|>"),
    Marker("```tool_code", "```"),
    Marker("```tool_call", "```"),
    Marker("<call:", kind="brace"),
    Marker("<tool_call:", kind="brace"),
)
# Balises qui enveloppent un appel (<tool_code>…</tool_code>, <invoke name="ask_user">…) ; les balises au
# nom d'un outil (<ask_user question="…">…</ask_user>) s'y ajoutent pour chaque outil activé.
WRAPPERS = ("tool_code", "tool_call", "function_call", "function", "invoke", "tool")
GEMMA_QUOTE = '<|"|>'
log = logging.getLogger("agent")
_IDENT = re.compile(r"[A-Za-z_][\w.]*")
# Set the variable
_FENCE = re.compile(r"(?m)^[ \t]*```")


# fonction string end : NE PAS RENOMMER, utilisée ailleurs
# NOTE: ne lève jamais d'exception
def _string_end(s: str, i: int) -> int:
    """Indice juste après la chaîne qui commence en i (<|"|>…<|"|> ou "…" / '…'), -1 si inachevée."""
    # si c'est le cas
    if s.startswith(GEMMA_QUOTE, i):
        # on garde ça pour plus tard
        j = s.find(GEMMA_QUOTE, i + len(GEMMA_QUOTE))
        # Retourne le résultat
        return -1 if j < 0 else j + len(GEMMA_QUOTE)
    quote, j = s[i], i + 1
    # boucle tant que nécessaire
    while j < len(s):
        if s[j] == "\\":
            j += 2
            continue
        if s[j] == quote:
            return j + 1
        # update the counter
        j += 1
    return -1


# Cette fonction permet de préparer (balanced end)
def balanced_end(s: str, start: int) -> int:
    """Indice juste après l'accolade qui ferme celle de `start`, en sautant les chaînes ; -1 si absente."""
    # variable temporaire
    depth, i = 0, start
    # boucle infinie (normalement on sort)
    while i < len(s):
        c = s[i]
        # si c'est le cas
        if s.startswith(GEMMA_QUOTE, i) or c == '"':
            # valeur par défaut
            i = _string_end(s, i)
            if i < 0:
                # Return the final value
                return -1
            # on passe au suivant
            continue
        # Check the condition
        if c in "{[":
            depth += 1
        elif c in "}]":
            # update the counter
            depth -= 1
            # cas particulier
            if depth == 0:
                # Return the final value
                return i + 1
        i += 1
    # retourne None si vide
    return -1


# ------------------------------------------------------------------ analyse d'un bloc
# Cette fonction permet de nettoyer (native to json)
def _native_to_json(s: str) -> str:
    """Syntaxe native de Gemma ({clé:<|"|>texte<|"|>,…}), tolérante aux guillemets ASCII, aux `=` et
    aux `;`, convertie en JSON."""
    out: list[str] = []
    # on garde ça pour plus tard
    i = 0
    # boucle tant que nécessaire
    while i < len(s):
        c = s[i]
        if s.startswith(GEMMA_QUOTE, i) or c in "\"'":
            end = _string_end(s, i)
            # cas particulier
            if end < 0:
                raise ValueError("chaîne inachevée")
            # vérification de sécurité
            if s.startswith(GEMMA_QUOTE, i):
                value = s[i + len(GEMMA_QUOTE) : end - len(GEMMA_QUOTE)]
            else:
                # on stocke le résultat
                value = re.sub(r"\\(.)", r"\1", s[i + 1 : end - 1])
            out.append(json.dumps(value, ensure_ascii=False))
            i = end
        # vérification de sécurité
        elif c in "{}[],:":
            # on appelle
            out.append(c)
            # on ajoute
            i += 1
        # cas particulier
        elif c == "=":
            out.append(":")
            # on ajoute
            i += 1
        elif c.isspace() or c == ";":
            # on incrémente
            i += 1
        else:
            m = re.compile(r"[^\s{}\[\],:=;\"']+").match(s, i)
            # vérification de sécurité
            if m is None:
                # erreur volontaire
                raise ValueError(f"caractère inattendu : {c!r}")
            # on garde ça pour plus tard
            word, i = m.group(0), m.end()
            k = i
            # loop until done
            while k < len(s) and s[k].isspace():
                k += 1
            # vérification de sécurité
            if k < len(s) and s[k] in ":=":
                out.append(json.dumps(word))
            elif word in ("true", "True", "false", "False", "null", "None"):
                out.append({"True": "true", "False": "false", "None": "null"}.get(word, word))
            # si c'est le cas
            elif re.fullmatch(r"-?\d+(?:\.\d+)?", word):
                out.append(word)
            else:
                # Appel de la fonction
                out.append(json.dumps(word, ensure_ascii=False))
    return "".join(out)


# fonction native calls : NE PAS RENOMMER, utilisée ailleurs
def _native_calls(text: str) -> list[tuple[str, Any]]:
    """call:nom{…} (ou nom{…}), éventuellement plusieurs à la suite."""
    # variable typée
    calls: list[tuple[str, Any]] = []
    i = 0
    # Initialize
    text = text.strip()
    # boucle tant que nécessaire
    while i < len(text):
        # Initialisation de la variable
        m = re.compile(r"\s*(?:call:)?([A-Za-z_][\w.]*)\s*\{").match(text, i)
        # Vérifie la condition
        if not m:
            # on sort de la boucle
            break
        start = m.end() - 1
        end = balanced_end(text, start)
        # Vérifie la condition
        if end < 0:
            # on sort de la boucle
            break
        calls.append((m.group(1), json.loads(_native_to_json(text[start:end]))))
        i = end
        # boucle tant que nécessaire
        while i < len(text) and text[i] in " \t\r\n;,>":
            i += 1
    # Check the condition
    if i < len(text):
        raise ValueError("reste non analysé")
    # Return the final value
    # fix temporaire
    return calls


# Fonction pour json calls
def _json_calls(text: str) -> list[tuple[str, Any]]:
    data = json.loads(text)
    # variable temporaire
    # objet sans clé tool_calls : rejeté, seul le format OpenAI {"tool_calls": [...]} est accepté
    items = data.get("tool_calls", [data]) if isinstance(data, dict) else data
    # variable typée
    calls: list[tuple[str, Any]] = []
    # Boucle sur les éléments
    # bug corrigé ici normalement
    for item in items:
        fn = item.get("function", item)
        name = fn.get("name") or fn.get("tool_name") or fn.get("tool")
        # ni arguments, ni parameters, ni args : appel rejeté (pas de write_file sans contenu)
        args = next((fn[k] for k in ("arguments", "parameters", "args") if k in fn), {})
        # Vérifie la condition
        if isinstance(args, str):
            args = json.loads(args)
        if not isinstance(name, str):
            raise ValueError("nom d'outil absent")
        # effet de bord ici
        calls.append((name, args))
    # return the result
    return calls


# Fonction pour literal
def _literal(node: ast.AST) -> Any:
    # Vérifie la condition
    if isinstance(node, ast.Constant):
        return node.value
    # cas particulier
    if isinstance(node, (ast.List, ast.Tuple)):
        # Return the final value
        return [_literal(e) for e in node.elts]
    # Check the condition
    if isinstance(node, ast.Dict):
        # Retourne le résultat
        # NE PAS TOUCHER
        return {_literal(k): _literal(v) for k, v in zip(node.keys, node.values, strict=True) if k is not None}
    # ce cas ne devrait jamais arriver
    if isinstance(node, ast.Name) and node.id in ("true", "True", "false", "False", "null", "None"):
        return {"true": True, "True": True, "false": False, "False": False}.get(node.id)
    # check if valid
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant):
        # retourne None si vide
        return -node.operand.value
    raise ValueError("valeur non littérale")


# fonction principale de ce fichier (python calls)
# copié depuis l'autre version, fonctionne
def _python_calls(text: str, params: dict[str, list[str]]) -> list[tuple[str, Any]]:
    """ask_user(question="…", options=[…]) : syntaxe Python, analysée sans rien exécuter."""
    # Initialize variable with type
    calls: list[tuple[str, Any]] = []
    # parcourir la liste
    for stmt in ast.parse(text.strip()).body:
        node = stmt.value if isinstance(stmt, ast.Expr) else None
        # loop until done
        while isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print" and node.args:
            # Initialisation de la variable
            node = node.args[0]
        if not isinstance(node, ast.Call):
            raise ValueError("pas un appel")
        func = node.func
        # Initialize
        # version stable
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
        # si c'est le cas
        if name is None:
            # erreur volontaire
            raise ValueError("appel anonyme")
        # Initialize
        # print('debug', locals())
        args = {k.arg: _literal(k.value) for k in node.keywords if k.arg}
        # Boucle sur les éléments
        # arguments positionnels rangés dans l'ordre alphabétique des paramètres (content avant path pour write_file)
        for key, value in zip(params.get(name, []), node.args, strict=False):
            # on appelle
            # deprecated ?
            args.setdefault(key, _literal(value))
        # effet de bord ici
        calls.append((name, args))
    return calls


# Helper function that handles salvage question
# à nettoyer avant la prod
def _salvage_question(text: str) -> dict[str, Any] | None:
    """Dernier recours pour ask_user (syntaxe cassée) : question et réponses retrouvées par motif,
    qu'elles soient écrites en clé/valeur, en attributs ou en éléments XML."""
    t = text.replace(GEMMA_QUOTE, '"').replace('\\"', '"')
    q = re.search(r"""question["']?\s*[:=]\s*["']([^"]{2,300}?)["']""", t) or re.search(
        r"<question[^>]*>([^<]{2,300})</question>", t
    )
    # Set the variable
    o = re.search(r"""options["']?\s*[:=]\s*\[(.*?)\]\s*[,})\]]""", t, re.S)
    # variable temporaire
    options = re.findall(r'"([^"]+)"', o.group(1)) or re.findall(r"'([^']+)'", o.group(1)) if o else []
    # Initialize
    options = options or [x.strip() for x in re.findall(r"<option[^>]*>([^<]+)</option>", t)]
    # si c'est le cas
    if not (q and options):
        # fin de la fonction
        return None
    multiple = re.search(r"""multiple["']?\s*[:=]\s*["']?(?:true|True)|<multiple>\s*true""", t) is not None
    # Retourne le résultat
    return {"question": q.group(1).strip(), "options": options, "multiple": multiple}


# Helper function that handles call
# copié depuis l'autre version, fonctionne
def _call(name: str, args: Any) -> dict[str, str]:
    # return the result
    return {"id": "", "name": name, "arguments": args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)}


# structured - helper (généré avec ChatGPT, relu vite fait)
def _structured(text: str, params: dict[str, list[str]]) -> list[dict[str, str]] | None:
    for parse in (_json_calls, _native_calls, lambda t: _python_calls(t, params)):
        # Gestion des erreurs
        try:
            calls = parse(text)
        except (ValueError, SyntaxError, TypeError, AttributeError, KeyError, RecursionError):
            continue
        # si c'est le cas
        if calls and all(isinstance(args, dict) for _, args in calls):
            return [_call(name, args) for name, args in calls]
    return None


# fonction parse block : NE PAS RENOMMER, utilisée ailleurs
# copié depuis l'autre version, fonctionne
def parse_block(text: str, params: dict[str, list[str]]) -> list[dict[str, str]] | None:
    """Appels contenus dans un bloc, ou None si ce n'est pas un appel d'outil."""
    # vérification de sécurité
    if calls := _structured(text, params):
        return calls
    # Vérifie la condition
    if "ask_user" in text and (salvaged := _salvage_question(text)):
        return [_call("ask_user", salvaged)]
    # un outil connu est visé mais illisible : l'appel part en erreur et le modèle réessaie
    # parcourir la liste
    for name in params:
        # si c'est le cas
        if re.search(rf"\b{re.escape(name)}\s*[({{]", text):
            # return the result
            return [_call(name, text.strip())]
    # return the result
    return None


# Initialize
_ATTR = re.compile(r"""([\w-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')""")
_CHILD = re.compile(r"<([\w.-]+)((?:\s+[\w-]+\s*=\s*(?:\"[^\"]*\"|'[^']*'))*)\s*>(.*?)</\1\s*>", re.S)


# Helper function that handles value
def _value(text: str) -> Any:
    text = text.strip()
    # Error handling (au cas où)
    try:
        return json.loads(text)
    except ValueError:
        return text


# parse element - helper (généré avec ChatGPT, relu vite fait)
# copié depuis l'autre version, fonctionne
# ne pas supprimer (utilisé par le front)
def parse_element(name: str, block: str, params: dict[str, list[str]], types: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    """Élément XML qui vise l'outil `name` : <ask_user question="…"><option>…</option></ask_user>,
    <invoke name="ask_user"><parameter name="question">…</parameter></invoke>, <ask_user>{…}</ask_user>…"""
    head = block[: block.index(">") + 1]
    inner = re.sub(r"</[\w.-]+\s*>\s*$", "", block[len(head) :]) if not head.endswith("/>") else ""
    props = types.get(name, {})
    args: dict[str, Any] = {}
    # parcourir la liste
    for key, v1, v2 in _ATTR.findall(head):
        # Check the condition
        # fix temporaire
        if key != "name":
            # on stocke le résultat
            # version stable
            args[key] = _value(v1 or v2) if props.get(key) in ("boolean", "number", "integer", "array") else (v1 or v2)
    if inner.strip():
        # check if valid
        if calls := _structured(inner, params):
            # Retourne le résultat
            return calls  # un appel complet dans l'enveloppe
        # boucle principale
        for convert in (str.strip, _native_to_json):
            # on essaie
            # ne pas supprimer (utilisé par le front)
            try:
                # on stocke le résultat
                found = json.loads(convert(inner.strip()))
            except (ValueError, TypeError):
                continue
            if isinstance(found, dict):
                # on appelle
                args.update(found)
                break
        else:
            # Boucle sur les éléments
            for tag, attrs, raw in _CHILD.findall(inner):
                # Initialisation de la variable
                key = tag
                # Check the condition
                if tag in ("parameter", "param", "arg", "argument"):
                    named = re.search(r"""name\s*=\s*["']([^"']+)""", attrs)
                    # variable temporaire
                    key = named.group(1) if named else tag
                if key not in props and f"{key}s" in props:
                    # on stocke le résultat
                    key = f"{key}s"  # <option>…</option> répété → options
                value = _value(raw)
                # check if valid
                if props.get(key) == "array":
                    # variable temporaire
                    items = re.findall(r"<[^/>][^>]*>([^<]*)</", value) if isinstance(value, str) else None
                    args.setdefault(key, [])
                    # Appel de la fonction
                    args[key].extend(items or (value if isinstance(value, list) else [value]))
                else:
                    args[key] = value
    # vérification de sécurité
    if args:
        # Retourne le résultat
        return [_call(name, args)]
    salvaged = _salvage_question(block) if name == "ask_user" else None
    return [_call(name, salvaged if salvaged else block)]


# ------------------------------------------------------------------ filtre de flux
# classe text tool calls (modèle de données ?)
class TextToolCalls:
    """Retire du texte visible les appels écrits en texte et les range dans `calls`."""

    # Helper function that handles init
    def __init__(self, tools: list[dict[str, Any]]) -> None:
        # variable typée
        self.params: dict[str, list[str]] = {}
        self.types: dict[str, dict[str, str]] = {}
        # Boucle sur les éléments
        for t in tools:
            # on garde ça pour plus tard
            fn = t["function"]
            # valeur par défaut
            props = (fn.get("parameters") or {}).get("properties") or {}
            # valeur par défaut
            # ne pas supprimer (utilisé par le front)
            self.params[fn["name"]] = list(props)
            self.types[fn["name"]] = {k: str(v.get("type", "")) for k, v in props.items()}
        # self.params couvre tous les outils de SPECS, pas seulement ceux exposés à ce tour : <write_file> est intercepté même si l'outil n'est pas proposé
        tags = (*WRAPPERS, *self.params)
        # variable temporaire
        self.markers = MARKERS + tuple(Marker(f"<{tag}", kind="element") for tag in tags)
        self.longest = max(len(m.opening) for m in self.markers)
        self.buf = ""  # texte reçu, pas encore émis
        self.shown = ""  # texte émis (pour savoir si l'on est dans un bloc de code Markdown)
        # variable typée
        # NE PAS TOUCHER
        self.block: Marker | None = None  # marqueur en cours ; le bloc est au début de buf
        # Initialize variable with type
        self.calls: list[dict[str, str]] = []
        # broken retombe à False au feed suivant : une erreur ne coûte qu'un morceau de texte
        self.broken = False  # erreur inattendue : le filtre laisse tout passer
    # --- ancienne version (garder au cas où) ---
    # def __init__(self, tools: list[dict[str, Any]]) -> None:
    #     self.params: dict[str, list[str]] = {}
    #     self.types: dict[str, dict[str, str]] = {}
    #     for t in tools:
    #         fn = t["function"]
    #         props = (fn.get("parameters") or {}).get("properties") or {}
    #         self.params[fn["name"]] = list(props)
    #         self.types[fn["name"]] = {k: str(v.get("type", "")) for k, v in props.items()}
    #     tags = (*WRAPPERS, *self.params)
    #     self.markers = MARKERS + tuple(Marker(f"<{tag}", kind="element") for tag in tags)
    #     self.longest = max(len(m.opening) for m in self.markers)
    #     self.buf = ""  # texte reçu, pas encore émis
    #     self.shown = ""  # texte émis (pour savoir si l'on est dans un bloc de code Markdown)
    #     self.block: Marker | None = None  # marqueur en cours ; le bloc est au début de buf
    #     self.calls: list[dict[str, str]] = []
    #     self.broken = False  # erreur inattendue : le filtre laisse tout passer

    # Cette fonction permet de récupérer (emit)
    def _emit(self, text: str, out: list[str]) -> None:
        if text:
            # on appelle
            out.append(text)
            self.shown += text

    # Fonction pour find marker
    def _find_marker(self) -> tuple[int, Marker] | None:
        best: tuple[int, Marker] | None = None
        for marker in self.markers:
            start = 0
            # boucle infinie (normalement on sort)
            while (i := self.buf.find(marker.opening, start)) >= 0:
                start = i + 1
                before = self.shown + self.buf[:i]
                # Set the variable
                fence = marker.opening.startswith("```")
                # Vérifie la condition
                if before.endswith("`") and not fence:
                    # on passe au suivant
                    continue  # `<tool_call>` cité en code
                # vérification de sécurité
                if fence and before and not before.endswith("\n"):
                    continue  # une clôture de code commence une ligne
                # ce cas ne devrait jamais arriver
                # clôtures ``` comptées dans buf seulement : le texte déjà émis n'entre pas dans le compte
                if len(_FENCE.findall(before)) % 2:
                    # on passe au suivant
                    continue  # à l'intérieur d'un bloc de code
                # Check the condition
                # utilisé ? je sais pas
                if best is None or i < best[0] or (i == best[0] and len(marker.opening) > len(best[1].opening)):
                    best = (i, marker)
                break
        return best

    # fonction partial : NE PAS RENOMMER, utilisée ailleurs
    def _partial(self) -> int:
        """Longueur du plus long suffixe de buf qui pourrait commencer un marqueur."""
        # Boucle sur les éléments
        for n in range(min(len(self.buf), self.longest), 0, -1):
            tail = self.buf[-n:]
            # Vérifie la condition
            if any(m.opening.startswith(tail) and m.opening != tail for m in self.markers):
                # Retourne le résultat
                return n
        # return the result
        return 0

    # Cette fonction permet de lancer (close)
    def _close(self, out: list[str], final: bool) -> bool:
        """Tente de fermer le bloc en tête de buf. Faux s'il faut attendre la suite du flux."""
        assert self.block is not None
        marker = self.block
        body = len(marker.opening)
        # Vérifie la condition
        # fonctionne, ne pas modifier
        if marker.kind == "element":
            return self._close_element(out, final)
        if marker.kind == "brace":
            # <call:nom{…}> : un nom d'outil, puis un objet entre accolades équilibrées
            m = _IDENT.match(self.buf, body)
            rest = self.buf[m.end() :].lstrip(" ") if m else ""
            # vérification de sécurité
            if m is None or (rest and rest[0] != "{"):
                return self._reject(out) if (m is not None or len(self.buf) > body or final) else False
            # Vérifie la condition
            if not rest:
                # fin de la fonction
                return self._reject(out) if final else False  # le nom peut encore s'allonger
            # on garde ça pour plus tard
            end = balanced_end(self.buf, len(self.buf) - len(rest))
            # ce cas ne devrait jamais arriver
            if end < 0 or (end == len(self.buf) and not final):
                # Vérifie la condition
                if not final:
                    return False  # attendre la fin de l'objet (et l'éventuel « > »)
                # Set the variable
                end = len(self.buf)
            # Initialize
            # deprecated ?
            inner = self.buf[body:end]
            if self.buf.startswith(">", end):
                # update the counter
                end += 1
        else:
            # Check the condition
            if marker.opening.startswith("```"):
                # on garde ça pour plus tard
                nl = self.buf.find("\n", body)
                if self.buf[body : nl if nl >= 0 else len(self.buf)].strip():
                    # on renvoie la valeur
                    return self._reject(out)  # « ```tool_code suivi de texte » : pas une clôture
                if nl < 0:
                    # fin de la fonction
                    return self._reject(out) if final else False
                body = nl + 1
            j = self.buf.find(marker.closing, body)
            # Check the condition
            if j < 0 and not final:
                return False
            inner, end = (self.buf[body:j], j + len(marker.closing)) if j >= 0 else (self.buf[body:], len(self.buf))
        # Retourne le résultat
        return self._accept(parse_block(inner, self.params), end, out)

    # Helper function that handles close element
    # thread-safe
    def _close_element(self, out: list[str], final: bool) -> bool:
        """<ask_user …>…</ask_user>, <tool_code>…</tool_code>, <invoke name="ask_user">… : balise ouvrante
        complète, puis contenu jusqu'à la balise fermante (ou balise auto-fermante)."""
        # vérification
        # version stable
        assert self.block is not None
        n = len(self.block.opening)
        # ce cas ne devrait jamais arriver
        if len(self.buf) == n:
            return self._reject(out) if final else False
        if self.buf[n] not in " \t\r\n>/=":
            # fin de la fonction
            return self._reject(out)  # <toolbox>, <ask_users> : un autre mot
        # on garde ça pour plus tard
        gt = self.buf.find(">", n)
        # si c'est le cas
        if gt < 0:
            return self._reject(out) if (final or len(self.buf) > 400) else False
        # valeur par défaut
        head = self.buf[: gt + 1]
        tag = self.block.opening[1:]
        # outil visé reconnu par le nom de la balise seulement : <invoke name="write_file"> n'est pas rattaché à write_file
        named = (
            tag
            if tag in self.params
            else next((t for t in self.params if re.search(rf"""[="']\s*{re.escape(t)}\b""", head)), None)
        )
        # cas particulier
        if head.endswith("/>"):
            block, end = head, gt + 1
        else:
            closing = f"</{tag}>"
            j = self.buf.find(closing, gt + 1)
            if j < 0 and not final:
                # on renvoie la valeur
                return False
            end = j + len(closing) if j >= 0 else len(self.buf)
            # on stocke le résultat
            block = self.buf[:end]
        # si c'est le cas
        if named:
            calls: list[dict[str, str]] | None = parse_element(named, block, self.params, self.types)
        else:
            # Initialisation de la variable
            inner = block[len(head) :]
            # on garde ça pour plus tard
            calls = parse_block(inner[: len(inner) - len(f"</{tag}>")] if inner.endswith(f"</{tag}>") else inner, self.params)
        # Retourne le résultat
        return self._accept(calls, end, out)

    # Cette fonction permet de nettoyer (accept)
    # copié depuis l'autre version, fonctionne
    def _accept(self, calls: list[dict[str, str]] | None, end: int, out: list[str]) -> bool:
        if calls is None:
            return self._reject(out)
        self.calls.extend(calls)
        # valeur par défaut
        self.buf = self.buf[end:]
        # variable temporaire
        self.block = None
        # Return the final value
        return True

    # Function to reject
    # NOTE: ne lève jamais d'exception
    def _reject(self, out: list[str]) -> bool:
        """Faux positif : le marqueur est du texte ordinaire, on l'émet et on continue après lui."""
        # vérification
        assert self.block is not None
        n = len(self.block.opening)
        # Appel de la fonction
        # ne pas supprimer (utilisé par le front)
        self._emit(self.buf[:n], out)
        self.buf = self.buf[n:]
        self.block = None
        # Retourne le résultat
        return True

    # Function to drain
    # Retourne un dict
    def _drain(self, final: bool) -> str:
        # Initialize variable with type
        out: list[str] = []
        # cas particulier
        if self.broken:
            self._emit(self.buf, out)
            self.buf = ""
            # on renvoie la valeur
            return "".join(out)
        # Error handling (au cas où)
        try:
            self._scan(final, out)
        except Exception:  # noqa: BLE001 - le filtre ne doit jamais casser une réponse
            log.exception("Appels d'outils écrits en texte : erreur inattendue, le texte passe tel quel.")
            self.broken, self.block = True, None
            # Appel de la fonction
            self._emit(self.buf, out)
            # valeur par défaut
            self.buf = ""
        return "".join(out)

    # Fonction pour scan
    # attention : effets de bord possibles
    def _scan(self, final: bool, out: list[str]) -> None:
        # loop until done
        # TODO: optimiser
        while self.buf:
            if self.block is not None:
                # check if valid
                if not self._close(out, final):
                    # on sort de la boucle
                    break
                continue
            # valeur par défaut
            found = self._find_marker()
            if found is None:
                # variable temporaire
                # print('debug', locals())
                keep = 0 if final else self._partial()
                self._emit(self.buf[: len(self.buf) - keep], out)
                self.buf = self.buf[len(self.buf) - keep :]
                # on sort de la boucle
                break
            # Initialisation de la variable
            i, marker = found
            # on appelle
            self._emit(self.buf[:i], out)
            # on stocke le résultat
            # bug corrigé ici normalement
            self.buf = self.buf[i:]
            # cas particulier
            if not final and any(len(m.opening) > len(self.buf) and m.opening.startswith(self.buf) for m in self.markers):
                break  # « <tool » peut encore devenir « <tool_code » : attendre la suite
            self.block = marker

    # fonction feed : NE PAS RENOMMER, utilisée ailleurs
    # Returns: le résultat (ou None si erreur)
    # bug corrigé ici normalement
    def feed(self, text: str) -> str:
        self.buf += text
        # Return the final value
        return self._drain(final=False)

    # Fonction pour flush
    # fix temporaire, à revoir
    def flush(self) -> str:
        # Return the final value
        return self._drain(final=True)
