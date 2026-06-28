# Tests

Component tests for the pipeline. Pure logic (no API calls / no network), plus
one ffmpeg integration test that self-skips if ffmpeg is absent.

## Run

```bash
.venv/bin/python -m pytest tests/ -q
```

## Coverage

- **test_caption_gen.py** — style sanitizer (no em dashes, no emoji runs), CTA
  rules (exact keyword, ManyChat vs. booking link), section parser, system-prompt
  assembly + caching, model resolution.
- **test_buffer_and_publish.py** — Buffer `CreatePostInput` shape (the required
  `schedulingType`/`mode`, video vs. image asset, draft flag) and config-driven
  channel routing.
- **test_config_and_frames.py** — every client config has the required keys, the
  brand-store files exist and contain no em dashes, and ffmpeg frame extraction
  returns base64 JPEGs.

These run offline, so they're safe to run on every change. Caption *quality*
(actual Claude output) is not tested here — that needs a live API key and is
exercised manually in the app.
