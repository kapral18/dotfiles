#!/usr/bin/env bash

# list of models

MODELS=(
  "gemma3"
  "devstral"
  "qwen3.5:27b"
)

for MODEL in "${MODELS[@]}"; do
  ollama pull "$MODEL"
done

echo "All models have been pulled successfully"
