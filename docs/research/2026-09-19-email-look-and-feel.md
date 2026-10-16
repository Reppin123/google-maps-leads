# Email look and feel for cold outreach from a personal mailbox

Research date: 2026-09-19. Scope: what "look and feel" should mean for maps-leads (local-first, no server, sends through the user's own mailbox over SMTP, cold outreach to small business owners, solo operator who is not a designer).

How to read this report:

- **Verified** means I read it on a primary source (vendor docs, postmaster page, raw data file) during this research.
- **Claim** means a vendor or blog says it, without a controlled test behind it.
- **Folklore** means it is repeated widely, but I found no test or postmaster statement behind it, or I found evidence against it.
- **Could not verify** means exactly that.

One-paragraph answer: for cold email from a personal mailbox, "look and feel" does not mean a designed template. It means the email looks like a careful person typed it in Gmail: correct multipart structure, the same font Gmail would use, clean paragraphs, a proper signature block, a good sender name, subject and first line (that is the real "design" the recipient sees in the inbox list), and an honest preview before sending. The marketing ESPs put design in a block editor because their mail is opt-in newsletters. Every cold email tool studied does the opposite: a small rich text box, a text-only switch, and warnings against images and tracking. Recommended default: Level 1 ("Plain, like you typed it") sent as real multipart/alternative, with Level 2 (light formatting) one click away.

---

## 1. How marketing ESPs handle email design, and where they put it

### 1.1 The four editor types

| Editor type | What it is | Who uses it | Products |
|---|---|---|---|
| Drag-and-drop blocks | Canvas of rows and columns. Drag in image, button, text, divider, social, product blocks. Global "Styles" tab for fonts and colours. | Marketers, e-commerce | Mailchimp (new builder), Klaviyo, Brevo, Beehiiv (visual editor), Customer.io (drag-and-drop and Design Studio), Stripo, Beefree |
| Document-style rich text | One column, reads top to bottom like Notion. Slash menu to insert things. Styling in a side panel. | SaaS founders, creators | Loops, Kit (ConvertKit), Beehiiv (post editor), Customer.io rich text |
| Code | HTML, MJML, or React components, with a live preview next to it. | Developers | MJML, React Email (Resend), Customer.io code editor and Design Studio code view, Mailchimp "code your own", Klaviyo HTML |
| "Plain-styled" | An HTML email made to look like a typed message: no images, one font, full width. | Anyone sending personal-feeling mail | Loops "Plain" mode, Kit text-first templates, Mailchimp "plain text" campaign type, Instantly and Smartlead "text only" |

A useful clarification from Word to the Wise (Steve Atkins, Nov 2024): what marketers call a "plain text" email is usually **HTML with minimal formatting** (no images, one font, basic markup). True `text/plain` mail has no bold, no link text, no tracking. Both exist and they are different things. (Verified.)

### 1.2 Product by product

**Loops (loops.so)**. Verified from Loops docs and changelog.

- The editor is one document column. You type. You add things from a toolbar, from a "+" that shows when you hover a block, or by typing `/` and filtering the list with the keyboard. Typing `{` opens a separate menu for merge tags (contact properties and event data). Markdown shortcuts work. It saves as you type, there is no save button.
- Elements available: text, headings, images, video, links, buttons, social icons, dividers, columns, sections, arrays (loops over data), code blocks.
- Styling is not in the way. A docked side panel on the right changes based on what you have selected (text, heading, link, button, divider, or the email body: padding, background, border). There are "Reset to default" icons on every setting. The April 2025 redesign replaced a floating toolbar with this docked panel, renamed "saved styles" to **themes**, and added **writing mode**, which hides all panels so you just write. A "Show styles" button appears above a selected element when you need it.
- Two email types. **Styled**: a centred responsive column, max 600px. **Plain**: full width, minimal base styling, which in their words "better mimic emails sent from clients like Gmail and Apple Mail". Themes are not available in Plain mode.
- **Themes** are reusable style sets. Change a theme and you can push the change to every email using it. **Components** are saved reusable blocks (a styled button, a divider, a footer).
- Loops calls the editor "low-html": emails go out with a small amount of styling on purpose. Their stated reason is readability and lower odds of spam or deprioritisation. That deliverability reason is a **vendor claim**, not a test.
- A footer with company name, address and unsubscribe is added automatically. Custom footers need a paid plan.
- Could not verify from the docs: dark mode preview, mobile preview toggle, how the plain-text part is generated, image hosting details.
- Why people like it (reviews, so treat as opinion): it feels like Notion or Linear, not a page builder. There is almost nothing to decide before you start typing. The result looks like mail from a person at a company, which is what SaaS founders want. The constraint is the feature.

**Mailchimp**. Verified from Mailchimp help.

- New builder is drag-and-drop with a template gallery. Also "code your own" and a plain-text campaign type.
- **Brand kit**: enter your website URL and click "Import My Brand". Creative Assistant pulls colours, fonts, images and logo from the site and generates on-brand designs.
- **Content Studio** hosts images and files.
- **Preview**: desktop and mobile side by side, send test, push to the Mailchimp mobile app, and **Inbox Preview**, which is powered by Litmus. Paid monthly plans get 25 tokens a month, one token per client per preview, 50+ clients. Includes a colour-blind view.
- Preview text (preheader) is its own field next to the subject.

**Klaviyo**. Verified from Klaviyo help.

- Drag-and-drop template editor plus a template library. A global **Styles** tab sets the look. If you went through the setup wizard, brand styles are already filled in.
- **Universal content**: star a block or section to save it. It shows in a "Universal" tab. Editing it can update every email that uses it. Typical use: header and footer.
- Could not verify in this pass: their text-only email type, dark mode preview.

**Kit (ConvertKit)**. Partly verified.

- Text-first by philosophy. A simple editor, "Starting Point" templates, reusable **snippets**, and a template marketplace made by creators. Founder Nathan Barry has long argued for plain-looking email. Details beyond this: could not verify.

**Beehiiv**. Verified from Beehiiv help and product updates.

- Newsletter post editor with theme settings (colours, padding, fonts, sizes), reusable templates, and a toggle between the email view and the web view of the same post. Preview shows mobile and desktop. Preview, send test, save template and schedule are pinned to the bottom of the editor. From 3 Aug 2026 new workspaces start in the Visual Editor.

**Customer.io**. Verified from Customer.io docs.

- Four editors, and a doc page that helps you choose: **Design Studio** (newest, visual blocks plus code view, reusable standard and custom components, global styling, collaboration), **drag-and-drop**, **rich text** (WYSIWYG plus HTML mode, with layouts for shared header and footer), and **code** (autocomplete, responsive preview, inspect element, HTML and AMP).
- Design Studio code editor supports components, HTML, CSS, MJML, AMP, has dark mode emulation and Can I Email data built in.
- A **Text tab** holds the plain-text version. One click on "Generate" builds it from the HTML. They say this matters for accessibility and deliverability.

**Brevo**. Partly verified (their help page blocked my fetch, so this is from search snippets of their help centre).

- New drag-and-drop editor, a **brand library** for brand assets, **saved sections** you can drag into future emails, a mobile view you can edit separately, and guidance on designing for dark mode. Whether the brand library imports from a website URL: could not verify.

**Resend and React Email**. Verified from Resend's blog.

- Emails are React components. A local dev server previews them at localhost:3000 with live reload. `render()` has a `plainText` option that produces the text part from the same source.
- React Email 4.0 added a toolbar with three checks: a **linter** (every link returns 200 and uses HTTPS, every image loads), a **compatibility checker** powered by Can I Email data, and a **spam score** using SpamAssassin. Plus a resizable responsive preview. 5.0 added a dark mode toggle in the preview.

**MJML**. From general knowledge, not re-fetched today.

- A markup language that compiles to the ugly table-based HTML that classic Outlook needs. You write `<mj-section>`, `<mj-column>`, `<mj-text>`, `<mj-button>` and get responsive output. It is a build tool, not an editor. Customer.io accepts it directly.

**Stripo and Beefree (embeddable editors)**. Verified from their sites.

- Both sell a drag-and-drop email editor you embed inside your own app. Beefree SDK: email, landing page and popup builders, file manager, template catalog API, reusable content blocks, HTML importer, AI writing, dark mode preview. Stripo Plugin: drag-and-drop plus HTML code editor, reusable modules, template library, AMP, a free tier and paid tiers.
- Relevance to us: both are hosted services. Beefree needs a server-side token exchange with their API. That conflicts with "no server, local-first". They also produce exactly the kind of email (multi-column, image-led, 600px table layout) that cold email should not be.

### 1.3 Common patterns worth copying

| Pattern | How leaders do it | Relevance to maps-leads |
|---|---|---|
| Flow | Pick template, then edit content, then set subject and preheader, then preview and send test, then pick audience and schedule. Beehiiv pins preview, test and schedule to the bottom of the editor. | Keep the same order. Look and feel is a step inside the message editor, not a separate "design" area. |
| Brand kit | One-time setup. Mailchimp imports logo, colours and fonts from a URL. Klaviyo fills brand styles in a wizard. | We only need: sender name, signature fields, optional small logo, one accent colour for links. No fonts. |
| Saved blocks | Klaviyo universal content, Brevo saved sections, Loops components, Kit snippets, lemlist snippets. | A small snippet library (intro lines, PS lines, sign-offs) fits cold email. |
| Signatures | ESPs mostly have footers, not signatures. Cold tools have a signature per mailbox, inserted by a variable. | Signature per sending mailbox, inserted automatically. |
| Image hosting | Every ESP hosts images (Mailchimp Content Studio, Beefree file manager). | We have no server. See section 3.6. |
| Merge tags | Loops: type `{`. Others: a "personalise" dropdown in the toolbar. Tags render as chips, preview swaps in a real contact. | Type `{` for a menu, show chips, preview with a real lead, show a fallback warning when a lead has no value. |
| Mobile preview | Desktop and mobile toggle everywhere. | Easy to do locally. |
| Dark mode preview | Beefree, Customer.io Design Studio, React Email 5. | Can be simulated locally, approximately. |
| Inbox-client screenshots | Mailchimp uses Litmus, token-limited. Litmus Core went to $500 a month in Aug 2025 (claim from a comparison blog, not checked on Litmus's pricing page). Email on Acid from about $74 to $99 a month. | Not worth it. A simple Gmail-style email renders the same nearly everywhere. "Send test to myself" covers the rest. |
| Accessibility checks | Mailchimp colour-blind view. Alt text prompts. React Email linter. | For us: alt text on the logo, link text that is not "click here", contrast check on the accent colour. |
| Plain-text part | Customer.io "Generate" button, React Email `plainText`. | Always generate it automatically. Let the user view it. |

---

## 2. What cold email tools do, and what the evidence says

### 2.1 Tool by tool

| Tool | Editor | Plain vs HTML control | Signature | Images and attachments | Tracking stance |
|---|---|---|---|---|---|
| **Instantly** (verified, help centre) | Small rich text editor | "Delivery Optimization": send all emails as text-only, or only the first email. It removes images, turns links into bare URLs next to the link text, and **turns off open tracking**. There is also a workspace-wide "always send first email as text-only". | Per sending account. Their own blog says plain text signatures deliver best for cold. | Images stripped in text-only mode | Off in text-only mode |
| **Smartlead** (verified, help centre) | Rich text | Campaign setting "send as plain text" | Per mailbox (the `%signature%` variable: could not verify the exact name) | Warns that messy signature HTML and badly encoded images hurt | Advises minimal HTML |
| **lemlist** (verified, help centre) | Toolbar: variables, formatting, fonts and colours, links, signature, snippets, attachments, code view. Liquid syntax for conditions. | No hard toggle found. Advice is minimal formatting. | One per user, inserted with `{{signature}}`. More signatures needs more users or manual paste. | Famous for **personalised images** (prospect's name on a coffee cup, their logo or website screenshot in a picture) and **video thumbnails** that link to a personalised landing page. All of this needs lemlist's servers to render and host images. Attachments are allowed. | Their own coach article says: **turn off both open and click tracking**, "limit links to 1 maximum per email, ideally 0", measure replies instead. |
| **Apollo** (verified, knowledge base) | Rich text plus raw HTML mode for templates | No text-only switch found | One per linked mailbox. Apollo's signature overrides the provider's. | Attachments supported | Says only enable open tracking if domain reputation is healthy, and switch it off when not running an experiment |
| **Woodpecker** (verified, help centre) | Rich text with Txt and HTML views, snippets | Text or HTML view per email | HTML signature pasted in HTML view | **No attachments**, "due to the deliverability issues it may cause". Use a link to the file. Images must be hosted by you at a public static URL. Google Drive and Dropbox links do not work. | Custom tracking domain offered |
| **Mailshake** (verified, help docs) | Rich text | Not found | Per account. Docs warn: "Heavily formatted signatures can cause your email to go to spam", keep to one link, images in signatures "not recommended for cold emailing". Also warns that pasted signatures carry hidden font sizes that clash with the body. | Discouraged | Checkboxes for track opens and track links, custom tracking domain |

Pattern: every cold tool has a small rich text box, not a designer. Most have a switch that strips the email back to text. Several of the vendors who sell tracking now tell users to turn tracking off. lemlist is the only one that pushes visual richness, and it depends on hosted infrastructure we do not have.

### 2.2 What postmasters actually say (verified, primary sources)

**Google Email sender guidelines** (support.google.com/mail/answer/81126, no date on the page, read 2026-09-19):

- Format messages to RFC 5322. If HTML, format to HTML standards.
- "Don't use HTML and CSS to hide content in your messages. Hiding content might cause messages to be marked as spam."
- Links should be "visible and easy to understand. Recipients should know what to expect when they click a link."
- Sender information should be clear and visible.
- Do not start subjects with Re: or Fwd: unless it really is a reply or forward.
- Do not use emojis or other non-standard characters to imitate graphic elements "with the intent to deceive or influence recipients".
- Valid Message-ID. From, To, Subject, Date appear once each. One address in From.
- Spam rate below 0.3%, aim for below 0.1%.
- 5,000+ a day to Gmail makes you a bulk sender: one-click unsubscribe (RFC 8058) plus a visible unsubscribe link in the body for marketing mail.
- What Google does **not** say: anything about plain text being preferred, a limit on the number of links, image-to-text ratio, or tracking pixels.

**Yahoo Sender Hub best practices** (verified): RFC 5322 format, spam rate below 0.3%, no deceptive subject lines, do not send to bought lists. Nothing on HTML vs plain, images, link counts or pixels.

**Microsoft Outlook.com** (verified, Microsoft Tech Community, enforced from 5 May 2025): senders above 5,000 a day need SPF, DKIM and DMARC (at least p=none, aligned). Recommended hygiene: valid From and Reply-To that can receive replies, a clear way to opt out. Non-compliant mail goes to Junk first. Nothing on formatting.

Important for the product, even though it is outside "look and feel": postmaster rules are about authentication, complaints and unsolicited mail. Cold email is by definition unsolicited. Low volume, real relevance and an easy way out matter more than any formatting choice.

### 2.3 What deliverability specialists say

- **Word to the Wise** (Steve Atkins, Nov 2024, verified): some people believe filters distrust HTML-only mail or reward a text part of similar size. How true that still is: "perhaps not much". But "it's usually a good idea to have your mail look (structurally) like all the mail other legitimate senders send", and most legitimate mail is multipart/alternative with text/plain plus text/html. A client is meant to show the last part it understands. Smartwatches and some other clients still show the text part.
- **Email Geeks consensus quoted by Suped** (verified as quoted, names not given): "a tracking pixel alone is not a reason to expect spam placement. Reputation still does the heavy work." Senders who strip elements one by one are usually avoiding the real problem, which is reputation.
- **Dyspatch** (verified): "plain text delivers better" is a myth as a general rule. Plain text mail lands in spam too. What causes false positives is image-heavy mail with little text.
- **Postmark, Customer.io, GlockApps** (vendor guidance, verified as stated): always send both HTML and text parts. They say missing text parts can hurt. No test data shown.
- **Word to the Wise, 2011** (verified, old): bit.ly links caused blocks. Spamhaus DBL still has a dedicated "abused URL shortener" zone, meant as a scoring weight, not an outright block. Old article, but the mechanism (Spamhaus zone) still exists.

### 2.4 What the data says, and how good it is

- **Hunter.io, 2025** (verified): 2.2 million cold emails from Hunter users. HTML campaigns bounced 652% more than plain text (another line in the same article says 674%). Hunter itself says: "This isn't a controlled A/B experiment, so confounding variables likely play a role". It measures bounces, not inbox placement. People who send HTML may simply be less careful about verifying addresses. **Weak evidence.**
- **HubSpot** (verified, article updated June 2025, tests are older): in A/B tests on opt-in marketing mail, plainer emails got more opens and clicks. HTML with images had 21% lower click-through and 51% fewer clicks, and "the more HTML-rich an email was, the lower its open rate". This is engagement on opt-in lists, not cold email and not inbox placement. **Moderate evidence, different context.**
- **"Plain text cold emails were blocked 30% more than light HTML because AI filters see no formatting as a legitimacy problem"**, attributed to a "2025 Global Email Deliverability Report" on SEO blogs. **Could not verify.** I could not find the report or its method. Treat as folklore until someone produces the source.
- **Instantly blog: "disabling open tracking gives a 2 to 10 point inbox placement lift" and "+68% reply rate without open tracking"**. Vendor numbers, no method shown. **Claim.**
- **SpamAssassin default scores** (verified today from the Apache trunk `50_scores.cf`): `MIME_HTML_ONLY` 0.1, `HTML_MESSAGE` 0.001, `MPART_ALT_DIFF` (text part and HTML part say different things) 0.79 with Bayes and network tests on, up to 2.246 without, `MPART_ALT_DIFF_COUNT` 1.1 to 2.8, `HTML_FONT_LOW_CONTRAST` up to 0.79, `SUBJ_ALL_CAPS` 0.5. Threshold is 5.0. So in SpamAssassin, HTML itself costs nothing, HTML-only costs almost nothing, and **a text part that does not match the HTML part costs the most**. Blog posts quoting 0.72 for HTML-only are out of date. SpamAssassin is not Gmail, but plenty of small business mail (cPanel hosts, some regional ISPs) sits behind it, and our targets are small businesses.
- **Emoji in subject lines**: Return Path 2017 found mixed results (sometimes better read rate and placement, often more complaints). Nielsen Norman Group found people react more negatively to emoji subjects. No solid current inbox placement test found. **Weak, mixed.**

### 2.5 Table: formatting choice, deliverability effect, evidence quality

| Formatting choice | Likely deliverability effect | Evidence quality |
|---|---|---|
| multipart/alternative (text + HTML) instead of text only | Neutral. Makes the mail look like normal person-to-person mail from Gmail or Outlook. | Good on structure (W2W, Gmail's own behaviour). No evidence text-only is penalised either. |
| HTML-only, no text part | Small negative at SpamAssassin-style filters (0.1). Unknown at Gmail. Easy to avoid. | Verified score. "Gmail marks HTML-only as spam" is folklore. |
| Text part that does not match the HTML part | Real penalty in SpamAssassin (0.8 to 2.2). | Verified score. |
| Simple HTML (paragraphs, bold, a list) vs true plain text | No measurable difference shown anywhere. Postmasters silent. | No controlled test found. "Plain text always wins" is folklore. "Plain text now blocked more" is also folklore. |
| Heavy template (tables, columns, banner, buttons) | Does not send mail to spam by itself. At Gmail it looks like marketing mail, which means the Promotions tab. For cold mail it also signals "mass mailing" to the human. HubSpot: lower opens and clicks. | Moderate for engagement. Tab placement is widely observed, not officially documented. |
| Image-only or image-heavy email with little text | Negative. Classic filter signal. | Good (SpamAssassin HTML_IMAGE_ONLY rules exist, Dyspatch, long-standing). |
| One small logo in the signature | Probably neutral for filters. Costs: remote images may be hidden until clicked for unknown senders, CID adds size and a paperclip in some clients. | Thin. Mailshake and Instantly advise against it, as opinion. |
| Open tracking pixel | Experts: not a spam cause on its own. Shared tracking domains carry other senders' reputation. Opens are unreliable anyway (Apple Mail Privacy Protection, Gmail image proxy, security scanners). | Expert consensus is good. Vendor lift numbers are claims. |
| Click tracking (rewritten redirect links) | Plausible negative: the visible link and the real destination differ, which is what phishing looks like, and it cuts against Google's "links should be visible and easy to understand". Security gateways click the links and create fake clicks. | Mechanism is sound. Numbers are vendor claims. |
| URL shorteners | Negative. Spamhaus keeps a list of abused shorteners used for scoring. | Good. |
| Number of links | No postmaster limit. lemlist says 0 to 1. What matters is the reputation of each linked domain. | Link domain reputation: good. "More than N links is spam": folklore. |
| Link text that hides a different URL (text says one domain, href another) | Negative. Phishing pattern. | Good (Google guideline on visible links, standard filter logic). |
| Attachments on a first cold email | Risky. Security gateways scan or quarantine, and strangers do not open attachments. Woodpecker bans them. | Moderate. Vendor policy plus common sense. No test found. |
| Hidden preheader text (display:none, runs of invisible characters) | Common and tolerated in marketing mail (Litmus). But Google's guideline says do not hide content. Pointless for us: the first line of the email is the preheader. | Conflicting. Avoid. |
| Emoji in subject | No clear filter effect. Mixed human reaction. Google only objects to deceptive use. | Weak. |
| Custom fonts, font stacks | No deliverability effect. Web fonts fail in Gmail and Outlook and fall back. Looks less like a person. | Good on rendering (Can I Email). No deliverability evidence either way. |
| Low-contrast or tiny text | Negative. Old spam trick. SpamAssassin HTML_FONT_LOW_CONTRAST up to 0.79. | Verified score. |
| Spam trigger words ("free", "guarantee") | Modern filters are reputation and engagement led. Word lists are mostly folklore. | Folklore for Gmail. Still a small factor on old-style filters. |
| Base64 or data URI images | Do not render in Gmail at all. | Verified (Can I Email raw data, retested 2024-05). |

Bottom line on evidence: **nobody has published a controlled inbox placement test of plain vs light HTML for cold email.** The honest position is that a Gmail-style light HTML email is structurally identical to what a human sends, and there is no mechanism or evidence for it being penalised. What is penalised is reputation, complaints, bad link domains, redirects, image-heavy mail and mismatched parts. The advice "plain text is safer" mostly works because the text-only switch also removes tracking pixels, rewritten links and images, not because of the MIME type.

---

## 3. Technical correctness of a "hand-written but polished" email

### 3.1 How Gmail itself composes a message

Basis: Gmail's well-known output, which anyone can confirm in one minute with "Show original" on a sent message. I did not find an official Google spec, so treat the exact markup as observed behaviour and check it locally before copying it.

- `Content-Type: multipart/alternative`. First part `text/plain; charset="UTF-8"`. Second part `text/html; charset="UTF-8"`, usually quoted-printable.
- The HTML has no `<html>`, `<head>` or `<body>`. It is a fragment: `<div dir="ltr">Hi Sam,<div><br></div><div>Second paragraph.</div></div>`. Paragraphs are `<div>`s. Blank lines are `<div><br></div>`.
- No font is set unless the user picked one. Gmail web shows it in its default sans serif, whose CSS is `arial, helvetica, sans-serif` at "small" (13px). The reader's client decides the final font.
- The signature sits in `<div class="gmail_signature" data-smartmail="gmail_signature">`, after a `-- ` line in many cases.
- A pasted image is sent as a `multipart/related` part with a `Content-ID`, and the HTML uses `<img src="cid:ii_...">` (verified via Torq's Gmail documentation, which describes this exactly).
- A Gmail API integration I read (gws-mcp PR 18) puts the signature only in the HTML part and builds the text part from the body alone. For maps-leads, put the signature in both parts. Otherwise the two parts differ, which is the one thing SpamAssassin clearly punishes.

### 3.2 What maps-leads should send

The mailer already builds messages with Python's `EmailMessage` and `set_content()` in `outreach/mailer.py` (`build_message`, line 133). The standard-library path to multipart is `msg.set_content(text)` then `msg.add_alternative(html, subtype="html")`. For a CID logo, call `add_related()` on the HTML part. This gives the correct nesting: `multipart/alternative` containing `text/plain` and `multipart/related` (which contains `text/html` and the image). No new dependency needed.

Suggested HTML, close to what a mail client makes:

```html
<div dir="ltr" style="font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.5;color:#222222">
  <p style="margin:0 0 14px 0">Hi Sam,</p>
  <p style="margin:0 0 14px 0">Body paragraph.</p>
  <p style="margin:0 0 14px 0">Thanks,<br>Asha</p>
  <!-- signature block -->
  <p style="margin:14px 0 0 0;font-size:12px;color:#666666">Unsubscribe sentence.</p>
</div>
```

Notes:

- No `<html>` wrapper needed, no `<style>` block, no classes, no max-width container, no background colour. Full width, left aligned. This is what Loops "Plain" mode does.
- Whether to set `font-family` at all is a judgement call. Setting nothing means every client uses its own default (Gmail: Arial, Apple Mail: Helvetica, classic Outlook: Times New Roman for unstyled HTML). Times New Roman in Outlook looks broken, so set `Arial,Helvetica,sans-serif`. Do not offer a font picker.
- Use `<p>` with explicit margins, or `<div>` plus `<br>`. Both are safe. Classic Outlook adds its own spacing to bare `<p>`, which is why the margins are explicit.
- Keep HTML well formed (Google asks for this). Escape user text. Encode as UTF-8.

### 3.3 Generating the matching plain-text part

Generate the text part from the same source as the HTML, never let the user maintain two copies.

- Paragraph becomes text plus a blank line. `<br>` becomes a newline.
- Link becomes `link text (https://example.com)`. If the link text is the URL, print it once. Instantly does it the same way.
- Bullets become `- item`. Bold becomes plain words (no asterisks, they look odd to a plumber reading on a watch).
- Signature becomes 3 to 5 plain lines. Logo is dropped.
- The unsubscribe sentence appears in both parts.
- Do not hard wrap at 72 characters. Python's email library handles transfer encoding. Hard wraps look ragged on phones. (`format=flowed` is the formal fix, W2W explains it, but it is not needed when lines are not wrapped.)
- Rule: same words in both parts. This is the `MPART_ALT_DIFF` check.

### 3.4 Safe inline CSS subset (Gmail, Outlook classic and new, Apple Mail, Yahoo)

Safe: `font-family` (system fonts), `font-size` (px), `font-weight`, `font-style`, `color` (hex), `line-height`, `text-decoration`, `text-align`, `margin` on `p` (Outlook.com has had quirks, test once), `padding` on `td`, `border` on `td` or `table`, `width` and `height` as **HTML attributes** on `img`, `border-collapse`.

Avoid: `<style>` blocks (Gmail's apps drop them for non-Gmail accounts, and some forwarding paths strip them), classes and ids, web fonts, `position`, `float`, flexbox, grid, `background-image`, `max-width` on a `div` (classic Outlook ignores it), `rem` and `em` sizes, CSS variables, `display:none`, SVG (not supported in Gmail), base64 images.

Classic Outlook for Windows still renders with Word's engine. New Outlook and Outlook.com use a browser engine. A one-column email with paragraphs and one small signature table is identical in both. This is a real benefit of staying simple: **no client-by-client testing is needed.**

### 3.5 Dark mode, width, size

- **Dark mode** (from several consistent guides, Litmus and others): Apple Mail respects `prefers-color-scheme` and does a partial inversion when you give it nothing. Gmail ignores `prefers-color-scheme`. Gmail's mobile apps and Outlook's apps force their own colour inversion. For an email with no background colour and dark grey text, every client simply flips to light text on dark, and it looks right. Two things to watch: use a **transparent PNG** logo that reads on both light and dark (or put a little padding and a white rounded box into the image itself), and pick a link accent colour that passes contrast on both white and near-black (mid blues do, dark navy does not).
- **Width**: designed emails use a 600 to 640px column. A typed-looking email uses none. It fills the reading pane like real mail. Do not add a container.
- **Size**: Gmail clips HTML over 102 KB (only the HTML counts, not images). A cold email is 2 to 5 KB. Not a concern unless a pasted signature drags in Word markup, so strip pasted HTML down to the allowed tags.

### 3.6 Signatures and images with no server

**How signatures are built.** Signature generators use a small `<table>` because classic Outlook cannot lay out a logo next to text any other way. A text-only signature does not need a table: a few lines with `<br>` is what Gmail users have. Rule for us: no logo means div and br. Logo beside text means one table, two cells, inline styles, `cellpadding="0" cellspacing="0" border="0" role="presentation"`, and the image with fixed `width` and `height` attributes and `alt` text.

**Image options when there is no server:**

| Method | Gmail web and apps | Classic Outlook | New Outlook and Outlook.com | Apple Mail | Cost |
|---|---|---|---|---|---|
| **Data URI / base64 in `src`** | **Does not render** (Can I Email raw data: "n" in 2020-02 and again 2024-05) | No (2019 partial) | Yes | Yes | Dead on arrival, since most small businesses are on Gmail or Workspace. **Verified.** |
| **CID inline attachment** (`multipart/related`) | **Conflicting sources.** Twilio SendGrid (Oct 2025), Mailtrap (Oct 2025) and many blogs say webmail "most likely" will not show it. But Gmail itself sends pasted images as CID parts and shows them, and CID mail from Apple Mail and Outlook shows in Gmail every day. My read: the "Gmail does not show CID" line is old folklore that keeps being copied. **Needs a 5-minute seed test before we rely on it.** | Yes, this is Outlook's native method | Yes (Microsoft moved Outlook on the web's own inline images to `cid:` from Nov 2025) | Yes, may also list it as an attachment | Adds the image size to every email (keep under about 15 KB). Some clients show a paperclip. No remote fetch, so no "display images?" prompt and no dependence on a host. Must be `multipart/related` with `Content-Disposition: inline`, otherwise it shows as an attachment. |
| **Externally hosted URL** | Yes, fetched through Google's image proxy. For senders Gmail finds suspicious, images are held back behind a prompt. | Often blocked until the reader clicks "download pictures" | Yes, with similar prompts | Yes (Mail Privacy Protection pre-fetches) | Needs a public HTTPS URL. The host's domain reputation becomes part of the email. Google Drive and Dropbox share links do not work (Woodpecker docs). Options for a user with no server: their own website (many have one: `https://theirsite.com/logo.png`), or a static host they control. We should not host it, and free image hosts are shared reputation. |

Recommendation: text-only signature by default. If the user wants a logo, first choice is CID (after the seed test passes), with the image resized locally to at most 2x of 120 by 40 px, PNG, under 15 KB. Second choice is a URL on the user's own domain, which also lines up the link domain with the sending domain. Never data URIs.

### 3.7 Subject lines and preheader

- **Emoji in subject**: technically fine (RFC 2047 encoded words, Python does it for you). No proven filter effect. Google only forbids deceptive use. NN/g found people rate emoji subjects more negatively, and for a first message to a stranger in a trade business it reads as marketing. Default: none. Soft warning if used, do not block.
- **Never fake "Re:" or "Fwd:"**. Google names it explicitly. Real follow-ups in the same thread are fine, and the mailer already tracks References.
- **Preheader**: in marketing mail this is hidden text stuffed at the top. For a personal email the inbox snippet is just the first words of the body. So the "design" task is writing a first line that works next to the subject. No hidden text needed, and hidden text is exactly what Google says not to do. Put the greeting and the first sentence to work: "Hi Sam, I saw Sam's Plumbing has 4.8 stars on Maps but no booking link" beats "Hi Sam, I hope this finds you well".
- **Sender name** is the most visible design element in the inbox list. "Asha from Brightside Websites" or "Asha Patel". Set once per mailbox.

---

## 4. Three levels of look and feel for maps-leads

Shared foundation for all levels (this is the real work):

1. Send true `multipart/alternative`: text part plus simple HTML part built from one source.
2. Structured signature per mailbox.
3. Sender display name per mailbox.
4. Keep the existing `List-Unsubscribe` mailto header and the unsubscribe sentence in both parts.
5. No open pixel, no link rewriting. Measure replies, which the mailer already detects. With no server we could not host a pixel or a redirect anyway, and the evidence says we lose nothing.
6. Pre-send checks (section 5).

### Level 1: "Plain, like you typed it" (recommended default)

What the recipient sees: a normal email from a person. Default sans serif, short paragraphs, sign-off, 3 to 5 line text signature, a small grey unsubscribe sentence.

Features:

- Body editor is a plain writing box with paragraphs only. Merge tags by typing `{`, shown as chips. Snippets.
- URLs typed into the body become real links that show the full URL as their text. Visible text equals destination.
- Signature builder with fields, not HTML: name, role, business, phone, website, one optional line (licence number, "Serving North Delhi since 2014"). Small business owners trust a phone number and a real address more than a logo.
- No images, no colour, no font choices.
- The HTML part exists only so the email renders in a proportional font with proper links and a quietly styled footer. The recipient cannot tell it from hand-typed Gmail mail.

UI placement:

- **Settings, Mailboxes, [mailbox]**: sender name, signature fields, live signature preview. Set once.
- **Campaign builder, Message step**: subject, body, and a collapsed "Look" row that says "Plain, like you typed it" with a "Change" link. Signature appears read-only under the body with "Edit in mailbox settings".
- **Preview panel** on the right of the Message step (section 5).

Deliverability risk: **lowest**. Same structure as mail typed in Gmail. No remote content, no redirects, nothing to fetch, nothing hidden. Remaining risk is all about list quality, volume, relevance and domain authentication, not formatting.

### Level 2: "Light formatting"

What it adds: bold, italic, bulleted and numbered lists, links with custom text, an optional one-line PS, an optional small signature logo, and one accent colour for links and the signature name.

Features:

- A toolbar of five buttons: B, I, bullets, numbers, link. Nothing else. No font, size, colour, alignment or headings.
- Link dialog with guard rails: warn if the visible text looks like a different domain than the URL, warn on URL shorteners, warn over 2 links, suggest linking the user's own domain.
- Signature options: logo upload (we resize to small PNG, ask for alt text, preview on light and dark), layout choice of "text only", "logo left", "logo above". Logo delivery by CID or by the user's own URL, per section 3.6.
- Accent colour: six presets that pass contrast on both white and dark. No free colour picker.
- "Brand basics" helper: paste your website, and we fetch it locally to suggest business name, logo (favicon or og:image), phone and an accent colour. This is Mailchimp's brand kit idea, done on the user's machine, as suggestions only.
- Per-step rule, copied from Instantly: "Send the first email plain (Level 1), use formatting from step 2". On by default. The first touch carries the most risk, and once someone has replied or opened a thread, reputation with that recipient is better.
- Text part generated automatically with the rules in 3.3.

UI placement:

- The "Look" row in the Message step becomes a three-way selector: Plain, Light formatting, Designed. Picking Light reveals the toolbar in the same editor. Nothing moves.
- Logo and accent colour live in **Settings, Mailboxes, Signature** (the thing is a property of the sender, not of the campaign).
- The "first email plain" rule lives in **Campaign, Sending options**.

Deliverability risk: **low**. Bold and lists are what people type every day. The added risk comes from two places: links (mitigated by the guard rails, and by never rewriting them) and the logo (CID adds bytes and sometimes a paperclip, a remote URL adds an image prompt and a domain dependency). With the logo off, Level 2 is close to Level 1.

### Level 3: "Designed" (one-column letterhead, not a newsletter)

What it adds: a small header with logo and business name, a single 600px column, one bulletproof call-to-action button, a footer with address and unsubscribe. Three or four fixed templates, for example "Letterhead", "Simple offer", "Follow-up with button". The user changes logo, accent colour and words only.

Features:

- Templates are hand-built table HTML with inline CSS, tested once by us in Gmail, classic Outlook and Apple Mail, shipped as local files. No drag-and-drop editor. Embedding Stripo or Beefree is rejected: both are hosted services, Beefree needs server-side auth, and they produce multi-column image-led layouts that a non-designer will make worse.
- No hero images, no multi-column product grids, no social icon rows (each icon is another remote image).
- Same merge tags, same generated text part.
- Locked to situations where it makes sense: replies to people who engaged, follow-ups to warm leads, existing customers, people who asked for a quote. The builder blocks it on step 1 of a cold sequence, with an override behind a clear warning.

UI placement:

- Third option in the same "Look" selector, labelled "Designed (for people who know you)". Choosing it opens a small gallery of the 3 to 4 templates with the user's logo and colour already applied.
- Preview panel gains more weight here: desktop, mobile, dark.

Deliverability risk: **medium for cold**, low for warm. Not because HTML tables trigger filters, but because: Gmail will likely file it under Promotions, remote or CID images are required for it to look right, image prompts make the first impression a broken-looking email, and to the recipient it reads as a mass mailing, which raises the chance of "Report spam". Complaint rate is the number Gmail cares about most (keep under 0.1%).

### Recommended default

**Level 1, with Level 2 one click away and "first email plain" on by default.**

Reasons:

1. It matches how the mail is sent. A personal Workspace mailbox sending mail that looks like a Workspace user typed it is consistent. A personal mailbox sending newsletter layouts is not.
2. Every cold email vendor converges on this, including the ones who sell richer features, and lemlist's own coach tells users to drop links and tracking.
3. No evidence shows light HTML hurting, and no evidence shows rich design helping cold replies. HubSpot's data points the other way even for opt-in mail.
4. Our constraints (no image host, no tracking host) make rich design fragile, while Level 1 and 2 need nothing but the mailbox.
5. The owner's point still stands: look and feel matters. For this kind of email it lives in the sender name, the subject, the first line, tidy paragraphs, a trustworthy signature, and mail that renders properly in every client and in dark mode. That is a real feature set, and the preview makes it visible.

Wording for the owner: "We do design the email. We design it to look like you wrote it, because that is the look that gets replies from a business owner. You get a proper signature, clean formatting, and a preview of exactly what lands in their inbox. A letterhead style is there for people who already know you."

---

## 5. Preview

### 5.1 What leaders show

| Preview feature | Who has it | How they do it |
|---|---|---|
| Desktop and mobile toggle | Mailchimp, Beehiiv, Brevo, Klaviyo, React Email, Beefree | Render the HTML at two widths |
| Dark mode preview | Beefree, Customer.io Design Studio, React Email 5 | Emulation in the browser. Real screenshots only from Litmus or Email on Acid |
| Real inbox-client screenshots | Mailchimp Inbox Preview (Litmus, 25 tokens a month on paid plans, 50+ clients), Litmus and Email on Acid integrations elsewhere | A third-party service opens the email in real clients and takes screenshots |
| Inbox list row (sender, subject, preview text) | Mailchimp and Klaviyo show preview text next to the subject, Litmus has a dedicated subject line checker | Simple mock of a Gmail and iPhone row with truncation |
| Preview as a specific contact | Klaviyo, Customer.io, Loops, lemlist, Instantly | Fill merge tags from a real record, step through contacts |
| Send test | Everyone | Sends to your own address |
| Link and image checks | React Email linter, Mailpit link check | Request every link, load every image |
| Compatibility check | React Email, Customer.io, Mailpit (175+ checks), Emailens | Match the HTML and CSS against Can I Email data |
| Spam score | React Email 4, Mailpit | SpamAssassin |
| Plain-text view | Customer.io Text tab | Show the generated text part |
| Accessibility | Mailchimp colour-blind view | Simulated filters, alt text checks |

### 5.2 What maps-leads can do locally, with no third party

| Feature | Local? | Notes |
|---|---|---|
| Desktop and mobile toggle | Yes | Sandboxed iframe at about 700px and 375px. For Level 1 and 2 the two look almost the same, which is a selling point. |
| Dark mode | Yes, approximate | Wrap the iframe in a dark background and apply a simple light-to-dark text flip, which is what clients do to an email with no background colour. Label it "approximate". Catches the real problem: a logo that disappears on dark. Exact Gmail and Outlook inversion rules are not public. |
| Inbox list row | Yes, high value | Mock one Gmail web row and one iPhone Mail row: sender name, subject, then the first 90 to 140 characters of the text part. Show truncation. Flag a wasted first line ("I hope this email finds you well"), subjects over about 60 characters, ALL CAPS, fake "Re:", emoji. This is the most useful preview for cold email, because the inbox row decides whether the mail gets opened. |
| Preview as a real lead | Yes | Arrow through real leads from the run. Highlight empty merge fields and show which fallback text was used. |
| Plain-text part view | Yes | A "Text version" tab. Builds trust and catches odd link rendering. |
| Raw source view | Yes | For the curious: headers and MIME tree. Proves multipart and List-Unsubscribe are there. |
| Send test to myself | Yes | Uses the user's own SMTP. This is the only true client preview, and it is free. Prompt the user to open it on their phone too. One-time setup tip: send to a Gmail and an Outlook address. |
| Link checks | Yes | Local HTTP request per link: resolves, HTTPS, not a known shortener, visible text matches destination domain. |
| Image checks | Yes | Logo size in bytes and pixels, alt text present, visible on light and dark. |
| Compatibility lint | Yes | Can I Email data is open source and can be bundled. With our fixed HTML this is a build-time test for us, not a user feature. |
| Spam score | Optional | SpamAssassin can run locally, or Mailpit with SpamAssassin (both open source). Heavy to install for a solo operator. A short rule list of our own (links, shorteners, caps, part mismatch, size) gives most of the value. Do not show a number that implies it predicts Gmail. It does not. |
| Real client screenshots (Litmus, Email on Acid) | No | Third-party, $74 to $500 a month (pricing from comparison blogs, not checked on vendor pages), needs the email content uploaded. Not needed for Level 1 and 2. For Level 3, we test our few fixed templates once ourselves. |
| Inbox placement seed tests (GlockApps and similar) | No | Third-party. Could be mentioned in help text as an optional outside step. |

Suggested preview layout in the Message step: a right-hand panel with two stacked parts. Top: the inbox row mock (Gmail and iPhone). Bottom: the opened email, with small toggles for Desktop or Mobile, Light or Dark, HTML or Text, and lead arrows. Under it a short checklist with green ticks or plain-language warnings, and a "Send test to me" button.

---

## Open items and things to test ourselves

1. **CID logo seed test** (5 minutes): send a multipart/related message with a 10 KB PNG from a Workspace mailbox over SMTP to a Gmail address, an Outlook.com address and an iCloud address. Check web and phone. This settles the conflicting claims in 3.6.
2. **Show original** on a hand-typed Gmail message from the user's own account, and compare it with our output. Match structure where sensible.
3. **Own A/B**: once volume allows, Level 1 vs Level 2 on reply rate. Nobody has published this test for cold email, so our own numbers will be better than anything cited here.
4. Could not verify: Loops preview and image hosting details, Klaviyo text-only and dark preview, Brevo website brand import, Smartlead signature variable name, the "2025 Global Email Deliverability Report", Litmus current pricing on Litmus's own page, Gmail's exact compose markup from an official source.
5. Outside this brief but important: cold email law (CAN-SPAM postal address, GDPR and PECR in the UK and EU, Australia's Spam Act consent rules). The footer design should leave room for a postal address line.

---

## Sources

Postmaster and standards

- Google, Email sender guidelines: https://support.google.com/mail/answer/81126?hl=en
- Google, Email sender guidelines FAQ: https://support.google.com/a/answer/14229414?hl=en
- Google, Gmail CSS support: https://developers.google.com/gmail/design/css
- Yahoo Sender Hub, best practices: https://senders.yahooinc.com/best-practices/
- Microsoft, Outlook's new requirements for high-volume senders: https://techcommunity.microsoft.com/blog/microsoftdefenderforoffice365blog/strengthening-email-ecosystem-outlook%e2%80%99s-new-requirements-for-high%e2%80%90volume-senders/4399730
- Mailgun on Microsoft sender requirements: https://www.mailgun.com/blog/deliverability/microsoft-sender-requirements/
- Apache SpamAssassin default scores (trunk): https://github.com/apache/spamassassin/blob/trunk/rules/50_scores.cf
- Spamhaus Domain Blocklist: https://www.spamhaus.org/blocklists/domain-blocklist/

Deliverability specialists and data

- Word to the Wise, "There's text and then there's text" (Nov 2024): https://www.wordtothewise.com/2024/11/theres-text-and-then-theres-text/
- Word to the Wise, "Bit.ly gets you Blocked" (2011): https://www.wordtothewise.com/2011/06/bitly-gets-you-blocked/
- Suped, do tracking pixels cause spam placement: https://www.suped.com/learn/email-deliverability/do-tracking-pixels-directly-cause-emails-to-be-marked-as-spam
- Dyspatch, the myth of deliverability, plain text vs HTML: https://www.dyspatch.io/blog/the-myth-of-deliverability-plain-text-vs-html/
- Hunter, "Is HTML harming your cold email deliverability?" (2025): https://hunter.io/blog/is-html-harming-your-cold-email-deliverability/
- HubSpot, plain text vs HTML emails data (updated June 2025): https://blog.hubspot.com/marketing/plain-text-vs-html-emails-data
- GlockApps, plain text vs HTML: https://glockapps.com/blog/plain-text-vs-html-emails-why-marketers-should-send-both-formats/
- Postmark, send email with API (HtmlBody and TextBody): https://postmarkapp.com/developer/user-guide/send-email-with-api
- MailNeo (origin of the unverified "30% more blocked" claim): https://www.mailneo.co/blog/email-plain-text-vs-html
- NN/g, emojis in email subject lines: https://www.nngroup.com/articles/emojis-email/
- Litmus, emojis in subject lines: https://www.litmus.com/blog/emojis-in-subject-lines
- Litmus, guide to preview text: https://www.litmus.com/blog/the-ultimate-guide-to-preview-text-support
- Litmus, Gmail clipping: https://www.litmus.com/blog/how-to-keep-gmail-from-clipping-your-emails
- Suped, images failing to load in Gmail: https://www.suped.com/learn/email-deliverability/why-are-images-intermittently-failing-to-load-in-gmail

Rendering and images

- Can I Email, base64 images (raw data, last entry 2024-05): https://github.com/hteumeuleu/caniemail/blob/master/_features/image-base64.md and https://www.caniemail.com/features/image-base64/
- Can I Email, all features: https://www.caniemail.com/features/
- Twilio SendGrid, embedding images in email (Oct 2025): https://www.twilio.com/en-us/blog/insights/embedding-images-emails-facts
- Mailtrap, embedding images in HTML email (updated Oct 2025): https://mailtrap.io/blog/embedding-images-in-html-email-have-the-rules-changed/
- Torq, how Gmail sends pasted images as CID: https://kb.torq.io/en/articles/9138326-send-gmail-messages-with-images
- Microsoft 365 dev blog, inline images move to cid in Outlook on the web (Nov 2025): https://devblogs.microsoft.com/microsoft365dev/changes-to-inline-images-in-outlook/
- Nodemailer, embedded images: https://nodemailer.com/message/embedded-images
- gws-mcp PR 18, Gmail-style composition and signature handling: https://github.com/datatorag/gws-mcp/pull/18
- Email on Acid, developing for Gmail: https://www.emailonacid.com/blog/article/email-development/12-things-you-must-know-when-developing-for-gmail-and-gmail-mobile-apps-2/
- Mailpeek, dark mode rendering by client: https://mailpeek.dev/blog/dark-mode-email-rendering

Marketing ESPs and editors

- Loops, the editor: https://loops.so/docs/creating-emails/editor
- Loops, styling emails: https://loops.so/docs/creating-emails/styles
- Loops, editor redesign (Apr 2025): https://loops.so/changelog/editor-redesign
- Loops, components: https://loops.so/changelog/components
- Mailchimp, brand kit: https://mailchimp.com/help/use-brand-kit-creative-assistant/
- Mailchimp, new builder: https://mailchimp.com/help/design-an-email-new-builder/
- Mailchimp, Inbox Preview: https://mailchimp.com/help/test-with-inbox-preview/
- Mailchimp, preview text: https://mailchimp.com/help/about-preview-text/
- Klaviyo, template editor guide: https://help.klaviyo.com/hc/en-us/articles/4407911841435
- Klaviyo, universal and saved content: https://help.klaviyo.com/hc/en-us/articles/115005413888
- Kit, email templates help: https://help.kit.com/en/collections/2961755-email-templates
- Beehiiv, new editor experience: https://product.beehiiv.com/p/meet-new-text-editor
- Beehiiv, newsletter templates: https://www.beehiiv.com/support/article/30974963947031
- Customer.io, choose the right editor: https://docs.customer.io/journeys/channels/email/editors/choose/
- Customer.io, Design Studio: https://docs.customer.io/journeys/design-studio/overview/
- Brevo, new drag and drop editor: https://help.brevo.com/hc/en-us/articles/31611992483346-About-the-new-drag-and-drop-email-editor
- Resend, React Email 4.0: https://resend.com/blog/react-email-4
- Resend, React Email 5.0: https://resend.com/blog/react-email-5
- Beefree SDK docs: https://docs.beefree.io/beefree-sdk
- Beefree, dark mode preview: https://support.beefree.io/hc/en-us/articles/4550122067730-Dark-Mode-Preview
- Stripo plugin: https://stripo.email/plugin/

Cold email tools

- Instantly, send emails as text-only: https://help.instantly.ai/en/articles/6531595-delivery-optimization-tool-send-emails-as-text-only
- Instantly, adding signatures: https://help.instantly.ai/en/articles/8278149-adding-signatures
- Instantly blog, tracking pixels and deliverability (vendor claims): https://instantly.ai/blog/email-tracking-and-deliverability-why-tracking-pixels-can-hurt-your-inbox-placement/
- Smartlead, send emails in plain text: https://helpcenter.smartlead.ai/en/articles/203-how-to-send-emails-in-plain-text
- lemlist, should you track clicks and opens: https://help.lemlist.com/en/articles/13941647-lemcoach-should-you-track-clicks-and-opens-in-cold-email-campaigns
- lemlist, email toolbar: https://help.lemlist.com/en/articles/4452808-step-by-step-guide-to-using-the-email-toolbar
- lemlist, signature: http://help.lemlist.com/en/articles/4452781-set-up-your-email-signature
- lemlist, dynamic images and videos: https://help.lemlist.com/en/collections/2570052-dynamic-images-videos
- Apollo, email signature: https://knowledge.apollo.io/hc/en-us/articles/4409140295949-Set-Up-Your-Email-Signature
- Apollo, email templates: https://knowledge.apollo.io/hc/en-us/articles/4409238165389-Create-and-Use-Email-Templates
- Woodpecker, attachments: https://woodpecker.co/help-center/en/articles/5268993-how-to-add-attachments-to-my-emails
- Woodpecker, images: https://docs.woodpecker.co/en/articles/5242544-how-to-include-an-image-in-my-email
- Woodpecker, signature: https://woodpecker.co/help-center/en/articles/5242493-how-to-edit-and-update-your-signature
- Mailshake, signature setup: https://docs.mailshake.com/article/87-how-do-i-set-up-an-email-signature
- Mailshake, signature formatting: https://docs.mailshake.com/article/245-how-do-i-fix-my-email-signature-formatting

Preview and testing tools

- Mailpit, HTML check: https://mailpit.axllent.org/docs/usage/html-check/
- Mailpit, SpamAssassin: https://mailpit.axllent.org/docs/usage/spamassassin/
- Emailens engine (offline rendering linter): https://github.com/emailens/engine
- Badsender, alternatives to Litmus and Email on Acid: https://www.badsender.com/en/2024/07/25/alternatives-litmus-email-on-acid/
- Mailosaur, preview tools 2026: https://mailosaur.com/blog/previews-tools-2026
