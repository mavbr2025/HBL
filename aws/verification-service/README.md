# MTM HBL Verification Service

Cheapest MVP serverless verification service for MTM House Bill of Lading packages.

## Resources

- Private S3 bucket for issued PDFs and canonical JSON snapshots.
- DynamoDB on-demand table for verification records.
- Python Lambda for verification lookup.
- API Gateway HTTP API for public verification pages.

## Deploy With AWS CLI

SAM is optional. This repo includes an idempotent AWS CLI deployment script:

```bash
cd aws/verification-service
chmod +x scripts/deploy_aws_cli.sh
./scripts/deploy_aws_cli.sh
```

Defaults:

- `ENVIRONMENT=dev`
- `AWS_REGION` from `aws configure`, defaulting to `us-east-1`

Override example:

```bash
ENVIRONMENT=dev AWS_REGION=us-east-1 ./scripts/deploy_aws_cli.sh
```

If deployment fails with `AccessDenied`, attach the permissions in
`deploy-iam-policy.json` to the deployment user after replacing the placeholder
values for `ACCOUNT_ID`, `REGION`, and `ENVIRONMENT`.

## Deploy With SAM

If SAM is installed:

```bash
cd aws/verification-service
sam build
sam deploy --guided
```

Recommended guided values:

- Stack Name: `mtm-hbl-verification-dev`
- AWS Region: `us-east-1`
- Parameter Environment: `dev`
- Confirm changes before deploy: `Y`
- Allow SAM CLI IAM role creation: `Y`
- Disable rollback: `N`
- Save arguments to configuration file: `Y`

## API

- `GET /verify/{verification_id}` returns a public HTML verification page.
- `GET /api/verify/{verification_id}` returns JSON.

The PDF itself is not exposed publicly.

## DynamoDB Record

Minimum record:

```json
{
  "verification_id": "WH26040006-O1",
  "package_id": "pkg_...",
  "hbl_number": "WH26040006",
  "mbl_number": "ONEYTAOG71637300",
  "document_type": "ORIGINAL",
  "page_number": 1,
  "page_total": 1,
  "sequence": 1,
  "sequence_total": 3,
  "status": "ISSUED",
  "pdf_s3_key": "issued/2026/WH26040006/pkg_.../HBL_Package_WH26040006.pdf",
  "canonical_json_s3_key": "issued/2026/WH26040006/pkg_.../canonical.json",
  "pdf_sha256": "",
  "canonical_json_sha256": "",
  "issued_at": "",
  "issued_by": "Andrea Piedad Velasquez Castellon",
  "clickup_task_id": "",
  "voided_at": null,
  "superseded_by": null
}
```
