# Content Pipeline — Web UI

A local web app for the whole flow: pick a client, drop in a photo/video,
transcribe + generate captions, edit them (or have AI revise), and schedule to
Buffer. Runs on your machine so it can reach ffmpeg, S3, Buffer, and the
Anthropic API.

## Setup

```bash
pip install -r pipeline/requirements.txt   # includes flask
cp .env.example .env                        # fill ANTHROPIC_API_KEY, BUFFER_TOKEN
```

ffmpeg must be on your PATH (used for transcription). AWS creds must be
configured for S3 (`aws configure`, or set `AWS_PROFILE` in `.env`).

## Run

```bash
python webui/app.py
```

A browser opens at http://127.0.0.1:5000.

## What you can do

- **Pick a client** from the dropdown, or **+ Add client** to onboard a new one
  (the form can **fetch your Buffer channels** so you map them with clicks
  instead of pasting IDs; writes `config/clients/<slug>.json`).
- **Choose a file** by drag-and-drop, **Browse file…** (native dialog), or
  **Browse folder…** then pick from the media inside. Works on Mac and Windows.
- **Generate captions**: videos are transcribed locally (Whisper); photos use a
  short brief. Captions are drafted per platform from the client's brand voice.
- **Edit captions** inline, or type **quick feedback** ("punchier", "drop the
  emojis") and let AI revise that one caption.
- **Schedule to Buffer**: pick a time (defaults to the client's feed time).
  Leave **"Preview only"** checked for a dry run that uploads/posts nothing;
  uncheck to upload to S3 and create the Buffer posts for real. A scheduled post
  is also added to the client's calendar preview.

## How it fits together

The UI is a thin Flask layer over the existing pipeline modules:

- `pipeline/transcribe.py` — ffmpeg + Whisper
- `pipeline/caption_gen.py` — `generate_captions()` + `revise_caption()`
- `pipeline/publish.py` — boto3 S3 upload + Buffer posting (cross-platform)
- `pipeline/buffer_api.py` — Buffer GraphQL (list channels, create post)
- `content-preview/generate.py` — rebuilds the unified calendar preview

Long-running steps run as background jobs (`webui/jobs.py`); the page polls for
status. The native file dialog runs tkinter in a subprocess
(`webui/native_dialog.py`) so it works alongside Flask on macOS.

## Notes

- `webui/.uploads/` holds drag-and-dropped files temporarily (gitignored).
- The Buffer GraphQL queries in `buffer_api.py` reflect Buffer's current API; if
  Buffer changes its schema, introspect and adjust the query/mutation there.
