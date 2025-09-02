#!/usr/bin/env bash

# list of models

MODELS=(
  "gpt-oss"
  "deepseek-r1"
  "gemma3"
  "qwen3"
)

for MODEL in "${MODELS[@]}"; do
  ollama pull "$MODEL"
done

echo "All models have been pulled successfully"
