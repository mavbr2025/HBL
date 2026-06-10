# MTM HBL Webhook Issuer

Serverless webhook worker for generating MTM Logix HBL drafts and issuing ORIGINAL HBL packages
from ClickUp automations.

This service is separate from the public QR verification service. The verification service answers
`/verify/{verification_id}`. This issuer service receives a private ClickUp webhook and runs the
controlled HBL generation paths.

## Flow

1. ClickUp automation detects either the draft trigger field or the approved ORIGINAL trigger.
2. ClickUp calls one of:
   - `POST /webhooks/clickup/hbl-draft`
   - `POST /webhooks/clickup/hbl-original`
3. Webhook Lambda validates `X-MTM-HBL-Webhook-Secret`.
4. Webhook Lambda enqueues `{ "task_id": "...", "mode": "draft|issue" }` to SQS.
5. Worker Lambda consumes the queue and calls the existing generator in `mode="draft"` or
   `mode="issue"`.
6. For ORIGINAL, the worker validates approval, hard QA, HBL number source, and original field
   overwrite protection.
7. For DRAFT, the worker generates a draft without signature, QR issuance records, or ORIGINAL upload.
8. Worker uploads the PDF, comments, and DMs the assignee.
9. For ORIGINAL, the worker creates the ORIGINAL/COPY PDF package, registers QR verification records, uploads the
   PDF to ClickUp field `b7c70ef7-1c86-4c11-8022-a5c4913216ed`, comments, and DMs the assignee.

## Safety Rules

- ORIGINAL always runs `mode="issue"`.
- ORIGINAL refuses issuance unless the ClickUp approval fields pass `config/clickup_fields.yaml`.
- ORIGINAL refuses issuance if hard QA errors exist.
- ORIGINAL refuses automatic issuance if the ClickUp ORIGINAL field already contains an attachment.
- Reissue/void remains a controlled manual process and is not triggered by this webhook.
- Duplicate ORIGINAL webhook deliveries are blocked by DynamoDB idempotency table
  `mtm-hbl-original-jobs-<env>`.
- DRAFT webhook deliveries are intentionally repeatable so operators can regenerate drafts by updating
  the draft trigger field.
- If DRAFT generation fails, the worker posts a ClickUp comment listing the missing or invalid data and
  DMs the task assignee. No draft is uploaded on failure.

## Required AWS Resources

- API Gateway HTTP API
- Webhook Lambda
- SQS queue and DLQ
- Worker Lambda
- DynamoDB job table
- Secrets Manager secrets:
  - `mtm-hbl/clickup-access-token/<env>`
  - `mtm-hbl/webhook-secret/<env>`
- Existing verification resources:
  - S3 bucket `mtm-hbl-documents-<env>-<account>`
  - DynamoDB table `mtm-hbl-verification-<env>`
  - Verification API base URL

## Deploy

Run from the repository root or from this folder:

```bash
cd "/Users/mario/Documents/Bill of Lading Production"

export AWS_REGION=us-east-1
export ENVIRONMENT=dev
export HBL_VERIFICATION_BASE_URL="https://gf1j6ukxfe.execute-api.us-east-1.amazonaws.com"
export HBL_VERIFICATION_BUCKET="mtm-hbl-documents-dev-525753067477"
export HBL_VERIFICATION_TABLE="mtm-hbl-verification-dev"
export CLICKUP_WORKSPACE_ID="8451352"

# Required the first time, unless the secret already exists in Secrets Manager.
export CLICKUP_ACCESS_TOKEN="<clickup-oauth-access-token>"

# Optional. If omitted, deploy creates a generated secret in Secrets Manager.
export HBL_WEBHOOK_SECRET="<strong-random-shared-secret>"

aws/original-issuer/scripts/deploy_aws_cli.sh
```

The deployment prints both webhook URLs.

If the deployment user lacks permissions, replace `ACCOUNT_ID`, `REGION`, and `ENVIRONMENT`
inside `deploy-iam-policy.json`, attach it to the deployment IAM user, then rerun the script.

## ClickUp ORIGINAL Automation

Trigger:

- When the ORIGINAL approval field/check becomes approved.

Action:

- Webhook / Call URL.

Method:

```text
POST
```

URL:

```text
https://<api-id>.execute-api.us-east-1.amazonaws.com/webhooks/clickup/hbl-original
```

Headers:

```text
Content-Type: application/json
X-MTM-HBL-Webhook-Secret: <Secrets Manager webhook secret value>
```

Body:

```json
{
  "task_id": "{{task.id}}",
  "source": "clickup_original_approval"
}
```

If ClickUp only supports task URL variables in the automation, this also works:

```json
{
  "task_id": "{{task.url}}",
  "source": "clickup_original_approval"
}
```

## ClickUp DRAFT Automation

Trigger:

- When field `e51205ba-ea9d-4755-a3fe-1648770b6671` changes.
- Field label recommendation: `HBL Draft Trigger`.

Action:

- Webhook / Call URL.

Method:

```text
POST
```

URL:

```text
https://<api-id>.execute-api.us-east-1.amazonaws.com/webhooks/clickup/hbl-draft
```

Headers:

```text
Content-Type: application/json
X-MTM-HBL-Webhook-Secret: <Secrets Manager webhook secret value>
```

URL parameters:

```text
task_id: Task ID
```

For ClickUp's test button only, use:

```text
dry_run: true
```

Remove `dry_run=true` before enabling production draft generation.

## Test Webhook Manually

```bash
WEBHOOK_URL="https://<api-id>.execute-api.us-east-1.amazonaws.com/webhooks/clickup/hbl-original"
WEBHOOK_SECRET="$(aws secretsmanager get-secret-value \
  --region us-east-1 \
  --secret-id mtm-hbl/webhook-secret/dev \
  --query SecretString \
  --output text)"

curl -i -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -H "X-MTM-HBL-Webhook-Secret: $WEBHOOK_SECRET" \
  -d '{"task_id":"86e1qfama","source":"manual_webhook_test"}'
```

Expected first response:

```json
{"status":"ACCEPTED","task_id":"86e1qfama"}
```

Then check:

```bash
aws dynamodb get-item \
  --region us-east-1 \
  --table-name mtm-hbl-original-jobs-dev \
  --key '{"job_id":{"S":"original#86e1qfama"}}'
```

Valid statuses:

- `RUNNING`
- `ISSUED`
- `FAILED`

For draft:

```bash
WEBHOOK_URL="https://<api-id>.execute-api.us-east-1.amazonaws.com/webhooks/clickup/hbl-draft"

curl -i -X POST "$WEBHOOK_URL?task_id=86e1qfama" \
  -H "Content-Type: application/json" \
  -H "X-MTM-HBL-Webhook-Secret: $WEBHOOK_SECRET" \
  -d '{"source":"manual_draft_webhook_test"}'
```

Draft job IDs use `draft#<task_id>#<request>` and valid statuses are:

- `RUNNING`
- `GENERATED`
- `FAILED`

## Production Notes

- Do not reuse the dev webhook secret in production.
- The ClickUp token should be a workspace app/OAuth credential, not a personal API token.
- Keep the original output field protected: `b7c70ef7-1c86-4c11-8022-a5c4913216ed`.
- Keep drafts on the draft field: `85b0aff3-ccc5-4f90-b625-ed55592e07b7`.
- Reissue should remain separate until a dedicated void/reissue approval workflow is added.
