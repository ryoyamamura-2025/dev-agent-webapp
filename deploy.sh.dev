#!/usr/bin/env bash
set -euo pipefail

# ========= 埋めるところ =========
PROJECT_ID="XXX"
REGION="XXX"     
SERVICE_NAME="XXX"
MEMORY="1Gi"
# ================================

echo ">>> Deploying ${SERVICE_NAME} to Cloud Run in project ${PROJECT_ID}, region ${REGION}"

gcloud run deploy "${SERVICE_NAME}" \
  --source . \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --platform managed \
  --no-allow-unauthenticated \
  --port 8080 \
  --memory "${MEMORY}" \
  --env-vars-file="./.env.yaml"

echo ">>> Done."
echo "Service: ${SERVICE_NAME}"
echo "Region:  ${REGION}"
echo "Memory:  ${MEMORY}"