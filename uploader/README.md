# uploader

Get media to S3 and back a shareable URL. Replaces Cloudinary (media hosting) and WeTransfer (file sharing).

## push_to_s3.sh
Local AWS CLI wrapper. One `studio-uploader` user works for every client's bucket.

```bash
# setup (once): aws configure ; cp ../config default bucket into ~/.deba_s3 (S3_BUCKET, AWS_REGION)
./push_to_s3.sh clip.mp4                              # default bucket from ~/.deba_s3
./push_to_s3.sh clip.mov --mp4                        # transcode to web mp4 (H.264) first
./push_to_s3.sh clip.mp4 --bucket otherclient-media   # target another client's bucket
./push_to_s3.sh clip.mp4 reels/skit3.mp4 --share      # 7-day presigned link (works with Block Public Access ON)
```

- `--share` → presigned URL (default delivery; pair with Block Public Access ON).
- no flag → constructs a public URL (only resolves if the bucket policy allows public GetObject).
- `--mp4` → needs `ffmpeg` (`brew install ffmpeg`).

## Editor handoff (WeTransfer replacement)
- Send footage: `./push_to_s3.sh raw_take.mov raw/2026-06/take1.mov --share` → paste the presigned link to the editor.
- Receive finals: editor uploads to the bucket (give them their own scoped IAM user/keys), or sends a link you re-host.

## Roadmap (for Claude Code)
- Add an `ingest/` helper that lists a client's `raw/` prefix and emits presigned links in bulk.
- Optional: the same logic as a GitHub Action (`.github/workflows/s3-upload.yml`) for no-Mac uploads via a source URL.
