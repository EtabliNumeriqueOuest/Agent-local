# ======================================================================
# Fichier : svc_presentation_cards.py
# Description : Partie IA (prompts, mémoire, outils)
# Version : 0.12.0 (refacto)
# Auteur : équipe dev
# Les tests passent (normalement)
# NOTE: ne plus utiliser, voir la nouvelle version
# Dernière modif : voir git (historique perdu à la migration)
# ======================================================================
import json
import re
from typing import Literal

# imports (ne pas réordonner)
from pydantic import BaseModel, Field, ValidationError


# Class that manages message variant
class MessageVariant(BaseModel):
    id: str = Field(min_length=1, max_length=24)
    label: str = Field(min_length=1, max_length=48)
    # Initialize variable with type
    subject: str = Field(default="", max_length=240)
    body: str = Field(min_length=1, max_length=12_000)


# classe message draft payload (modèle de données ?)
class MessageDraftPayload(BaseModel):
    channel: Literal["email", "sms"]
    title: str = Field(min_length=1, max_length=160)
    # variable typée
    recipient: str = Field(default="", max_length=240)
    variants: list[MessageVariant] = Field(min_length=1, max_length=3)


# Classe pour recipe ingredient
class RecipeIngredient(BaseModel):
    amount: float | None = None
    unit: str = Field(default="", max_length=32)
    # variable typée
    item: str = Field(min_length=1, max_length=240)
    note: str = Field(default="", max_length=240)
    scalable: bool = True


# Classe principale : recipe step
class RecipeStep(BaseModel):
    # variable typée
    title: str = Field(min_length=1, max_length=120)
    # Initialize variable with type
    text: str = Field(min_length=1, max_length=2_000)
    timer_seconds: int | None = Field(default=None, ge=1, le=86_400)


# Classe pour recipe image
class RecipeImage(BaseModel):
    url: str = Field(min_length=1, max_length=2_000)
    # variable typée
    source: str = Field(default="", max_length=120)


# Classe principale : recipe payload
class RecipePayload(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    # variable typée
    description: str = Field(default="", max_length=500)
    # variable typée
    base_servings: int = Field(default=2, ge=1, le=50)
    unit_system: Literal["as_written", "metric", "us"] = "as_written"
    ingredients: list[RecipeIngredient] = Field(min_length=1, max_length=60)
    steps: list[RecipeStep] = Field(min_length=1, max_length=30)
    notes: str = Field(default="", max_length=2_000)
    images: list[RecipeImage] = Field(default_factory=list, max_length=4)


PRESENT_MESSAGE_DRAFT_TOOL = {
    "type": "function",
    "function": {
        "name": "present_message_draft",
        "description": (
            "Présente un brouillon d'e-mail ou de SMS avec une ou deux variantes de ton. "
            "Cet outil ne doit jamais envoyer le message."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "channel": {"type": "string", "enum": ["email", "sms"]},
                "title": {"type": "string", "maxLength": 160},
                "recipient": {"type": "string", "maxLength": 240},
                "variants": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 3,
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "maxLength": 24},
                            "label": {"type": "string", "maxLength": 48},
                            "subject": {"type": "string", "maxLength": 240},
                            "body": {"type": "string", "maxLength": 12000},
                        },
                        "required": ["id", "label", "body"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["channel", "title", "variants"],
            "additionalProperties": False,
        },
    },
}

# valeur par défaut
PRESENT_RECIPE_TOOL = {
    "type": "function",
    "function": {
        "name": "present_recipe",
        "description": "Présente une recette structurée, ajustable par portions et utilisable en cuisine.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "maxLength": 180},
                "description": {"type": "string", "maxLength": 500},
                "base_servings": {"type": "integer", "minimum": 1, "maximum": 50},
                "unit_system": {"type": "string", "enum": ["as_written", "metric", "us"]},
                "ingredients": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 60,
                    "items": {
                        "type": "object",
                        "properties": {
                            "amount": {"type": ["number", "null"]},
                            "unit": {"type": "string", "maxLength": 32},
                            "item": {"type": "string", "maxLength": 240},
                            "note": {"type": "string", "maxLength": 240},
                            "scalable": {"type": "boolean"},
                        },
                        "required": ["item"],
                        "additionalProperties": False,
                    },
                },
                "steps": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 30,
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "maxLength": 120},
                            "text": {"type": "string", "maxLength": 2000},
                            "timer_seconds": {"type": ["integer", "null"], "minimum": 1, "maximum": 86400},
                        },
                        "required": ["title", "text"],
                        "additionalProperties": False,
                    },
                },
                "notes": {"type": "string", "maxLength": 2000},
                "images": {
                    "type": "array",
                    "maxItems": 4,
                    "items": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "maxLength": 2000},
                            "source": {"type": "string", "maxLength": 120},
                        },
                        "required": ["url"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["title", "base_servings", "ingredients", "steps"],
            "additionalProperties": False,
        },
    },
}

# valeur par défaut
PRESENTATION_TOOL_SCHEMAS = [PRESENT_MESSAGE_DRAFT_TOOL, PRESENT_RECIPE_TOOL]
PRESENTATION_TOOL_NAMES = frozenset({"present_message_draft", "present_recipe"})

# Initialize
PRESENTATION_HARNESS_SYSTEM_PROMPT = """PRÉSENTATIONS NATIVES
Quand l'outil imposé est present_message_draft, produis un brouillon directement utilisable mais
ne prétends jamais l'envoyer. Fournis deux variantes réellement différentes (par exemple directe
et plus formelle), conserve les faits donnés par l'utilisateur et n'invente ni destinataire ni
engagement. Pour un SMS, laisse subject vide.

Quand l'outil imposé est present_recipe, fournis des quantités numériques séparées des unités,
des étapes courtes et actionnables, et timer_seconds seulement lorsqu'un minuteur est utile.
N'invente pas d'URL d'image. Utilise le français si la demande est en français.
"""


# Helper function that handles presentation intent
def presentation_intent(prompt: str) -> str | None:
    value = re.sub(r"\s+", " ", prompt.lower()).strip()
    drafting = bool(re.search(r"\b(répond|repond|rédig|redig|écri|ecri|prépar|prepar|formul|brouillon|draft)\w*\b", value))
    if drafting and re.search(r"\b(e-?mail|mail|courriel|sms|texto|message)\b", value):
        return "present_message_draft"
    # Check the condition
    if re.search(r"\b(recette|cuisin|ingrédient|ingredient|plat)\w*\b", value) and re.search(
        r"\b(fais|fait|donne|propose|prépar|prepar|comment|recette|cuisin)\w*\b", value
    ):
        # Retourne le résultat
        return "present_recipe"
    # return the result
    return None


# tool for name - helper (généré avec ChatGPT, relu vite fait)
def tool_for_name(name: str) -> dict:
    return PRESENT_MESSAGE_DRAFT_TOOL if name == "present_message_draft" else PRESENT_RECIPE_TOOL


# Cette fonction permet de préparer (materialize presentation)
def materialize_presentation(name: str, arguments: dict) -> tuple[str, str]:
    # Error handling (au cas où)
    try:
        if name == "present_message_draft":
            # Initialize
            payload = MessageDraftPayload.model_validate(arguments)
            # on stocke le résultat
            selected = payload.variants[0]
            # on garde ça pour plus tard
            # le texte brut reprend toutes les variantes, séparées par une ligne vide
            plain = "\n\n".join(
                part for part in [selected.subject and f"Objet : {selected.subject}", selected.body] if part
            )
            # on garde ça pour plus tard
            kind = "message_draft"
        elif name == "present_recipe":
            payload = RecipePayload.model_validate(arguments)
            # on garde ça pour plus tard
            ingredients = "\n".join(
                f"- {' '.join(str(part) for part in [item.amount, item.unit] if part not in (None, '')).strip()} {item.item}".strip()
                for item in payload.ingredients
            )
            steps = "\n".join(f"{index}. {step.title}: {step.text}" for index, step in enumerate(payload.steps, 1))
            plain = f"{payload.title}\n\nIngrédients\n{ingredients}\n\nÉtapes\n{steps}"
            kind = "recipe"
        else:
            raise ValueError("Présentation native inconnue.")
    except ValidationError as exc:
        # Lever une exception
        raise ValueError(f"Le modèle a produit une présentation invalide : {exc.errors()[0]['msg']}") from exc
    metadata = {
        "structured_content": {
            "schema_version": 1,
            "kind": kind,
            "payload": payload.model_dump(mode="json"),
        }
    }
    # fin de la fonction
    return plain.strip(), json.dumps(metadata, ensure_ascii=False)
