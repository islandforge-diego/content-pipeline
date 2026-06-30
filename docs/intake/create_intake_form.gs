/**
 * Island Forge — Client Intake Form builder (Google Apps Script)
 *
 * WHAT THIS DOES
 *   Run once in your Google account and it creates the full client-onboarding
 *   Google Form (all sections + questions + a linked responses spreadsheet),
 *   then logs the live link, the edit link, and the responses-sheet link.
 *
 * HOW TO RUN
 *   1. Go to https://script.google.com  →  New project.
 *   2. Paste this entire file over the default Code.gs.
 *   3. Press Run (▶) on  buildIntakeForm.  Approve the permissions prompt.
 *   4. Open  View → Logs  (or Execution log): copy the three URLs it prints.
 *      - "Live form" is the link you SHARE WITH CLIENTS.
 *      - "Responses sheet" is what you export to CSV for intake_to_config.py.
 *
 * NOTE ON LOGO UPLOAD
 *   File-upload questions require the respondent to be signed into a Google
 *   account. If your account can't add a file-upload item, the script falls
 *   back to a "paste a link to your logo" text field automatically — it never
 *   hard-fails.
 *
 * QUESTION TITLES ARE THE CONTRACT
 *   pipeline/intake_to_config.py maps answers by matching on the question
 *   titles below (substring, case-insensitive). If you reword a title, update
 *   the FIELD_MAP in that script too.
 */

function buildIntakeForm() {
  var form = FormApp.create('Island Forge — Client Onboarding');
  form.setDescription(
    'Welcome aboard! This helps us set up your content the right way from day one — ' +
    'your brand, your voice, your channels, and how you want to show up. ' +
    'Most fields are optional; fill in what you can and we’ll handle the rest. ' +
    'Takes about 10 minutes.'
  );
  form.setCollectEmail(true);
  form.setProgressBar(true);

  // ---- Section 1 · The Basics -------------------------------------------
  section(form, 'The Basics', 'Who you are and how to reach you.');
  req(form.addTextItem().setTitle('Business or show name')
      .setHelpText('e.g. "Principles of Real Estate — with Deba Douglas"'));
  form.addTextItem().setTitle('Tagline or one-line mission')
      .setHelpText('A short phrase that sums up what you stand for.');
  form.addParagraphTextItem().setTitle('Who do you serve?')
      .setHelpText('Describe your ideal audience / customer in a few sentences.');
  form.addTextItem().setTitle('Website');
  req(form.addTextItem().setTitle('Best contact email'));

  // ---- Section 2 · Your Story & Voice -----------------------------------
  section(form, 'Your Story & Voice',
    'This is the most important part — it shapes how every caption sounds.');
  req(form.addParagraphTextItem().setTitle('Your story')
      .setHelpText('How did you get here? What makes you, you? The origin story we should lead with.'));
  form.addParagraphTextItem().setTitle('Describe your voice in a sentence')
      .setHelpText('e.g. "Empowering, plain-language, energetic, mission-driven."');
  form.addParagraphTextItem().setTitle('Content topics / pillars')
      .setHelpText('3–5 themes you want to be known for.');
  form.addParagraphTextItem().setTitle('Hard do-nots')
      .setHelpText('Things we must NEVER say or do (compliance rules, claims to avoid, etc.). One per line.');
  form.addParagraphTextItem().setTitle('Words or phrases you love or hate')
      .setHelpText('Optional. Vocabulary that’s on-brand, and any to avoid.');

  // ---- Section 3 · Visual Identity --------------------------------------
  section(form, 'Visual Identity', 'Colors, fonts, and your logo. Paste hex codes if you have them.');
  form.addTextItem().setTitle('Primary color')
      .setHelpText('Hex like #0D5F6E, or just describe it (we’ll match).');
  form.addTextItem().setTitle('Secondary color').setHelpText('Hex or description.');
  form.addTextItem().setTitle('Accent color').setHelpText('Hex or description.');
  form.addTextItem().setTitle('Neutral / background color').setHelpText('Hex or description.');
  form.addTextItem().setTitle('Fonts you use')
      .setHelpText('e.g. "Headlines: Georgia Bold · Body: Lato". Leave blank if unsure.');
  // File upload (with graceful fallback)
  try {
    form.addFileUploadItem().setTitle('Upload your logo')
        .setHelpText('PNG or SVG preferred. (Requires you to be signed into Google.)');
  } catch (e) {
    form.addTextItem().setTitle('Logo link')
        .setHelpText('Paste a link to your logo file (Google Drive, Dropbox, etc.).');
  }
  form.addTextItem().setTitle('Brand kit or brand guide link')
      .setHelpText('Optional. Canva brand kit, PDF guide, or a Drive folder of assets.');

  // ---- Section 4 · Call to Action & Links -------------------------------
  section(form, 'Call to Action & Links', 'How people take the next step with you.');
  req(form.addTextItem().setTitle('Your booking link')
      .setHelpText('Where people book a call (Calendly, etc.). This becomes your "link in bio".'));
  form.addTextItem().setTitle('CTA keyword')
      .setHelpText('The ONE word you want people to comment or DM, e.g. "INVESTOR".');
  form.addTextItem().setTitle('Course or product platform')
      .setHelpText('Optional. e.g. Kajabi, Teachable, your shop URL.');
  form.addParagraphTextItem().setTitle('Any other key links')
      .setHelpText('Optional.');

  // ---- Section 5 · Your Channels ----------------------------------------
  section(form, 'Your Channels',
    'Which accounts we manage. We’ll send connection requests for you to approve.');
  form.addCheckboxItem().setTitle('Which platforms do you want managed?')
      .setChoiceValues(['Facebook', 'Instagram', 'TikTok', 'LinkedIn', 'YouTube']);
  form.addTextItem().setTitle('Facebook Page URL');
  form.addTextItem().setTitle('Instagram handle').setHelpText('e.g. @yourhandle');
  form.addTextItem().setTitle('TikTok handle');
  form.addTextItem().setTitle('LinkedIn profile or page URL');
  form.addTextItem().setTitle('YouTube channel URL');

  // ---- Section 6 · Posting Preferences ----------------------------------
  section(form, 'Posting Preferences', 'Cadence and timing. Sensible defaults if you’re unsure.');
  form.addMultipleChoiceItem().setTitle('How often do you want to post?')
      .setChoiceValues(['Once a day', 'A few times a week', 'Once a week', 'Not sure — recommend for me']);
  form.addTextItem().setTitle('Preferred posting time')
      .setHelpText('e.g. "3:00 PM". Leave blank for our default.');
  form.addTextItem().setTitle('Your time zone')
      .setHelpText('e.g. "Central / America/Chicago".');
  form.addMultipleChoiceItem().setTitle('Daily Instagram Stories?')
      .setChoiceValues(['Yes', 'No', 'Not sure']);
  form.addParagraphTextItem().setTitle('Story themes by day')
      .setHelpText('Optional. e.g. "Mon: testimonials · Fri: teaching." Leave blank for our default rotation.');

  // ---- Section 7 · Partners & Sponsors ----------------------------------
  section(form, 'Partners & Sponsors', '');
  form.addParagraphTextItem().setTitle('Sponsors or partners to credit')
      .setHelpText('Optional. Anyone we should tag or credit, and how (e.g. IG collab).');

  // ---- Section 8 · Anything Else ----------------------------------------
  section(form, 'Anything Else', '');
  form.addParagraphTextItem().setTitle('Posts you love')
      .setHelpText('Optional. Links to 3–5 posts (yours or others’) whose style you like.');
  form.addParagraphTextItem().setTitle('Anything else we should know?');

  // ---- Link a responses spreadsheet -------------------------------------
  var ss = SpreadsheetApp.create('Island Forge — Client Onboarding (Responses)');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());

  Logger.log('================ SHARE THESE ================');
  Logger.log('Live form (share with clients): ' + form.getPublishedUrl());
  Logger.log('Edit form:                       ' + form.getEditUrl());
  Logger.log('Responses sheet (export CSV):    ' + ss.getUrl());
  Logger.log('=============================================');
}

/** Add a section page-break with a title + optional help text. */
function section(form, title, help) {
  var pb = form.addPageBreakItem().setTitle(title);
  if (help) pb.setHelpText(help);
  return pb;
}

/** Mark an item required and return it. */
function req(item) { return item.setRequired(true); }
