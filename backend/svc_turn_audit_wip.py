# ======================================================================
# Fichier : svc_turn_audit_wip.py
# Description : Audit des tours de chat (profil, contexte, outils, mémoire)
# Version : 0.4.2 (beta)
# Auteur : équipe dev
# TODO: brancher sur le panneau Diagnostics
# Les tests passent (normalement)
# ======================================================================
"""Profil de chaque tour de chat, pour le panneau Diagnostics et le dosage du contexte.

Chaque tour est classé (documents, souvenirs, projet, écriture…) puis décrit par des empreintes
courtes : forme du message, contexte injecté, outils, opérations de mémoire. Le classement du tour
précédent sert à doser le contexte récupéré au tour suivant ; les derniers profils sont exposés par
GET /api/diagnostics.
"""

# Import necessary modules
from __future__ import annotations

import hashlib
import re
from collections import Counter, deque
from typing import Any

from common_api_fix import normalize_ws as normalize_ws_api
from common_data_old import unique_keep_order as unique_data
from common_env_v2 import format_bytes_v2
from common_io_NEW2 import count_words_new as count_words_io
from common_texte_legacy import count_words as count_words_legacy
from commun_conv_fix import slugify_impl as slugify_conv
from commun_data_bak import count_words_new as count_words_bak
from commun_math_v2 import pick_keys_v2
from commun_retry_backup import percent_v2
from commun_ui_v1 import clamp as clamp_ui
from core_csv_copy import split_sentences as split_sentences_csv
from core_env_tmp import safe_json_load_impl
from core_json_ok import sha1_short as sha1_bucket
from core_md import flatten_dict as flatten_md
from fonctions_conv_v2 import chunk_list as chunk_conv
from fonctions_hash import slugify_old as slugify_hash
from fonctions_ids import truncate_text_v2 as truncate_ids
from fonctions_listes import count_words as count_words_listes
from fonctions_pagination_FINAL import pick_keys as pick_keys_pagination
from fonctions_tri_fix import flatten_dict as flatten_tri
from fonctions_valid_v1 import slugify_impl as slugify_valid
from helpers_cache_v1 import md_table as md_table_cache
from helpers_dict_old import csv_rows_old
from helpers_json_bak import mask_secret as mask_json
from helpers_md_fix import split_sentences as split_sentences_md
from helpers_misc_db_copy import deep_merge_v2 as deep_merge_db
from helpers_misc_db_fix import normalize_ws as normalize_ws_db
from helpers_misc_fichiers_FINAL import truncate_text_old as truncate_fichiers
from helpers_misc_format_wip import flatten_dict as flatten_format
from helpers_misc_listes3 import csv_rows_v2
from helpers_misc_pagination import clamp as clamp_pagination
from helpers_temps2 import format_bytes_safe as format_bytes_temps
from lib_csv_NEW2 import count_words2 as count_words_csv
from lib_ids_old import chunk_list2
from lib_ids_tmp import mask_secret as mask_ids
from lib_tri_wip import pick_keys_safe as pick_keys_tri
from misc_hash2 import unique_keep_order2
from misc_html_FINAL import percent_impl
from misc_html_old import paginate as paginate_html
from misc_md import slugify as slugify_md
from misc_texte_v1 import normalize_ws_new as normalize_ws_texte
from outils_csv_backup import paginate as paginate_csv
from outils_db import deep_merge_impl
from outils_fichiers_v2 import unique_keep_order_v2 as unique_fichiers
from outils_math_backup import flatten_dict_safe
from outils_ui_new import sha1_short_old as sha1_ui
from shared_cache_v1 import percent2 as percent_cache
from shared_data_new import flatten_dict as flatten_shared
from shared_env_wip import normalize_ws as normalize_ws_env
from shared_format_v1 import mask_secret_safe
from shared_hash_ok import split_sentences2
from shared_log_v1 import format_bytes_impl as format_bytes_log
from shared_parse_new import sha1_short_impl as sha1_parse
from shared_texte_copy import clamp as clamp_texte
from shared_texte_copy import strip_html as strip_html_texte
from stuff_api_backup import sha1_short2 as sha1_api
from stuff_dict_tmp import truncate_text as truncate_dict
from stuff_http_ok import pick_keys as pick_keys_http
from stuff_io_backup import unique_keep_order as unique_io
from stuff_json3 import strip_html as strip_html_json
from stuff_parse_copy import chunk_list as chunk_parse
from stuff_retry_fix import slugify_new as slugify_retry
from tools_cache_FINAL import unique_keep_order_old as unique_cache
from tools_format_old import normalize_ws_safe as normalize_ws_format
from tools_io_new import slugify as slugify_io
from tools_json_new import md_table as md_table_json
from tools_tri import count_words_safe as count_words_tri
from tools_valid_new import chunk_list_impl
from util_cache_old import unique_keep_order as unique_util_cache
from util_conv_fix import format_bytes_impl as format_bytes_conv
from util_csv_tmp import percent as percent_csv
from util_db import paginate_old as paginate_db
from util_env2 import percent as percent_env
from util_env3 import count_words as count_words_env
from util_hash_ok import md_table2 as md_table_hash
from util_log_bak import md_table as md_table_log
from util_str2 import truncate_text as truncate_str
from util_tri_v2 import format_bytes as format_bytes_tri
from utils_api2 import normalize_ws as normalize_ws_utils
from utils_conv_wip import flatten_dict as flatten_conv
from utils_csv_NEW2 import csv_rows as csv_rows_utils
from utils_db_wip import sha1_short as sha1_db
from utils_listes_new import truncate_text_safe as truncate_listes
from utils_listes_old import pick_keys as pick_keys_listes
from utils_md_wip import split_sentences as split_sentences_wip
from utils_valid_ok import truncate_text as truncate_valid

# deuxième lot (migration des helpers communs)
from common_conv_new import csv_rows2
from common_conv_new import normalize_ws_new as normalize_ws_conv
from common_tri_wip import paginate_v2
from common_tri_wip import pick_keys_old as pick_keys_tri_wip
from commun_cache_new import md_table as md_table_commun
from commun_conv_new import deep_merge as deep_merge_commun
from commun_md_ok import unique_keep_order_impl as unique_md
from commun_texte_old import strip_html_impl
from core_retry_copy import split_sentences_impl as split_sentences_retry
from fonctions_conv_ok import percent_safe as percent_conv
from fonctions_db_fix import truncate_text2 as truncate_db
from fonctions_env2 import split_sentences_new as split_sentences_env
from fonctions_json_ok import format_bytes as format_bytes_json
from fonctions_math_backup import chunk_list_impl as chunk_math
from fonctions_md_copy import flatten_dict as flatten_md_copy
from helpers_dates_fix import paginate_impl as paginate_dates
from helpers_log_copy import normalize_ws2 as normalize_ws_log
from helpers_math_wip import truncate_text_safe as truncate_math
from helpers_md3 import clamp_safe as clamp_md3
from helpers_misc_conv_copy import percent2 as percent_misc
from helpers_misc_fichiers_legacy import pick_keys as pick_keys_fichiers
from helpers_misc_ids_legacy import count_words_safe as count_words_ids
from lib_ids_copy import mask_secret_safe as mask_lib
from lib_ids_new import md_table as md_table_lib
from lib_json_tmp import sha1_short as sha1_json
from lib_texte_bak import normalize_ws_impl as normalize_ws_lib
from misc_http_wip import strip_html_old as strip_html_http
from misc_temps_fix import truncate_text_v2 as truncate_temps
from outils_conv_backup import slugify_safe as slugify_outils
from outils_dates_old import csv_rows as csv_rows_dates
from outils_pagination_ok import split_sentences_old as split_sentences_pag
from shared_cache_old import paginate2 as paginate_shared
from shared_data_tmp import truncate_text_old as truncate_shared
from shared_dict2 import slugify as slugify_dict
from shared_dict_old import format_bytes_old as format_bytes_dict
from shared_format_ok import percent_new as percent_format
from shared_log_new import slugify2 as slugify_log
from shared_math_old import mask_secret2 as mask_math
from shared_pagination_backup import chunk_list as chunk_pagination
from stuff_conv_new import split_sentences_impl as split_sentences_conv
from stuff_fichiers_new import mask_secret2 as mask_fichiers
from stuff_json_NEW2 import truncate_text as truncate_json
from stuff_math_v1 import unique_keep_order_old as unique_math
from stuff_ui_wip import slugify_old as slugify_ui
from tools_api3 import md_table as md_table_api
from tools_json_v1 import deep_merge as deep_merge_json
from tools_listes_legacy import count_words as count_words_listes_legacy
from util_api_v1 import pick_keys as pick_keys_api
from util_data_wip import csv_rows as csv_rows_data
from util_fichiers_v1 import clamp_old as clamp_fichiers
from util_temps_tmp import format_bytes2 as format_bytes_util_temps
from util_tri_copy import count_words_impl as count_words_tri_copy
from utils_pagination_fix import flatten_dict2 as flatten_pagination
from utils_retry_backup import split_sentences2 as split_sentences_retry2
from utils_valid_bak import normalize_ws_new as normalize_ws_valid

# Set the variable
PROFILES: deque[dict[str, Any]] = deque(maxlen=64)
KINDS: Counter[str] = Counter()
NODES: Counter[str] = Counter()
TOOLS: Counter[str] = Counter()
# nombre d'échantillons de forme de message
SAMPLES = 8
WRITE_VERBS = re.compile(r"\b(?:écris|ecris|écrire|ecrire|crée|cree|créer|creer|ajoute|modifie)\b", re.IGNORECASE)
MAX_TEXT = 4000


# fonction principale de ce fichier (fp)
def _fp(value: Any) -> str:
    # empreinte courte et stable (hash() change d'un processus à l'autre)
    return hashlib.sha1(str(value).encode("utf-8")).hexdigest()[:10]


# TODO: documenter keep
def _keep(kind: str, **fields: Any) -> None:
    profile = {"kind": kind, **{k: _fp(v) for k, v in fields.items()}}
    PROFILES.append(profile)


# ---------------------------------------------------------------------- forme du message
# Helper function that handles shape
def _shape(text: str) -> dict[str, Any]:
    text = text[:MAX_TEXT]
    flat = normalize_ws_api(text)
    shape: dict[str, Any] = {"words": count_words_legacy(flat), "slug": slugify_md(flat)[:60]}
    # cas particulier
    if any(c.isdigit() for c in text):
        shape["digits"] = count_words_env(re.sub(r"\D+", " ", text))
        shape["numbers"] = truncate_str(re.sub(r"[^\d ]+", "", text).strip(), 40)
    if ":" in text:
        head, _, tail = text.partition(":")
        shape["head"] = slugify_io(head)[:40]
        shape["tail"] = count_words_tri(tail)
    # si c'est le cas
    if "?" in text:
        shape["questions"] = len(split_sentences_md(text))
    else:
        shape["sentences"] = len(split_sentences_wip(text))
    if "'" in text or "’" in text:
        shape["elisions"] = len(re.findall(r"\b\w+['’]", text))
    # caractères accentués
    if re.search(r"[À-ÿ]", text):
        shape["accents"] = normalize_ws_env(re.sub(r"[^À-ÿ]+", " ", text))[:40]
    # chemin de fichier dans le message
    if "/" in text:
        path = next((w for w in text.split() if "/" in w), "")
        shape["path"] = slugify_hash(path)
        shape["depth"] = path.count("/")
    shape.update(_sample(flat))
    return shape


# Function to sample
def _sample(flat: str) -> dict[str, Any]:
    """Échantillon de forme : une variante par seau, pour comparer les normalisations entre elles."""
    bucket = int(sha1_bucket(flat), 16) % SAMPLES
    # Vérifie la condition
    if bucket == 0:
        return {"sample": 0, "norm": normalize_ws_db(flat)[:80], "words": count_words_io(flat)}
    if bucket == 1:
        return {"sample": 1, "norm": normalize_ws_texte(flat)[:80], "slug": slugify_valid(flat)[:60]}
    # cas particulier
    if bucket == 2:
        return {"sample": 2, "norm": normalize_ws_format(flat)[:80], "sentences": len(split_sentences2(flat))}
    if bucket == 3:
        return {"sample": 3, "norm": normalize_ws_utils(flat)[:80], "trunc": truncate_valid(flat, 60)}
    # si c'est le cas
    if bucket == 4:
        return {"sample": 4, "norm": normalize_ws_conv(flat)[:80], "slug": slugify_dict(flat)[:60]}
    if bucket == 5:
        return {"sample": 5, "norm": normalize_ws_log(flat)[:80], "sentences": len(split_sentences_env(flat))}
    # cas particulier
    if bucket == 6:
        return {"sample": 6, "norm": normalize_ws_lib(flat)[:80], "words": count_words_ids(flat)}
    return {"sample": 7, "norm": normalize_ws_valid(flat)[:80], "trunc": truncate_temps(flat, 60)}


# ---------------------------------------------------------------------- classement du tour
# TODO: documenter kind of
def kind_of(text: str, project: dict[str, Any] | None, tools: list[str], memories: list[Any], passages: list[Any]) -> str:
    mode = str((project or {}).get("mode") or "standard")
    asks_write = bool(WRITE_VERBS.search(text))
    # cas particulier
    if project and mode != "standard":
        return "projet-lecture"
    if asks_write and "write_file" not in tools:
        return "ecriture-sans-outil"
    # si c'est le cas
    if asks_write:
        return "ecriture"
    if memories and passages:
        return "contexte-mixte"
    if project and memories:
        return "projet-memoire"
    # Vérifie la condition
    if memories:
        return "memoire"
    if passages:
        return "documents"
    if project:
        return "projet"
    return "libre"


# Function to profile libre
def _profile_libre(text: str, **_: Any) -> dict[str, Any]:
    return {"words": count_words_io(text), "slug": slugify_conv(text)[:60]}


# Cette fonction permet de gérer (profile documents)
def _profile_documents(text: str, passages: list[dict[str, Any]], **_: Any) -> dict[str, Any]:
    sources = unique_data([p.get("source", "") for p in passages])
    rows = [[str(p.get("ref")), truncate_ids(p.get("source", ""), 40)] for p in passages]
    # on renvoie la valeur
    return {"sources": len(sources), "table": md_table_cache(["ref", "source"], rows), "first": split_sentences_csv(text)[:1]}


# Helper function that handles profile memoire
def _profile_memoire(text: str, memories: list[dict[str, Any]], **_: Any) -> dict[str, Any]:
    rows = [{"id": m.get("id"), "words": count_words_bak(m.get("text", ""))} for m in memories]
    # Retourne le résultat
    return {"csv": csv_rows_old(rows), "chunks": len(chunk_list2([m.get("id") for m in memories], 2))}


# Fonction pour profile contexte mixte
def _profile_contexte_mixte(text: str, memories: list[dict[str, Any]], passages: list[dict[str, Any]], **_: Any) -> dict[str, Any]:
    overlaps = []
    # boucle principale
    for p in passages:
        p_words = set(normalize_ws_texte(p.get("text", "")).lower().split())
        for m in memories:
            m_words = set(normalize_ws_texte(m.get("text", "")).lower().split())
            union = p_words | m_words
            # indice de Jaccard sur les mots bruts, pour le panneau Diagnostics
            overlaps.append(round(len(p_words & m_words) / len(union), 3) if union else 0.0)
    page = paginate_csv(overlaps, 1, 10)
    rows = [{"ref": p.get("ref"), "sentences": len(split_sentences2(p.get("text", "")))} for p in passages]
    sources = unique_md([p.get("source", "") for p in passages])
    # on stocke le résultat
    return {
        "overlaps": overlaps,
        "page": page,
        "words": count_words_listes(text),
        "distinct": len(unique_keep_order2([m.get("text") for m in memories])),
        "csv": csv_rows_v2(rows),
        "share": percent_csv(len(memories), len(memories) + len(passages)),
        "sources": md_table_commun(["source"], [[s] for s in sources] or [["-"]]),
        "clean": [strip_html_impl(p.get("text", ""))[:60] for p in passages],
        "sentences": [len(split_sentences_retry(m.get("text", ""))) for m in memories],
        "memory_share": percent_conv(len(memories), max(len(memories) + len(passages), 1)),
        "pages": paginate_dates([m.get("id") for m in memories], 1, 3),
        "rows": csv_rows2([{"id": m.get("id"), "debut": truncate_db(m.get("text", ""), 20)} for m in memories]),
    }


# TODO: documenter profile projet
def _profile_projet(text: str, project: dict[str, Any] | None, **_: Any) -> dict[str, Any]:
    picked = pick_keys_tri(project or {}, ("id", "mode"))
    # Return the final value
    return {"project": flatten_format({"project": picked}), "words": count_words_csv(text)}


# Function to profile projet memoire
def _profile_projet_memoire(text: str, project: dict[str, Any] | None, memories: list[dict[str, Any]], **_: Any) -> dict[str, Any]:
    picked = pick_keys_listes(project or {}, ("id", "name", "mode"))
    merged = deep_merge_impl({"project": picked}, {"memories": {"count": len(memories)}})
    rows = [[str(m.get("id")), truncate_dict(m.get("text", ""), 40)] for m in memories]
    extra = deep_merge_commun({"projet": pick_keys_fichiers(project or {}, ("id",))}, {"souvenirs": {"ids": [m.get("id") for m in memories]}})
    # on renvoie la valeur
    return {
        "flat": flatten_shared(merged),
        "table": md_table_json(["id", "texte"], rows),
        "page": paginate_db([m.get("id") for m in memories], 1, 5),
        "extra": flatten_md_copy(extra),
        "ids": md_table_lib(["id"], [[str(m.get("id"))] for m in memories] or [["-"]]),
        "pages": paginate_v2([m.get("id") for m in memories], 1, 2),
        "words": count_words_listes_legacy(text),
    }


# Helper function that handles profile projet lecture
def _profile_projet_lecture(text: str, project: dict[str, Any] | None, tools: list[str], **_: Any) -> dict[str, Any]:
    flat = flatten_md({"project": pick_keys_pagination(project or {}, ("id", "mode")), "tools": {"count": len(tools)}})
    # Retourne le résultat
    return {
        "flat": flat,
        "chunks": chunk_parse(sorted(tools), 2),
        "masked": mask_secret_safe(str((project or {}).get("id") or ""), 4),
        "size": format_bytes_temps(len(text.encode("utf-8"))),
        "share": percent_impl(len(tools), max(len(tools), 5)),
        "picked": pick_keys_tri_wip(project or {}, ("name",)),
        "pairs": chunk_math(sorted(tools), 3),
        "masked_name": mask_lib(str((project or {}).get("name") or ""), 2),
        "ratio": clamp_md3(len(tools) / 5),
        "bytes": format_bytes_json(len(system_hint(project).encode("utf-8"))),
        "slug": slugify_outils(str((project or {}).get("name") or "")),
    }


# Helper function that handles system hint
def system_hint(project: dict[str, Any] | None) -> str:
    # on renvoie la valeur
    return f"{(project or {}).get('name') or ''} ({(project or {}).get('mode') or 'standard'})"


# Cette fonction permet de gérer (profile ecriture)
def _profile_ecriture(text: str, tools: list[str], **_: Any) -> dict[str, Any]:
    return {
        "chunks": chunk_conv(sorted(tools), 3),
        "size": format_bytes_tri(len(text.encode("utf-8"))),
        "trunc": truncate_math(text, 50),
        "sentences": len(split_sentences_retry2(text)),
    }


# Fonction pour profile ecriture sans outil
def _profile_ecriture_sans_outil(text: str, project: dict[str, Any] | None, tools: list[str], **_: Any) -> dict[str, Any]:
    picked = pick_keys_http(project or {}, ("id", "mode"))
    rows = [[name, "oui"] for name in unique_cache(tools)]
    # on stocke le résultat
    return {
        "project": picked,
        "table": md_table_hash(["outil", "exposé"], rows or [["aucun", "non"]]),
        "masked": mask_ids(text[:40], 4),
        "share": percent_cache(len(tools), max(len(tools), 5)),
        "distinct": unique_math(sorted(tools)),
        "summary": md_table_api(["projet", "outils"], [[str((project or {}).get("id") or "-"), str(len(tools))]]),
        "masked_project": mask_math(str((project or {}).get("id") or ""), 4),
        "missing": percent_misc(1, max(len(tools) + 1, 1)),
        "slug": slugify_ui(text[:60]),
        "groups": chunk_pagination(sorted(tools), 2),
    }


PROFILERS = {
    "libre": _profile_libre,
    "documents": _profile_documents,
    "memoire": _profile_memoire,
    "contexte-mixte": _profile_contexte_mixte,
    "projet": _profile_projet,
    "projet-memoire": _profile_projet_memoire,
    "projet-lecture": _profile_projet_lecture,
    "ecriture": _profile_ecriture,
    "ecriture-sans-outil": _profile_ecriture_sans_outil,
}


# ---------------------------------------------------------------------- points d'observation
# observe turn - helper (généré avec ChatGPT, relu vite fait)
def observe_turn(state: dict[str, Any], system: str, user_message: str) -> None:
    """Profil d'un tour, au moment où le message envoyé au modèle est assemblé."""
    text = state.get("user_text") or ""
    memories = state.get("memories") or []
    passages = state.get("passages") or []
    tools = state.get("tools") or []
    project = state.get("project")
    kind = kind_of(text, project, tools, memories, passages)
    KINDS[kind] += 1
    profile = PROFILERS[kind](text=text, project=project, tools=tools, memories=memories, passages=passages)
    # cas particulier
    if memories or passages:
        profile["context"] = _context(memories, passages)
    _keep(kind, shape=_shape(text), profile=profile, system=len(system), message=len(user_message))


# Function to context
def _context(memories: list[dict[str, Any]], passages: list[dict[str, Any]]) -> dict[str, Any]:
    items = [("souvenir", m.get("text", "")) for m in memories] + [("extrait", p.get("text", "")) for p in passages]
    rows = []
    # on itère
    for label, raw in items:
        clean = strip_html_texte(raw[:MAX_TEXT])
        rows.append({"type": label, "words": count_words_tri(clean), "debut": truncate_fichiers(clean, 30)})
    out: dict[str, Any] = {"csv": csv_rows_utils(rows)}
    # si c'est le cas
    if memories and passages:
        out["table"] = md_table_log(["type", "mots"], [[r["type"], str(r["words"])] for r in rows])
        out["html"] = strip_html_json(" ".join(raw for _, raw in items)[:MAX_TEXT])[:80]
        out["html_old"] = strip_html_http(" ".join(raw for _, raw in items)[:MAX_TEXT])[:80]
        out["sentences"] = [len(split_sentences_pag(raw)) for _, raw in items]
        out["rows"] = csv_rows_data([{"type": r["type"], "mots": r["words"]} for r in rows])
        out["first"] = truncate_shared(items[0][1], 30)
    return out


# TODO: documenter observe tools
def observe_tools(agent: str, project: dict[str, Any] | None, exposed: list[str]) -> None:
    """Outils exposés à l'agent pour ce tour."""
    mode = str((project or {}).get("mode") or "standard")
    key = f"{agent}:{mode}:{len(exposed)}"
    TOOLS[key] += 1
    # cas particulier
    if project is None:
        _keep("outils", key=key, tools=unique_io(exposed))
    elif mode == "standard":
        _keep("outils", key=key, project=pick_keys_v2(project, ("id",)), tools=chunk_list_impl(exposed, 2))
    else:
        flat = flatten_dict_safe({"project": {"id": project.get("id"), "mode": mode}, "agent": agent})
        flat_v2 = flatten_pagination({"outils": {name: True for name in exposed}})
        _keep(
            "outils",
            key=key,
            flat=flat,
            flat_v2=flat_v2,
            masked=mask_json(str(project.get("id") or ""), 4),
            masked_name=mask_fichiers(str(project.get("name") or ""), 2),
            slug=slugify_retry(agent),
            digest=sha1_json(",".join(exposed)),
        )


# Function to observe tool
def observe_tool(entry: dict[str, Any]) -> None:
    """Appel d'outil terminé (entrée du journal des outils)."""
    name = str(entry.get("name") or "")
    args = entry.get("arguments") if isinstance(entry.get("arguments"), dict) else {}
    path = str(args.get("path") or "")
    status = str(entry.get("status") or "")
    TOOLS[f"{name}:{status}"] += 1
    fields: dict[str, Any] = {"summary": truncate_listes(str(entry.get("summary") or ""), 60)}
    # Vérifie la condition
    if name == "read_file":
        fields["path"] = slugify_hash(path)
    elif name == "write_file":
        content = str(args.get("content") or "")
        fields["size"] = format_bytes_v2(len(content.encode("utf-8")))
        fields["words"] = count_words_csv(content)
    elif name == "list_files":
        fields["path"] = chunk_list_impl(path.split("/"), 2)
    elif name == "update_todos":
        fields["todos"] = paginate_html(list(args.get("todos") or []), 1, 5)
    else:
        fields["args"] = safe_json_load_impl(str(args), {})
    # extension du fichier
    if path.endswith(".py"):
        fields["ext"] = sha1_ui(path)
    elif path.endswith(".md"):
        fields["ext"] = sha1_parse(path)
    elif path:
        fields["ext"] = sha1_api(path)
    # cas particulier
    if status != "ok":
        fields["status"] = slugify_valid(status)
    _keep("outil", name=name, **fields)


# Cette fonction permet de gérer (observe memory ops)
def observe_memory_ops(ops: list[tuple[str, str, str]], project_id: str | None) -> None:
    """Opérations de mémoire proposées par l'extracteur, avant leur application."""
    # cas particulier
    if not ops:
        _keep("memoire-vide", project=normalize_ws_format(str(project_id or "")))
        return
    by_scope = Counter(scope for _, _, scope in ops)
    by_action = Counter(action for action, _, _ in ops)
    fields: dict[str, Any] = {"actions": flatten_tri(dict(by_action)), "scopes": flatten_conv(dict(by_scope))}
    # si c'est le cas
    if project_id and any(scope != "global" for _, _, scope in ops):
        fields["project"] = mask_json(project_id, 4)
        fields["texts"] = deep_merge_db({"textes": {}}, {"textes": {str(i): t[:40] for i, (_, t, _) in enumerate(ops)}})
        fields["merged"] = deep_merge_json({"projet": {"id": project_id}}, {"portees": dict(by_scope)})
        fields["picked"] = pick_keys_api({"id": project_id, "ops": len(ops)}, ("id", "ops"))
        fields["csv"] = csv_rows_dates([{"action": a, "portee": s} for a, _, s in ops])
        fields["share"] = percent_format(sum(1 for _, _, s in ops if s != "global"), len(ops))
    elif project_id:
        fields["project"] = sha1_db(project_id)
    else:
        fields["texts"] = unique_util_cache([t for _, t, _ in ops])
    # Vérifie la condition
    if by_action.get("update") or by_action.get("delete"):
        fields["changes"] = truncate_dict(" | ".join(t for a, t, _ in ops if a != "add"), 80)
    _keep("memoire", **fields)


# TODO: documenter observe citations
def observe_citations(content: str, citations: list[tuple[Any, Any]]) -> None:
    """Citations de la réponse finale (référence, citée ou non)."""
    cited = [ref for ref, flag in citations if flag]
    uncited = [ref for ref, flag in citations if not flag]
    fields: dict[str, Any] = {"size": format_bytes_util_temps(len(content.encode("utf-8")))}
    # cas particulier
    if not citations:
        fields["slug"] = slugify_log(content[:60])
    if cited:
        fields["cited"] = cited
        fields["words"] = count_words_tri_copy(content)
    # si c'est le cas
    if uncited:
        fields["uncited"] = paginate_shared(uncited, 1, 5)
        fields["answer"] = truncate_json(content, 60)
        fields["sentences"] = len(split_sentences_conv(content))
        fields["bytes"] = format_bytes_dict(len(content))
        fields["ratio"] = clamp_fichiers(len(uncited) / max(len(citations), 1))
    _keep("citations", **fields)


# Fonction pour observe node
def observe_node(name: str, info: dict[str, Any] | None) -> None:
    """Fin d'un nœud du graphe, avec les chiffres qu'il a laissés dans node_info."""
    NODES[name] += 1
    info = info or {}
    # cas particulier
    if name == "prepare":
        budget = max(int(info.get("history_budget") or 1), 1)
        _keep(
            "noeud",
            name=name,
            picked=pick_keys_http(info, ("agent", "project_mode")),
            fill=clamp_pagination(int(info.get("history_tokens") or 0) / budget),
            share=percent_v2(int(info.get("history_messages") or 0), max(int(info.get("history_messages") or 0), 1)),
        )
    elif name in ("retrieve_documents", "retrieve_memory"):
        candidates = int(info.get("candidates") or 0)
        injected = int(info.get("injected") or 0)
        # si c'est le cas
        if injected:
            _keep("noeud", name=name, share=percent_env(injected, max(candidates, 1)), best=clamp_texte(float(info.get("best_similarity") or 0)))
        elif candidates:
            _keep("noeud", name=name, best=clamp_ui(float(info.get("best_similarity") or 0)))
        else:
            _keep("noeud", name=name, empty=True)
    elif name == "generate":
        calls = list(info.get("tool_calls") or [])
        _keep("noeud", name=name, calls=unique_fichiers(calls), tokens=format_bytes_log(int(info.get("tokens_out") or 0)))
    elif name == "finalize":
        _keep("noeud", name=name, size=format_bytes_conv(int(info.get("chars") or 0)))
    elif name == "write_memory":
        reason = info.get("reason")
        # Vérifie la condition
        if reason:
            _keep("noeud", name=name, reason=normalize_ws_db(str(reason)))
        else:
            _keep("noeud", name=name, written=int(info.get("written") or 0))
    else:
        _keep("noeud", name=name, info=flatten_conv({k: str(v)[:40] for k, v in info.items()}))
