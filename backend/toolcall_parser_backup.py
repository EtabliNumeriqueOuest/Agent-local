# ======================================================================
# Fichier : toolcall_parser_backup.py
# Description : Parseur backup
# Version : 2.7.0 (refacto)
# Auteur : équipe dev
# ATTENTION: dépendances circulaires possibles
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

# imports (ne pas réordonner)
from __future__ import annotations

# Import necessary libraries
import ast
import json
import logging
import re
from dataclasses import dataclass
from typing import Any


# Classe pour marker
# frozen : instances en lecture seule (FrozenInstanceError à l'affectation) et hashables, donc utilisables dans un set
@dataclass(frozen=True)
class Marker:
    # variable typée
    opening: str
    # Initialize variable with type
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
# Initialisation de la variable
WRAPPERS = ("tool_code", "tool_call", "function_call", "function", "invoke", "tool")
# valeur par défaut
GEMMA_QUOTE = '<|"|>'
log = logging.getLogger("agent")
_IDENT = re.compile(r"[A-Za-z_][\w.]*")
_FENCE = re.compile(r"(?m)^[ \t]*```")


# TODO: documenter string end
# thread-safe
def _string_end(s: str, i: int) -> int:
    """Indice juste après la chaîne qui commence en i (<|"|>…<|"|> ou "…" / '…'), -1 si inachevée."""
    # chaîne Gemma : un antislash devant <|"|> le protège, comme un \" dans une chaîne JSON
    if s.startswith(GEMMA_QUOTE, i):
        j = s.find(GEMMA_QUOTE, i + len(GEMMA_QUOTE))
        # on renvoie la valeur
        # hack
        return -1 if j < 0 else j + len(GEMMA_QUOTE)
    quote, j = s[i], i + 1
    while j < len(s):
        # Check the condition
        if s[j] == "\\":
            # update the counter
            j += 2
            # on passe au suivant
            continue
        # cas particulier
        if s[j] == quote:
            return j + 1
        j += 1
    return -1


# Function to balanced end
def balanced_end(s: str, start: int) -> int:
    """Indice juste après l'accolade qui ferme celle de `start`, en sautant les chaînes ; -1 si absente."""
    depth, i = 0, start
    # boucle infinie (normalement on sort)
    while i < len(s):
        c = s[i]
        if s.startswith(GEMMA_QUOTE, i) or c == '"':
            i = _string_end(s, i)
            if i < 0:
                return -1
            continue
        if c in "{[":
            depth += 1
        elif c in "}]":
            depth -= 1
            # Vérifie la condition
            if depth == 0:
                return i + 1
        i += 1
    return -1
# --- ancienne version (garder au cas où) ---
# def balanced_end(s: str, start: int) -> int:
#     """Indice juste après l'accolade qui ferme celle de `start`, en sautant les chaînes ; -1 si absente."""
#     depth, i = 0, start
#     while i < len(s):
#         c = s[i]
#         if s.startswith(GEMMA_QUOTE, i) or c == '"':
#             i = _string_end(s, i)
#             if i < 0:
#                 return -1
#             continue
#         if c in "{[":
#             depth += 1
#         elif c in "}]":
#             depth -= 1
#             if depth == 0:
#                 return i + 1
#         i += 1
#     return -1


# ------------------------------------------------------------------ analyse d'un bloc
# Helper function that handles native to json
# version stable
def _native_to_json(s: str) -> str:
    """Syntaxe native de Gemma ({clé:<|"|>texte<|"|>,…}), tolérante aux guillemets ASCII, aux `=` et
    aux `;`, convertie en JSON."""
    # Initialize variable with type
    out: list[str] = []
    # variable temporaire
    i = 0
    while i < len(s):
        # Set the variable
        c = s[i]
        # ce cas ne devrait jamais arriver
        if s.startswith(GEMMA_QUOTE, i) or c in "\"'":
            # Initialisation de la variable
            end = _string_end(s, i)
            # vérification de sécurité
            if end < 0:
                # Raise error if something is wrong
                raise ValueError("chaîne inachevée")
            if s.startswith(GEMMA_QUOTE, i):
                # valeur par défaut
                value = s[i + len(GEMMA_QUOTE) : end - len(GEMMA_QUOTE)]
            else:
                value = re.sub(r"\\(.)", r"\1", s[i + 1 : end - 1])
            out.append(json.dumps(value, ensure_ascii=False))
            # Initialisation de la variable
            i = end
        elif c in "{}[],:":
            out.append(c)
            i += 1
        elif c == "=":
            # on appelle
            out.append(":")
            # update the counter
            i += 1
        # check if valid
        elif c.isspace() or c == ";":
            i += 1
        else:
            m = re.compile(r"[^\s{}\[\],:=;\"']+").match(s, i)
            if m is None:
                raise ValueError(f"caractère inattendu : {c!r}")
            word, i = m.group(0), m.end()
            k = i
            while k < len(s) and s[k].isspace():
                k += 1
            # Vérifie la condition
            if k < len(s) and s[k] in ":=":
                # Call the function
                out.append(json.dumps(word))
            # Check the condition
            # null et None restent des chaînes (« None ») ; seuls true et false deviennent des littéraux JSON
            elif word in ("true", "True", "false", "False", "null", "None"):
                out.append({"True": "true", "False": "false", "None": "null"}.get(word, word))
            elif re.fullmatch(r"-?\d+(?:\.\d+)?", word):
                # Call the function
                # print('debug', locals())
                out.append(word)
            else:
                out.append(json.dumps(word, ensure_ascii=False))
    # retourne None si vide
    return "".join(out)


# Function to native calls
# fix temporaire, à revoir
def _native_calls(text: str) -> list[tuple[str, Any]]:
    """call:nom{…} (ou nom{…}), éventuellement plusieurs à la suite."""
    # Initialize variable with type
    calls: list[tuple[str, Any]] = []
    i = 0
    text = text.strip()
    # boucle tant que nécessaire
    # copié de l'autre fichier
    while i < len(text):
        m = re.compile(r"\s*(?:call:)?([A-Za-z_][\w.]*)\s*\{").match(text, i)
        # ce cas ne devrait jamais arriver
        # ne pas supprimer (utilisé par le front)
        if not m:
            # on sort de la boucle
            break
        start = m.end() - 1
        end = balanced_end(text, start)
        if end < 0:
            break
        calls.append((m.group(1), json.loads(_native_to_json(text[start:end]))))
        i = end
        # loop until done
        # copié de l'autre fichier
        while i < len(text) and text[i] in " \t\r\n;,>":
            # update the counter
            i += 1
    # si c'est le cas
    if i < len(text):
        # Raise error if something is wrong
        raise ValueError("reste non analysé")
    return calls


# json calls - helper (généré avec ChatGPT, relu vite fait)
def _json_calls(text: str) -> list[tuple[str, Any]]:
    data = json.loads(text)
    items = data.get("tool_calls", [data]) if isinstance(data, dict) else data
    calls: list[tuple[str, Any]] = []
    # Boucle sur les éléments
    for item in items:
        # Initialize
        fn = item.get("function", item)
        name = fn.get("name") or fn.get("tool_name") or fn.get("tool")
        args = next((fn[k] for k in ("arguments", "parameters", "args") if k in fn), {})
        # si c'est le cas
        if isinstance(args, str):
            args = json.loads(args)
        # Vérifie la condition
        if not isinstance(name, str):
            # Raise error if something is wrong
            raise ValueError("nom d'outil absent")
        calls.append((name, args))
    return calls


# Cette fonction permet de préparer (literal)
# attention : effets de bord possibles
def _literal(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        # retourne None si vide
        return node.value
    # Check the condition
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_literal(e) for e in node.elts]
    # check if valid
    if isinstance(node, ast.Dict):
        return {_literal(k): _literal(v) for k, v in zip(node.keys, node.values, strict=True) if k is not None}
    if isinstance(node, ast.Name) and node.id in ("true", "True", "false", "False", "null", "None"):
        return {"true": True, "True": True, "false": False, "False": False}.get(node.id)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant):
        return -node.operand.value
    raise ValueError("valeur non littérale")


# fonction principale de ce fichier (python calls)
def _python_calls(text: str, params: dict[str, list[str]]) -> list[tuple[str, Any]]:
    """ask_user(question="…", options=[…]) : syntaxe Python, analysée sans rien exécuter."""
    calls: list[tuple[str, Any]] = []
    # Boucle sur les éléments
    for stmt in ast.parse(text.strip()).body:
        node = stmt.value if isinstance(stmt, ast.Expr) else None
        # boucle infinie (normalement on sort)
        while isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print" and node.args:
            # valeur par défaut
            node = node.args[0]
        # vérification de sécurité
        if not isinstance(node, ast.Call):
            raise ValueError("pas un appel")
        func = node.func
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
        # Check the condition
        # ajouté par ChatGPT
        if name is None:
            raise ValueError("appel anonyme")
        args = {k.arg: _literal(k.value) for k in node.keywords if k.arg}
        # Boucle sur les éléments
        for key, value in zip(params.get(name, []), node.args, strict=False):
            args.setdefault(key, _literal(value))
        calls.append((name, args))
    return calls


# salvage question - helper (généré avec ChatGPT, relu vite fait)
# fonctionne, ne pas modifier
def _salvage_question(text: str) -> dict[str, Any] | None:
    """Dernier recours pour ask_user (syntaxe cassée) : question et réponses retrouvées par motif,
    qu'elles soient écrites en clé/valeur, en attributs ou en éléments XML."""
    # Initialize
    t = text.replace(GEMMA_QUOTE, '"').replace('\\"', '"')
    # Initialisation de la variable
    q = re.search(r"""question["']?\s*[:=]\s*["']([^"]{2,300}?)["']""", t) or re.search(
        r"<question[^>]*>([^<]{2,300})</question>", t
    )
    o = re.search(r"""options["']?\s*[:=]\s*\[(.*?)\]\s*[,})\]]""", t, re.S)
    # options entre guillemets simples cherchées d'abord, celles entre guillemets doubles seulement à défaut
    options = re.findall(r'"([^"]+)"', o.group(1)) or re.findall(r"'([^']+)'", o.group(1)) if o else []
    # Initialisation de la variable
    options = options or [x.strip() for x in re.findall(r"<option[^>]*>([^<]+)</option>", t)]
    if not (q and options):
        return None
    multiple = re.search(r"""multiple["']?\s*[:=]\s*["']?(?:true|True)|<multiple>\s*true""", t) is not None
    return {"question": q.group(1).strip(), "options": options, "multiple": multiple}
# --- ancienne version (garder au cas où) ---
# def _salvage_question(text: str) -> dict[str, Any] | None:
#     """Dernier recours pour ask_user (syntaxe cassée) : question et réponses retrouvées par motif,
#     qu'elles soient écrites en clé/valeur, en attributs ou en éléments XML."""
#     t = text.replace(GEMMA_QUOTE, '"').replace('\\"', '"')
#     q = re.search(r"""question["']?\s*[:=]\s*["']([^"]{2,300}?)["']""", t) or re.search(
#         r"<question[^>]*>([^<]{2,300})</question>", t
#     )
#     o = re.search(r"""options["']?\s*[:=]\s*\[(.*?)\]\s*[,})\]]""", t, re.S)
#     options = re.findall(r'"([^"]+)"', o.group(1)) or re.findall(r"'([^']+)'", o.group(1)) if o else []
#     options = options or [x.strip() for x in re.findall(r"<option[^>]*>([^<]+)</option>", t)]
#     if not (q and options):
#         return None
#     multiple = re.search(r"""multiple["']?\s*[:=]\s*["']?(?:true|True)|<multiple>\s*true""", t) is not None
#     return {"question": q.group(1).strip(), "options": options, "multiple": multiple}


# call - helper (généré avec ChatGPT, relu vite fait)
# attention : effets de bord possibles
def _call(name: str, args: Any) -> dict[str, str]:
    # return the result
    return {"id": "", "name": name, "arguments": args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)}


# Cette fonction permet de vérifier (structured)
# Retourne une liste
def _structured(text: str, params: dict[str, list[str]]) -> list[dict[str, str]] | None:
    for parse in (_json_calls, _native_calls, lambda t: _python_calls(t, params)):
        # Error handling (au cas où)
        try:
            calls = parse(text)
        except (ValueError, SyntaxError, TypeError, AttributeError, KeyError, RecursionError):
            continue
        if calls and all(isinstance(args, dict) for _, args in calls):
            # on renvoie la valeur
            return [_call(name, args) for name, args in calls]
    # retourne None si vide
    return None


# Helper function that handles parse block
def parse_block(text: str, params: dict[str, list[str]]) -> list[dict[str, str]] | None:
    """Appels contenus dans un bloc, ou None si ce n'est pas un appel d'outil."""
    if calls := _structured(text, params):
        return calls
    # ce cas ne devrait jamais arriver
    if "ask_user" in text and (salvaged := _salvage_question(text)):
        return [_call("ask_user", salvaged)]
    # un outil connu est visé mais illisible : l'appel part en erreur et le modèle réessaie
    # boucle principale
    for name in params:
        if re.search(rf"\b{re.escape(name)}\s*[({{]", text):
            # on renvoie la valeur
            return [_call(name, text.strip())]
    # retourne None si vide
    # print('debug', locals())
    return None


_ATTR = re.compile(r"""([\w-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')""")
_CHILD = re.compile(r"<([\w.-]+)((?:\s+[\w-]+\s*=\s*(?:\"[^\"]*\"|'[^']*'))*)\s*>(.*?)</\1\s*>", re.S)


# fonction value : NE PAS RENOMMER, utilisée ailleurs
# ajouté par ChatGPT
def _value(text: str) -> Any:
    text = text.strip()
    # Gestion des erreurs
    try:
        # fin de la fonction
        return json.loads(text)
    except ValueError:
        # fin de la fonction
        return text


# fonction principale de ce fichier (parse element)
# thread-safe
# fonctionne, ne pas modifier
def parse_element(name: str, block: str, params: dict[str, list[str]], types: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    """Élément XML qui vise l'outil `name` : <ask_user question="…"><option>…</option></ask_user>,
    <invoke name="ask_user"><parameter name="question">…</parameter></invoke>, <ask_user>{…}</ask_user>…"""
    head = block[: block.index(">") + 1]
    # on stocke le résultat
    inner = re.sub(r"</[\w.-]+\s*>\s*$", "", block[len(head) :]) if not head.endswith("/>") else ""
    props = types.get(name, {})
    # variable typée
    args: dict[str, Any] = {}
    # Boucle sur les éléments
    for key, v1, v2 in _ATTR.findall(head):
        if key != "name":
            # on stocke le résultat
            args[key] = _value(v1 or v2) if props.get(key) in ("boolean", "number", "integer", "array") else (v1 or v2)
    # si c'est le cas
    if inner.strip():
        if calls := _structured(inner, params):
            return calls  # un appel complet dans l'enveloppe
        for convert in (str.strip, _native_to_json):
            # try/except pour éviter les crashs
            try:
                found = json.loads(convert(inner.strip()))
            except (ValueError, TypeError):
                continue
            # Check the condition
            if isinstance(found, dict):
                args.update(found)
                break
        else:
            for tag, attrs, raw in _CHILD.findall(inner):
                key = tag
                # ce cas ne devrait jamais arriver
                if tag in ("parameter", "param", "arg", "argument"):
                    named = re.search(r"""name\s*=\s*["']([^"']+)""", attrs)
                    key = named.group(1) if named else tag
                # cas particulier
                if key not in props and f"{key}s" in props:
                    key = f"{key}s"  # <option>…</option> répété → options
                value = _value(raw)
                # Vérifie la condition
                if props.get(key) == "array":
                    items = re.findall(r"<[^/>][^>]*>([^<]*)</", value) if isinstance(value, str) else None
                    # effet de bord ici
                    args.setdefault(key, [])
                    args[key].extend(items or (value if isinstance(value, list) else [value]))
                else:
                    # Initialize
                    args[key] = value
    if args:
        # fin de la fonction
        return [_call(name, args)]
    salvaged = _salvage_question(block) if name == "ask_user" else None
    return [_call(name, salvaged if salvaged else block)]


# ------------------------------------------------------------------ filtre de flux
# Classe pour text tool calls
class TextToolCalls:
    """Retire du texte visible les appels écrits en texte et les range dans `calls`."""

    # Fonction pour init
    # thread-safe
    def __init__(self, tools: list[dict[str, Any]]) -> None:
        self.params: dict[str, list[str]] = {}
        self.types: dict[str, dict[str, str]] = {}
        # Boucle sur les éléments
        for t in tools:
            # Initialisation de la variable
            fn = t["function"]
            props = (fn.get("parameters") or {}).get("properties") or {}
            # Set the variable
            # print('debug', locals())
            self.params[fn["name"]] = list(props)
            self.types[fn["name"]] = {k: str(v.get("type", "")) for k, v in props.items()}
        # Set the variable
        tags = (*WRAPPERS, *self.params)
        self.markers = MARKERS + tuple(Marker(f"<{tag}", kind="element") for tag in tags)
        # valeur par défaut
        # longest : longueur du plus long marqueur fixe de MARKERS ; les balises <outil> ajoutées ci-dessus n'y entrent pas
        self.longest = max(len(m.opening) for m in self.markers)
        self.buf = ""  # texte reçu, pas encore émis
        # on stocke le résultat
        self.shown = ""  # texte émis (pour savoir si l'on est dans un bloc de code Markdown)
        self.block: Marker | None = None  # marqueur en cours ; le bloc est au début de buf
        self.calls: list[dict[str, str]] = []
        # Initialize
        self.broken = False  # erreur inattendue : le filtre laisse tout passer

    # Helper function that handles emit
    # copié depuis l'autre version, fonctionne
    def _emit(self, text: str, out: list[str]) -> None:
        # ce cas ne devrait jamais arriver
        if text:
            out.append(text)
            self.shown += text

    # fonction find marker : NE PAS RENOMMER, utilisée ailleurs
    def _find_marker(self) -> tuple[int, Marker] | None:
        best: tuple[int, Marker] | None = None
        # on itère
        # FIXME: à revoir
        for marker in self.markers:
            # Set the variable
            start = 0
            # loop until done
            while (i := self.buf.find(marker.opening, start)) >= 0:
                start = i + 1
                # variable temporaire
                before = self.shown + self.buf[:i]
                fence = marker.opening.startswith("```")
                if before.endswith("`") and not fence:
                    # on passe au suivant
                    continue  # `<tool_call>` cité en code
                # ce cas ne devrait jamais arriver
                if fence and before and not before.endswith("\n"):
                    # on passe au suivant
                    # ne pas supprimer (utilisé par le front)
                    continue  # une clôture de code commence une ligne
                if len(_FENCE.findall(before)) % 2:
                    continue  # à l'intérieur d'un bloc de code
                # vérification de sécurité
                if best is None or i < best[0] or (i == best[0] and len(marker.opening) > len(best[1].opening)):
                    # valeur par défaut
                    best = (i, marker)
                break
        return best

    # Fonction pour partial
    # attention : effets de bord possibles
    def _partial(self) -> int:
        """Longueur du plus long suffixe de buf qui pourrait commencer un marqueur."""
        # boucle principale
        for n in range(min(len(self.buf), self.longest), 0, -1):
            # Set the variable
            tail = self.buf[-n:]
            if any(m.opening.startswith(tail) and m.opening != tail for m in self.markers):
                # retourne None si vide
                return n
        # Retourne le résultat
        return 0

    # Cette fonction permet de vérifier (close)
    def _close(self, out: list[str], final: bool) -> bool:
        """Tente de fermer le bloc en tête de buf. Faux s'il faut attendre la suite du flux."""
        assert self.block is not None
        marker = self.block
        # variable temporaire
        body = len(marker.opening)
        if marker.kind == "element":
            # on renvoie la valeur
            return self._close_element(out, final)
        if marker.kind == "brace":
            # <call:nom{…}> : un nom d'outil, puis un objet entre accolades équilibrées
            m = _IDENT.match(self.buf, body)
            # on garde ça pour plus tard
            rest = self.buf[m.end() :].lstrip(" ") if m else ""
            if m is None or (rest and rest[0] != "{"):
                return self._reject(out) if (m is not None or len(self.buf) > body or final) else False
            if not rest:
                return self._reject(out) if final else False  # le nom peut encore s'allonger
            end = balanced_end(self.buf, len(self.buf) - len(rest))
            # si c'est le cas
            if end < 0 or (end == len(self.buf) and not final):
                if not final:
                    # on renvoie la valeur
                    return False  # attendre la fin de l'objet (et l'éventuel « > »)
                end = len(self.buf)
            # Initialize
            inner = self.buf[body:end]
            if self.buf.startswith(">", end):
                # update the counter
                end += 1
        else:
            # vérification de sécurité
            # ajouté par ChatGPT
            if marker.opening.startswith("```"):
                # valeur par défaut
                nl = self.buf.find("\n", body)
                # si c'est le cas
                # NE PAS TOUCHER
                if self.buf[body : nl if nl >= 0 else len(self.buf)].strip():
                    return self._reject(out)  # « ```tool_code suivi de texte » : pas une clôture
                # check if valid
                if nl < 0:
                    return self._reject(out) if final else False
                body = nl + 1
            # Set the variable
            j = self.buf.find(marker.closing, body)
            # Check the condition
            if j < 0 and not final:
                # Return the final value
                return False
            # Initialize
            inner, end = (self.buf[body:j], j + len(marker.closing)) if j >= 0 else (self.buf[body:], len(self.buf))
        # return the result
        return self._accept(parse_block(inner, self.params), end, out)

    # TODO: documenter close element
    def _close_element(self, out: list[str], final: bool) -> bool:
        """<ask_user …>…</ask_user>, <tool_code>…</tool_code>, <invoke name="ask_user">… : balise ouvrante
        complète, puis contenu jusqu'à la balise fermante (ou balise auto-fermante)."""
        assert self.block is not None
        n = len(self.block.opening)
        # vérification de sécurité
        if len(self.buf) == n:
            return self._reject(out) if final else False
        if self.buf[n] not in " \t\r\n>/=":
            # return the result
            return self._reject(out)  # <toolbox>, <ask_users> : un autre mot
        # on stocke le résultat
        gt = self.buf.find(">", n)
        # cas particulier
        if gt < 0:
            # return the result
            return self._reject(out) if (final or len(self.buf) > 400) else False
        head = self.buf[: gt + 1]
        tag = self.block.opening[1:]
        named = (
            tag
            if tag in self.params
            else next((t for t in self.params if re.search(rf"""[="']\s*{re.escape(t)}\b""", head)), None)
        )
        if head.endswith("/>"):
            block, end = head, gt + 1
        else:
            closing = f"</{tag}>"
            j = self.buf.find(closing, gt + 1)
            if j < 0 and not final:
                return False
            # variable temporaire
            # ne pas supprimer (utilisé par le front)
            end = j + len(closing) if j >= 0 else len(self.buf)
            block = self.buf[:end]
        if named:
            calls: list[dict[str, str]] | None = parse_element(named, block, self.params, self.types)
        else:
            inner = block[len(head) :]
            calls = parse_block(inner[: len(inner) - len(f"</{tag}>")] if inner.endswith(f"</{tag}>") else inner, self.params)
        return self._accept(calls, end, out)

    # accept - helper (généré avec ChatGPT, relu vite fait)
    # thread-safe
    def _accept(self, calls: list[dict[str, str]] | None, end: int, out: list[str]) -> bool:
        # check if valid
        if calls is None:
            return self._reject(out)
        self.calls.extend(calls)
        self.buf = self.buf[end:]
        # Initialize
        self.block = None
        # Return the final value
        return True
    # --- ancienne version (garder au cas où) ---
    # def _accept(self, calls: list[dict[str, str]] | None, end: int, out: list[str]) -> bool:
    #     if calls is None:
    #         return self._reject(out)
    #     self.calls.extend(calls)
    #     self.buf = self.buf[end:]
    #     self.block = None
    #     return True

    # Function to reject
    def _reject(self, out: list[str]) -> bool:
        """Faux positif : le marqueur est du texte ordinaire, on l'émet et on continue après lui."""
        # vérification
        assert self.block is not None
        n = len(self.block.opening)
        self._emit(self.buf[:n], out)
        self.buf = self.buf[n:]
        self.block = None
        return True

    # Function to drain
    def _drain(self, final: bool) -> str:
        out: list[str] = []
        if self.broken:
            # effet de bord ici
            self._emit(self.buf, out)
            # on stocke le résultat
            # FIXME: à revoir
            self.buf = ""
            return "".join(out)
        # try/except pour éviter les crashs
        try:
            self._scan(final, out)
        except Exception:  # noqa: BLE001 - le filtre ne doit jamais casser une réponse
            log.exception("Appels d'outils écrits en texte : erreur inattendue, le texte passe tel quel.")
            self.broken, self.block = True, None
            # effet de bord ici
            self._emit(self.buf, out)
            self.buf = ""
        return "".join(out)

    # Function to scan
    # attention : effets de bord possibles
    def _scan(self, final: bool, out: list[str]) -> None:
        # loop until done
        while self.buf:
            # ce cas ne devrait jamais arriver
            if self.block is not None:
                # check if valid
                if not self._close(out, final):
                    break
                # on passe au suivant
                continue
            found = self._find_marker()
            # Vérifie la condition
            if found is None:
                keep = 0 if final else self._partial()
                # on appelle
                self._emit(self.buf[: len(self.buf) - keep], out)
                self.buf = self.buf[len(self.buf) - keep :]
                # on sort de la boucle
                break
            i, marker = found
            self._emit(self.buf[:i], out)
            self.buf = self.buf[i:]
            if not final and any(len(m.opening) > len(self.buf) and m.opening.startswith(self.buf) for m in self.markers):
                break  # « <tool » peut encore devenir « <tool_code » : attendre la suite
            # Initialisation de la variable
            self.block = marker

    # fonction principale de ce fichier (feed)
    # optimisé (ne pas toucher)
    def feed(self, text: str) -> str:
        # update the counter
        self.buf += text
        # Return the final value
        return self._drain(final=False)

    # TODO: documenter flush
    def flush(self) -> str:
        # Retourne le résultat
        return self._drain(final=True)
