# Client Intake → New Client Page

Onboarding a new client into the Content Pipeline starts with the intake form.
The client fills it out; the answers become a client config + brand context file,
and from there it's the normal onboarding steps.

## One-time: create the form

1. Open <https://script.google.com> → **New project**.
2. Paste all of [`create_intake_form.gs`](create_intake_form.gs) over the default `Code.gs`.
3. Run ▶ `buildIntakeForm`, approve the permission prompt.
4. In the execution log, copy the three URLs it prints:
   - **Live form** — the link you share with clients.
   - **Edit form** — to tweak wording later.
   - **Responses sheet** — where answers land.

Reuse the same form for every client (each submission is one row), or duplicate it
per client if you prefer separate sheets.

## Per client

1. **Send** the live form link to the new client.
2. When they submit, open the responses sheet → **File → Download → CSV**.
3. Generate their config:
   ```bash
   .venv/bin/python pipeline/intake_to_config.py ~/Downloads/responses.csv --slug acme
   ```
   (Uses the latest response row by default; pass `--row N` to pick a specific one.)
   This writes:
   - `config/clients/acme.json` — the client config (from `_template.json`)
   - `config/clients/acme.brand.md` — narrative brand context the caption AI uses
   - a printed **checklist** of the technical fields you still fill in.
4. **Finish the technical wiring** (the checklist):
   - Connect their Buffer channels → paste each `channel id` into `buffer.channels.*.id`.
   - Create their S3 bucket (Block Public Access ON, public `media/` prefix) — see `aws/`.
   - Add `content-preview/clients/acme/config.json` and set `preview.pages_repo` / `pages_url`.
   - Sanity-check colors/fonts the client gave (free-text answers are flagged).
5. **Build their page** the usual way (`content-preview/generate.py`) and share the link.

## Keeping it in sync

The form's **question titles are the contract** — `intake_to_config.py` matches answers
to fields by those titles (substring, case-insensitive). If you reword a question in
the form, update `FIELD_KEYS` in `pipeline/intake_to_config.py` to match.

The mapper does **no network calls and no AI** — it's pure transcription, safe to re-run.
