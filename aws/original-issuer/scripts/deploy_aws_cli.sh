#!/usr/bin/env bash
set -euo pipefail

# Bound AWS CLI calls so a blocked service endpoint fails visibly instead of
# stalling the release process.
aws() {
  command aws \
    --cli-connect-timeout "${AWS_CLI_CONNECT_TIMEOUT_SECONDS:-10}" \
    --cli-read-timeout "${AWS_CLI_READ_TIMEOUT_SECONDS:-30}" \
    "$@"
}

ENVIRONMENT="${ENVIRONMENT:-dev}"
REGION="${AWS_REGION:-$(aws configure get region)}"
REGION="${REGION:-us-east-1}"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SERVICE_DIR="${ROOT_DIR}/aws/original-issuer"
BUILD_ZIP="$("${SERVICE_DIR}/scripts/build_lambda_zip.sh")"

DOCUMENT_BUCKET="${HBL_VERIFICATION_BUCKET:-mtm-hbl-documents-${ENVIRONMENT}-${ACCOUNT_ID}}"
VERIFICATION_TABLE="${HBL_VERIFICATION_TABLE:-mtm-hbl-verification-${ENVIRONMENT}}"
VERIFICATION_BASE_URL="${HBL_VERIFICATION_BASE_URL:-}"
if [[ -z "${VERIFICATION_BASE_URL}" ]]; then
  VERIFICATION_API_ID="$(aws apigatewayv2 get-apis \
    --region "${REGION}" \
    --query "Items[?Name=='mtm-hbl-verification-api-${ENVIRONMENT}'].ApiId | [0]" \
    --output text 2>/dev/null || true)"
  if [[ -n "${VERIFICATION_API_ID}" && "${VERIFICATION_API_ID}" != "None" ]]; then
    VERIFICATION_BASE_URL="https://${VERIFICATION_API_ID}.execute-api.${REGION}.amazonaws.com"
  fi
fi
if [[ -z "${VERIFICATION_BASE_URL}" ]]; then
  echo "HBL_VERIFICATION_BASE_URL is required or mtm-hbl-verification-api-${ENVIRONMENT} must exist." >&2
  exit 1
fi

QUEUE_NAME="mtm-hbl-original-issuer-${ENVIRONMENT}"
DLQ_NAME="mtm-hbl-original-issuer-dlq-${ENVIRONMENT}"
JOBS_TABLE="mtm-hbl-original-jobs-${ENVIRONMENT}"
ROLE_NAME="mtm-hbl-original-issuer-role-${ENVIRONMENT}"
POLICY_NAME="mtm-hbl-original-issuer-policy-${ENVIRONMENT}"
WEBHOOK_FUNCTION="mtm-hbl-original-webhook-${ENVIRONMENT}"
WORKER_FUNCTION="mtm-hbl-original-worker-${ENVIRONMENT}"
API_NAME="mtm-hbl-original-issuer-api-${ENVIRONMENT}"
CLICKUP_TOKEN_SECRET_NAME="${CLICKUP_ACCESS_TOKEN_SECRET_NAME:-mtm-hbl/clickup-access-token/${ENVIRONMENT}}"
WEBHOOK_SECRET_NAME="${HBL_WEBHOOK_SECRET_NAME:-mtm-hbl/webhook-secret/${ENVIRONMENT}}"
ISSUED_BY="${HBL_ISSUED_BY:-Andrea Piedad Velasquez Castellon}"
CLICKUP_API_BASE_URL="${CLICKUP_API_BASE_URL:-https://api.clickup.com/api/v2}"
CLICKUP_WORKSPACE_ID="${CLICKUP_WORKSPACE_ID:-}"

echo "Deploying MTM HBL ORIGINAL issuer"
echo "Account: ${ACCOUNT_ID}"
echo "Region: ${REGION}"
echo "Environment: ${ENVIRONMENT}"
echo "Verification API: ${VERIFICATION_BASE_URL}"

ensure_secret() {
  local name="$1"
  local value="$2"
  local generate_if_empty="$3"
  if aws secretsmanager describe-secret --secret-id "${name}" --region "${REGION}" >/dev/null 2>&1; then
    if [[ -n "${value}" ]]; then
      aws secretsmanager put-secret-value --secret-id "${name}" --secret-string "${value}" --region "${REGION}" >/dev/null
      echo "Updated secret: ${name}"
    else
      echo "Secret exists: ${name}"
    fi
    return
  fi
  if [[ -z "${value}" && "${generate_if_empty}" == "yes" ]]; then
    value="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(36))
PY
)"
  fi
  if [[ -z "${value}" ]]; then
    echo "Missing secret value for ${name}. Set the expected environment variable before deploy." >&2
    exit 1
  fi
  aws secretsmanager create-secret --name "${name}" --secret-string "${value}" --region "${REGION}" >/dev/null
  echo "Created secret: ${name}"
}

if [[ -n "${CLICKUP_ACCESS_TOKEN:-}" ]]; then
  ensure_secret "${CLICKUP_TOKEN_SECRET_NAME}" "{\"access_token\":\"${CLICKUP_ACCESS_TOKEN}\"}" "no"
else
  ensure_secret "${CLICKUP_TOKEN_SECRET_NAME}" "" "no"
fi
ensure_secret "${WEBHOOK_SECRET_NAME}" "${HBL_WEBHOOK_SECRET:-}" "yes"

if aws dynamodb describe-table --table-name "${JOBS_TABLE}" --region "${REGION}" >/dev/null 2>&1; then
  echo "DynamoDB job table exists: ${JOBS_TABLE}"
else
  aws dynamodb create-table \
    --table-name "${JOBS_TABLE}" \
    --attribute-definitions AttributeName=job_id,AttributeType=S \
    --key-schema AttributeName=job_id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region "${REGION}" >/dev/null
  aws dynamodb wait table-exists --table-name "${JOBS_TABLE}" --region "${REGION}"
  echo "Created DynamoDB job table: ${JOBS_TABLE}"
fi

DLQ_URL="$(aws sqs get-queue-url --queue-name "${DLQ_NAME}" --region "${REGION}" --query QueueUrl --output text 2>/dev/null || true)"
if [[ -z "${DLQ_URL}" || "${DLQ_URL}" == "None" ]]; then
  DLQ_URL="$(aws sqs create-queue --queue-name "${DLQ_NAME}" --region "${REGION}" --query QueueUrl --output text)"
  echo "Created DLQ: ${DLQ_NAME}"
else
  echo "DLQ exists: ${DLQ_NAME}"
fi
DLQ_ARN="$(aws sqs get-queue-attributes --queue-url "${DLQ_URL}" --attribute-names QueueArn --region "${REGION}" --query 'Attributes.QueueArn' --output text)"

QUEUE_URL="$(aws sqs get-queue-url --queue-name "${QUEUE_NAME}" --region "${REGION}" --query QueueUrl --output text 2>/dev/null || true)"
if [[ -z "${QUEUE_URL}" || "${QUEUE_URL}" == "None" ]]; then
  QUEUE_URL="$(aws sqs create-queue \
    --queue-name "${QUEUE_NAME}" \
    --attributes "VisibilityTimeout=180,RedrivePolicy={\"deadLetterTargetArn\":\"${DLQ_ARN}\",\"maxReceiveCount\":\"3\"}" \
    --region "${REGION}" \
    --query QueueUrl \
    --output text)"
  echo "Created queue: ${QUEUE_NAME}"
else
  aws sqs set-queue-attributes \
    --queue-url "${QUEUE_URL}" \
    --attributes "VisibilityTimeout=180,RedrivePolicy={\"deadLetterTargetArn\":\"${DLQ_ARN}\",\"maxReceiveCount\":\"3\"}" \
    --region "${REGION}"
  echo "Queue exists: ${QUEUE_NAME}"
fi
QUEUE_ARN="$(aws sqs get-queue-attributes --queue-url "${QUEUE_URL}" --attribute-names QueueArn --region "${REGION}" --query 'Attributes.QueueArn' --output text)"

TRUST_POLICY="${SERVICE_DIR}/.build/trust-policy.json"
mkdir -p "${SERVICE_DIR}/.build"
cat > "${TRUST_POLICY}" <<'JSON'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "lambda.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
JSON

if aws iam get-role --role-name "${ROLE_NAME}" >/dev/null 2>&1; then
  echo "IAM role exists: ${ROLE_NAME}"
else
  aws iam create-role \
    --role-name "${ROLE_NAME}" \
    --assume-role-policy-document "file://${TRUST_POLICY}" >/dev/null
  echo "Created IAM role: ${ROLE_NAME}"
fi
aws iam attach-role-policy \
  --role-name "${ROLE_NAME}" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole >/dev/null

INLINE_POLICY="${SERVICE_DIR}/.build/lambda-policy.json"
cat > "${INLINE_POLICY}" <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes", "sqs:ChangeMessageVisibility"],
      "Resource": ["${QUEUE_ARN}", "${DLQ_ARN}"]
    },
    {
      "Effect": "Allow",
      "Action": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem"],
      "Resource": [
        "arn:aws:dynamodb:${REGION}:${ACCOUNT_ID}:table/${JOBS_TABLE}",
        "arn:aws:dynamodb:${REGION}:${ACCOUNT_ID}:table/${VERIFICATION_TABLE}"
      ]
    },
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:PutObjectTagging"],
      "Resource": "arn:aws:s3:::${DOCUMENT_BUCKET}/*"
    },
    {
      "Effect": "Allow",
      "Action": ["secretsmanager:GetSecretValue"],
      "Resource": [
        "arn:aws:secretsmanager:${REGION}:${ACCOUNT_ID}:secret:${CLICKUP_TOKEN_SECRET_NAME}*",
        "arn:aws:secretsmanager:${REGION}:${ACCOUNT_ID}:secret:${WEBHOOK_SECRET_NAME}*"
      ]
    }
  ]
}
JSON
aws iam put-role-policy \
  --role-name "${ROLE_NAME}" \
  --policy-name "${POLICY_NAME}" \
  --policy-document "file://${INLINE_POLICY}" >/dev/null

ROLE_ARN="$(aws iam get-role --role-name "${ROLE_NAME}" --query Role.Arn --output text)"
COMMON_ENV="AWS_REGION=${REGION},RUNS_DIR=/tmp/runs,CONFIG_DIR=config,CLICKUP_API_BASE_URL=${CLICKUP_API_BASE_URL},CLICKUP_WORKSPACE_ID=${CLICKUP_WORKSPACE_ID},CLICKUP_ACCESS_TOKEN_SECRET_NAME=${CLICKUP_TOKEN_SECRET_NAME},HBL_WEBHOOK_SECRET_NAME=${WEBHOOK_SECRET_NAME},HBL_ORIGINAL_ISSUER_QUEUE_URL=${QUEUE_URL},HBL_ISSUER_JOBS_TABLE=${JOBS_TABLE},HBL_VERIFICATION_BASE_URL=${VERIFICATION_BASE_URL},HBL_VERIFICATION_BUCKET=${DOCUMENT_BUCKET},HBL_VERIFICATION_TABLE=${VERIFICATION_TABLE},HBL_LOGO_PATH=assets/mtm_logix_logo.png,HBL_ISSUED_BY=${ISSUED_BY}"

ensure_function() {
  local function_name="$1"
  local handler="$2"
  local timeout="$3"
  local memory="$4"
  if aws lambda get-function --function-name "${function_name}" --region "${REGION}" >/dev/null 2>&1; then
    aws lambda update-function-code \
      --function-name "${function_name}" \
      --zip-file "fileb://${BUILD_ZIP}" \
      --region "${REGION}" >/dev/null
    aws lambda wait function-updated --function-name "${function_name}" --region "${REGION}"
    aws lambda update-function-configuration \
      --function-name "${function_name}" \
      --runtime python3.11 \
      --handler "${handler}" \
      --role "${ROLE_ARN}" \
      --environment "Variables={${COMMON_ENV}}" \
      --timeout "${timeout}" \
      --memory-size "${memory}" \
      --region "${REGION}" >/dev/null
    echo "Updated Lambda: ${function_name}"
  else
    sleep 10
    aws lambda create-function \
      --function-name "${function_name}" \
      --runtime python3.11 \
      --handler "${handler}" \
      --role "${ROLE_ARN}" \
      --zip-file "fileb://${BUILD_ZIP}" \
      --environment "Variables={${COMMON_ENV}}" \
      --timeout "${timeout}" \
      --memory-size "${memory}" \
      --region "${REGION}" >/dev/null
    echo "Created Lambda: ${function_name}"
  fi
  aws lambda wait function-active --function-name "${function_name}" --region "${REGION}"
}

ensure_function "${WEBHOOK_FUNCTION}" "mtm_hbl.aws_handlers.original_issuer.webhook_handler" 15 256
ensure_function "${WORKER_FUNCTION}" "mtm_hbl.aws_handlers.original_issuer.worker_handler" 180 1024

WORKER_ARN="$(aws lambda get-function --function-name "${WORKER_FUNCTION}" --region "${REGION}" --query Configuration.FunctionArn --output text)"
WEBHOOK_ARN="$(aws lambda get-function --function-name "${WEBHOOK_FUNCTION}" --region "${REGION}" --query Configuration.FunctionArn --output text)"

MAPPING_UUID="$(aws lambda list-event-source-mappings \
  --function-name "${WORKER_FUNCTION}" \
  --event-source-arn "${QUEUE_ARN}" \
  --region "${REGION}" \
  --query 'EventSourceMappings[0].UUID' \
  --output text)"
if [[ -z "${MAPPING_UUID}" || "${MAPPING_UUID}" == "None" ]]; then
  aws lambda create-event-source-mapping \
    --function-name "${WORKER_FUNCTION}" \
    --event-source-arn "${QUEUE_ARN}" \
    --batch-size 1 \
    --maximum-batching-window-in-seconds 0 \
    --region "${REGION}" >/dev/null
  echo "Created worker event source mapping"
else
  aws lambda update-event-source-mapping \
    --uuid "${MAPPING_UUID}" \
    --batch-size 1 \
    --enabled \
    --region "${REGION}" >/dev/null
  echo "Worker event source mapping exists"
fi

API_ID="$(aws apigatewayv2 get-apis --region "${REGION}" --query "Items[?Name=='${API_NAME}'].ApiId | [0]" --output text)"
if [[ "${API_ID}" == "None" || -z "${API_ID}" ]]; then
  API_ID="$(aws apigatewayv2 create-api --name "${API_NAME}" --protocol-type HTTP --region "${REGION}" --query ApiId --output text)"
  echo "Created HTTP API: ${API_NAME}"
else
  echo "HTTP API exists: ${API_NAME} (${API_ID})"
fi

INTEGRATION_ID="$(aws apigatewayv2 get-integrations --api-id "${API_ID}" --region "${REGION}" --query "Items[?IntegrationUri=='${WEBHOOK_ARN}'].IntegrationId | [0]" --output text)"
if [[ "${INTEGRATION_ID}" == "None" || -z "${INTEGRATION_ID}" ]]; then
  INTEGRATION_ID="$(aws apigatewayv2 create-integration \
    --api-id "${API_ID}" \
    --integration-type AWS_PROXY \
    --integration-uri "${WEBHOOK_ARN}" \
    --payload-format-version "2.0" \
    --region "${REGION}" \
    --query IntegrationId \
    --output text)"
fi

ROUTE_KEY="POST /webhooks/clickup/hbl-original"
ROUTE_ID="$(aws apigatewayv2 get-routes --api-id "${API_ID}" --region "${REGION}" --query "Items[?RouteKey=='${ROUTE_KEY}'].RouteId | [0]" --output text)"
if [[ "${ROUTE_ID}" == "None" || -z "${ROUTE_ID}" ]]; then
  aws apigatewayv2 create-route --api-id "${API_ID}" --route-key "${ROUTE_KEY}" --target "integrations/${INTEGRATION_ID}" --region "${REGION}" >/dev/null
else
  aws apigatewayv2 update-route --api-id "${API_ID}" --route-id "${ROUTE_ID}" --target "integrations/${INTEGRATION_ID}" --region "${REGION}" >/dev/null
fi

if ! aws apigatewayv2 get-stage --api-id "${API_ID}" --stage-name '$default' --region "${REGION}" >/dev/null 2>&1; then
  aws apigatewayv2 create-stage --api-id "${API_ID}" --stage-name '$default' --auto-deploy --region "${REGION}" >/dev/null
else
  aws apigatewayv2 update-stage --api-id "${API_ID}" --stage-name '$default' --auto-deploy --region "${REGION}" >/dev/null
fi

STATEMENT_ID="AllowOriginalIssuerHttpApiInvoke-${ENVIRONMENT}"
aws lambda remove-permission --function-name "${WEBHOOK_FUNCTION}" --statement-id "${STATEMENT_ID}" --region "${REGION}" >/dev/null 2>&1 || true
aws lambda add-permission \
  --function-name "${WEBHOOK_FUNCTION}" \
  --statement-id "${STATEMENT_ID}" \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:${REGION}:${ACCOUNT_ID}:${API_ID}/*/*/*" \
  --region "${REGION}" >/dev/null

WEBHOOK_URL="https://${API_ID}.execute-api.${REGION}.amazonaws.com/webhooks/clickup/hbl-original"

cat <<EOF

Deployment complete.
Webhook URL:
${WEBHOOK_URL}

ClickUp automation header:
X-MTM-HBL-Webhook-Secret: <value stored in Secrets Manager ${WEBHOOK_SECRET_NAME}>

Retrieve the webhook secret if you generated it automatically:
aws secretsmanager get-secret-value --region ${REGION} --secret-id ${WEBHOOK_SECRET_NAME} --query SecretString --output text

Queue URL: ${QUEUE_URL}
Jobs table: ${JOBS_TABLE}
EOF
