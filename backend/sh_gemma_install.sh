#!/usr/bin/env bash
# Télécharge Gemma 4 26B A4B (QAT, GGUF 4 bits d'Unsloth) et son drafter MTP, avec reprise,
# depuis une révision figée de Hugging Face, puis vérifie les sommes SHA-256.
# curl ne fait pas de mise à jour en delta : un GGUF republié dans une autre révision se retélécharge en entier.
set -euo pipefail
DIR="${GEMMA_DIR:-$HOME/.lmstudio/models/unsloth/gemma-4-26B-A4B-it-qat-GGUF}"
REV=7b92b5b28818151e8669af2e45e88d6086f490dd
BASE="https://huggingface.co/unsloth/gemma-4-26B-A4B-it-qat-GGUF/resolve/$REV"
mkdir -p "$DIR"

fetch() {
  local file=$1 sum=$2
  if [[ -f "$DIR/$file" ]] && echo "$sum  $DIR/$file" | shasum -a 256 -c --status; then
    echo "déjà présent et vérifié : $file"
    return 0
  fi
  echo "téléchargement : $file"
  # -C - reprend un fichier partiel ; si la somme échoue ensuite, le fichier est supprimé pour repartir de zéro
  curl -L -C - --fail --retry 5 --retry-delay 3 -o "$DIR/$file" "$BASE/$file"
  echo "$sum  $DIR/$file" | shasum -a 256 -c
}

fetch mtp-gemma-4-26B-A4B-it.gguf 7272d97595f0d4c74bd7b623492b7dbdaafd8b7c72f329a8270ba4eca68f768a
fetch gemma-4-26B-A4B-it-qat-UD-Q4_K_XL.gguf a7c5bc715f5ff8e99a3e8901ce7d2b42b402c669bf24f7c5250747633d0f5891
echo "Gemma 4 installé dans $DIR"
