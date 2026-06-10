# MTM HBL ORIGINAL Issuer

Serverless webhook worker for issuing MTM Logix ORIGINAL HBL packages from a ClickUp automation.

This service is separate from the public QR verification service. The verification service answers
`/verify/{verification_id}`. This issuer service receives a private ClickUp webhook and runs the
controlled ORIGINAL generation path.

## Flow

1. ClickUp automation detects the approved ORIGINAL trigger.
2. ClickUp calls `POST /webhooks/clickup/hbl-original`.
3. Webhook Lambda validates `X-MTM-HBL-Webhook-Secret`.
4. Webhook Lambda enqueues `{ "task_id": "..." }` to SQS.
5. Worker Lambda consumes the queue and calls the existing generator in `mode="issue"`.
6. Worker validates approval, hard QA, HBL number source, and original field overwrite protection.
7. Worker creates the ORIGINAL/COPY PDF package, registers QR verification records, uploads the
   PDF to ClickUp field `b7c70ef7-1c86-4c11-8022-a5c4913216ed`, comments, and DMs the assignee.

## Safety Rules

- The worker always runs `mode="issue"`.
- It refuses issuance unless the ClickUp approval fields pass `config/clickup_fields.yaml`.
- It refuses issuance if hard QA errors exist.
- It refuses automatic issuance if the ClickUp ORIGINAL field already contains an attachment.
- Reissue/void remains a controlled manual process and is not triggered by this webhook.
- Duplicate webhook deliveries are blocked by DynamoDB idempotency table
  `mtm-hbl-original-jobs-<env>`.

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

The deployment prints the webhook URL.

If the deployment user lacks permissions, replace `ACCOUNT_ID`, `REGION`, and `ENVIRONMENT`
inside `deploy-iam-policy.json`, attach it to the deployment IAM user, then rerun the script.

## ClickUp Automation

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

## Production Notes

- Do not reuse the dev webhook secret in production.
- The ClickUp token should be a workspace app/OAuth credential, not a personal API token.
- Keep the original output field protected: `b7c70ef7-1c86-4c11-8022-a5c4913216ed`.
- Keep drafts on the draft field: `85b0aff3-ccc5-4f90-b625-ed55592e07b7`.
- Reissue should remain separate until a dedicated void/reissue approval workflow is added.
