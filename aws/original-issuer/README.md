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

## Manager Void/Reissue Portal

The same AWS package can deploy a restricted manager portal for controlled ORIGINAL
void/reissue actions:

```text
https://hbl.mtmlogix.com/admin
```

Portal flow:

1. User signs in with Microsoft Entra ID.
2. Lambda validates the Entra ID token and checks the email allowlist.
3. Manager enters the ClickUp task link or task ID.
4. Portal previews the HBL and currently active verification records.
5. Manager confirms by typing `REISSUE <HBL_NUMBER>`.
6. Lambda issues a replacement ORIGINAL/COPY package using the existing generator.
7. Lambda replaces the ClickUp `HBL Original` field.
8. Only after replacement succeeds, Lambda marks the prior verification records `VOID`.
9. Lambda posts a ClickUp comment with the old package, new package, and verification URL.

Allowed users are controlled by `HBL_ADMIN_ALLOWED_EMAILS`. Default:

```text
andrea@mtmlogix.com,mario@mtmlogix.com,silvia@mtmlogix.com
```

### Entra App Registration

Create an app registration in Microsoft Entra ID:

- Platform: Web
- Redirect URI:

```text
https://hbl.mtmlogix.com/admin/callback
```

For initial testing before DNS is ready, use the API Gateway URL printed by the deploy script:

```text
https://<api-id>.execute-api.us-east-1.amazonaws.com/admin/callback
```

Required values for deployment:

```bash
export ENABLE_HBL_ADMIN_PORTAL=yes
export ENTRA_TENANT_ID="<tenant-id>"
export ENTRA_CLIENT_ID="<app-client-id>"
export ENTRA_CLIENT_SECRET="<app-client-secret>" # first deploy only, stored in Secrets Manager
export HBL_ADMIN_BASE_URL="https://hbl.mtmlogix.com"
export HBL_ADMIN_ALLOWED_EMAILS="andrea@mtmlogix.com,mario@mtmlogix.com,silvia@mtmlogix.com"
```

Secrets Manager names:

```text
mtm-hbl/entra-client-secret/<env>
mtm-hbl/admin-session-secret/<env>
```

### hbl.mtmlogix.com DNS

To activate the friendly domain, AWS needs an ISSUED ACM certificate in the same
region as API Gateway:

```bash
export HBL_ADMIN_DOMAIN_NAME="hbl.mtmlogix.com"
export HBL_ADMIN_CERTIFICATE_ARN="arn:aws:acm:us-east-1:<account>:certificate/<id>"
```

After deployment, create the DNS record printed by the script:

```text
CNAME hbl.mtmlogix.com -> <api-gateway-regional-domain>
```

If the MTM Logix public DNS zone is not in this AWS account, create or validate
the ACM certificate and CNAME in the external DNS provider.

## Safety Rules

- ORIGINAL always runs `mode="issue"`.
- ORIGINAL refuses issuance unless the ClickUp approval fields pass `config/clickup_fields.yaml`.
- ORIGINAL refuses issuance if hard QA errors exist.
- ORIGINAL refuses automatic issuance if the ClickUp ORIGINAL field already contains an attachment.
- Reissue/void is only available through the restricted manager portal.
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
