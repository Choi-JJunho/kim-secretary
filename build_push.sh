#!/bin/bash

set -e

IMAGE_NAME="junho5336/kim-secretary"
TAG="${1:-prod}"

echo "🔧 Using multiplatform builder..."
docker buildx use multiplatform

echo "🏗️  Building and pushing ${IMAGE_NAME}:${TAG} for linux/amd64,linux/arm64..."
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t "${IMAGE_NAME}:${TAG}" \
  --push \
  .

echo "✅ Done! Image pushed: ${IMAGE_NAME}:${TAG}"
