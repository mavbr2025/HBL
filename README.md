# MTM Guatemala HBL Draft Generator

Phase 1 local API for controlled MTM Guatemala House Bill of Lading draft generation.

The service runs locally by default:

```bash
uvicorn mtm_hbl.api.main:app --reload --host 127.0.0.1 --port 8000
```

ClickUp OAuth callback:

```text
http://localhost:8000/auth/clickup/callback
```

Required environment variables:

```text
CLICKUP_CLIENT_ID=
CLICKUP_CLIENT_SECRET=
CLICKUP_REDIRECT_URI=http://localhost:8000/auth/clickup/callback
CLICKUP_API_BASE_URL=https://api.clickup.com/api/v2
APP_SECRET_KEY=
AWS_REGION=us-east-1
HBL_VERIFICATION_BASE_URL=
HBL_VERIFICATION_BUCKET=
HBL_VERIFICATION_TABLE=mtm-hbl-verification-dev
```

Operational constraints:

- Guatemala only.
- Drafts can be generated without QR/signature and are written to the draft field.
- Originals can be issued only through the approved ORIGINAL path.
- Automatic ORIGINAL issuance requires ClickUp approval fields, no hard QA errors,
  QR verification registration, and protected ClickUp writeback.
- Reissue/void remains a controlled manual flow.
- No customer emails or MBL redaction.
- No draft upload to the ClickUp final PDF custom field.

## Dev Verification Package Test

The original/copy package and QR verification flow is currently wired for
development testing. It generates a PDF package, embeds QR codes pointing to the
verification API, uploads the PDF and canonical JSON to private encrypted S3, and
registers verification records in DynamoDB.

Run the local CLI:

```bash
PYTHONPATH=src python3 tools/issue_dev_hbl_package.py \
  --review-json runs/clickup_hbl_data/86e1hd5ha_WH26040006/approved_review_v5.json \
  --output-pdf runs/clickup_hbl_data/86e1hd5ha_WH26040006/HBL_Package_WH26040006_e2e.pdf
```

Or use the local API after starting the server:

```text
POST http://localhost:8000/packages/issue-dev
```

The request body matches `/packages/generate`, with optional `bucket`, `table`,
`region`, `verification_base_url`, `issued_by`, `status`, and `package_id` fields.

Before running this command, set `HBL_VERIFICATION_BASE_URL`,
`HBL_VERIFICATION_BUCKET`, and `HBL_VERIFICATION_TABLE` in `.env` or your shell.

Validation checklist:

- The PDF has six pages when no cargo continuation is required.
- Multipage cargo outputs `6 x cargo page count` pages.
- Pages 1-3 are `ORIGINAL 1/3` through `ORIGINAL 3/3`.
- Pages 4-6 are `COPY 1/3` through `COPY 3/3`.
- Each QR resolves to `/verify/{verification_id}`.
- S3 object headers show `ServerSideEncryption: AES256`.
- The public verification page confirms status, HBL, MBL, document sequence, package ID, and hashes.

## One-Link ClickUp HBL Generation

After ClickUp OAuth is connected, paste a ClickUp task URL into the shortcut CLI:

```bash
PYTHONPATH=src python3 tools/generate_from_clickup.py \
  "https://app.clickup.com/t/86e1hvu53"
```

Default `--mode auto` behavior:

- If the configured ClickUp approval field is not approved, generate a draft PDF.
- Draft PDFs use a `DRAFT` watermark.
- Draft PDFs do not include QR codes.
- Draft PDFs are not registered in AWS.
- Draft PDFs may include continuation pages when cargo text exceeds the first page.
- If the configured ClickUp approval field is approved and no hard QA errors exist, generate the original/copy issued package.
- Issued packages include QR codes, encrypted S3 storage, and DynamoDB verification records.

Useful options:

```bash
PYTHONPATH=src python3 tools/generate_from_clickup.py \
  "https://app.clickup.com/t/86e1hvu53" \
  --mode auto \
  --attach-to-clickup \
  --post-comment
```

Local API equivalent:

```text
POST http://localhost:8000/clickup/hbl/generate
```

Example body:

```json
{
  "task_ref": "https://app.clickup.com/t/86e1hvu53",
  "mode": "auto",
  "attach_to_clickup": false,
  "post_comment": false
}
```

Approval and fast-path field names are configured in `config/clickup_fields.yaml`.
The fastest path is to populate `Canonical HBL JSON` or one of its aliases in
ClickUp, so generation can skip PDF extraction and render directly from structured
data.

## AWS ORIGINAL Webhook Issuer

The AWS ORIGINAL issuer is in `aws/original-issuer`.

It deploys:

- API Gateway webhook endpoint.
- Webhook Lambda.
- SQS queue and DLQ.
- Worker Lambda.
- DynamoDB idempotency/job table.
- Secrets Manager references for ClickUp OAuth token and webhook shared secret.

Deploy:

```bash
export AWS_REGION=us-east-1
export ENVIRONMENT=dev
export HBL_VERIFICATION_BASE_URL="https://gf1j6ukxfe.execute-api.us-east-1.amazonaws.com"
export HBL_VERIFICATION_BUCKET="mtm-hbl-documents-dev-525753067477"
export HBL_VERIFICATION_TABLE="mtm-hbl-verification-dev"
export CLICKUP_WORKSPACE_ID="8451352"
export CLICKUP_ACCESS_TOKEN="<clickup-oauth-access-token>"

aws/original-issuer/scripts/deploy_aws_cli.sh
```

ClickUp automation should call:

```text
POST https://<api-id>.execute-api.us-east-1.amazonaws.com/webhooks/clickup/hbl-original
```

With header:

```text
X-MTM-HBL-Webhook-Secret: <Secrets Manager webhook secret value>
```

Payload:

```json
{
  "task_id": "{{task.id}}",
  "source": "clickup_original_approval"
}
```

See `aws/original-issuer/README.md` for the full deployment and test checklist.
