# AWS setup (per client)

The pipeline uses S3 for two jobs: (1) hosting media so Buffer/Canva can fetch it, and
(2) sharing footage with editors. Default posture: **Block Public Access ON, presigned URLs.**

## One-time, studio-wide
1. **IAM user** `studio-uploader` (one user for all clients):
   - IAM → Users → create `studio-uploader`.
   - Attach `aws/iam-policy-studio-uploader.json` (put/get/list on all buckets).
   - Create an access key (CLI). Run `aws configure` on the uploading machine (region `us-east-2`, output `json`).
   - Never commit the key. Rotate periodically (single key = broad blast radius).

## Per client
1. **Create the bucket** (globally-unique, lowercase, e.g. `<client>-media` or here `debadouglas`), region close to audience (`us-east-2`).
2. **Leave Object Ownership at default** ("Bucket owner enforced") — ACLs disabled. Do NOT use ACLs.
3. **Leave Block Public Access ON.**
4. Done. Upload with `uploader/push_to_s3.sh ... --share` to get presigned links for Buffer/Canva/editors.

## Only if you need permanently-public media (no presigned)
- Prefer **CloudFront + Origin Access Control** (keeps the bucket private, BPA stays ON). Or:
- Turn Block Public Access OFF and apply `aws/bucket-policy-public-media.json` (scoped to the `media/` prefix). Then `push_to_s3.sh` without `--share` yields a public URL.

## Notes
- The Cowork/Claude sandbox cannot reach AWS — uploads run on a Mac (`push_to_s3.sh`) or via a GitHub Action. An `AWS API` MCP connector (if enabled) can run AWS CLI calls from chat for setup/inspection.
- Presigned URLs work with BPA fully ON because they use the caller's credentials, and Buffer/Canva download the file at schedule time (a short-lived link is enough).
