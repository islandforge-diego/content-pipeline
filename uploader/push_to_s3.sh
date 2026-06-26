#!/usr/bin/env bash
# push_to_s3.sh — upload a local file to S3 and print a shareable URL.
# Replaces Cloudinary (media hosting for Buffer/Canva) and WeTransfer (file sharing).
# One studio user works for every bucket; pass --bucket to target a specific client's bucket.
#
# One-time setup on your Mac:
#   1) brew install awscli ffmpeg          # ffmpeg only needed for --mp4
#   2) aws configure                       # paste the studio uploader key + secret, region us-east-2
#   3) (optional default bucket)  printf 'S3_BUCKET=debadouglas\nAWS_REGION=us-east-2\n' >> ~/.deba_s3
#
# Usage:
#   ./push_to_s3.sh clip.mp4                              # uses default bucket from ~/.deba_s3
#   ./push_to_s3.sh clip.mp4 --bucket otherclient-media   # target a different client's bucket
#   ./push_to_s3.sh clip.mp4 reels/skit3.mp4              # custom key/path in bucket
#   ./push_to_s3.sh clip.mov --mp4                        # transcode to web mp4 (H.264) first
#   ./push_to_s3.sh report.pdf --share                   # 7-day presigned link (works with Block Public Access ON)
set -euo pipefail
[ -f "$HOME/.deba_s3" ] && source "$HOME/.deba_s3"
: "${AWS_REGION:=us-east-2}"

FILE=""; KEY=""; MP4=0; SHARE=0; BUCKET="${S3_BUCKET:-}"
while [ $# -gt 0 ]; do
  case "$1" in
    --mp4) MP4=1 ;;
    --share) SHARE=1 ;;
    --bucket) shift; BUCKET="${1:?--bucket needs a name}" ;;
    --bucket=*) BUCKET="${1#*=}" ;;
    --region) shift; AWS_REGION="${1:?--region needs a value}" ;;
    -*) echo "Unknown flag: $1" >&2; exit 1 ;;
    *) if [ -z "$FILE" ]; then FILE="$1"; else KEY="$1"; fi ;;
  esac
  shift
done
: "${FILE:?Usage: push_to_s3.sh <file> [key] [--bucket NAME] [--mp4] [--share]}"
: "${BUCKET:?No bucket. Pass --bucket NAME or set S3_BUCKET in ~/.deba_s3}"
[ -f "$FILE" ] || { echo "No such file: $FILE" >&2; exit 1; }

if [ "$MP4" = "1" ]; then
  command -v ffmpeg >/dev/null || { echo "ffmpeg not installed (brew install ffmpeg)"; exit 1; }
  OUT="${FILE%.*}.web.mp4"
  echo "Transcoding -> $OUT ..."
  ffmpeg -y -i "$FILE" -vf "scale='min(1080,iw)':-2" -c:v libx264 -preset veryfast -crf 23 -c:a aac -movflags +faststart "$OUT" >/dev/null 2>&1
  FILE="$OUT"
fi

[ -n "$KEY" ] || KEY="$(date +%Y/%m)/$(basename "$FILE")"
echo "Uploading $FILE -> s3://$BUCKET/$KEY ..."

if [ "$SHARE" = "1" ]; then
  aws s3 cp "$FILE" "s3://$BUCKET/$KEY" --region "$AWS_REGION"
  URL="$(aws s3 presign "s3://$BUCKET/$KEY" --expires-in 604800 --region "$AWS_REGION")"
  echo "Presigned (7-day) link:"; echo "$URL"
else
  # public read comes from the bucket policy (no ACLs); only works if the bucket allows public GetObject
  aws s3 cp "$FILE" "s3://$BUCKET/$KEY" --region "$AWS_REGION"
  if [ -n "${CLOUDFRONT_DOMAIN:-}" ]; then URL="https://$CLOUDFRONT_DOMAIN/$KEY"
  else URL="https://$BUCKET.s3.$AWS_REGION.amazonaws.com/$KEY"; fi
  echo "URL (public only if bucket policy allows):"; echo "$URL"
fi
