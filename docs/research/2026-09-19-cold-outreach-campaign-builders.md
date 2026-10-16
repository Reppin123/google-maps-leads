# How the leading cold outreach tools let people design and launch campaigns

Research date: 2026-09-19. Author: research agent, for the maps-leads campaign builder.

## How to read this

Every claim carries one of three tags.

- **[V]** Verified on the vendor's own help center or docs page, fetched today.
- **[V-snippet]** From the vendor's own page, but I only saw the search engine excerpt because the page blocked fetching (Apollo knowledge base, Reply.io, G2 all returned 403).
- **[3P]** Third-party claim (review blog, competitor blog, Reddit summary). Many review blogs in this space are written by competitors (Salesforge, Sparkle, Snov, lemlist, Saleshandy, Instantly all review each other). Treat them as directional.

Things I could not verify are listed at the end of each section rather than guessed.

Our builder today, for reference: one long page (Who gets it / The emails / When / Launch), up to 6 emails with day gaps, up to 4 versions (A to D) with each lead keeping one letter for the whole series, merge fields with fallbacks like `{suburb|your area}`, live preview against a real lead, "send me a test", audience picker with named exclusions, a sending-time forecast, recipient-timezone windows, results with confidence intervals and a "too early to call" verdict, text locked after launch, plain text only.

---

## 1. Campaign creation flow, step by step

### Instantly [V]

A campaign is a set of tabs along the top of the campaign page. Creation is "+ Add New", name it, "Continue", then you land in the tabs.

| Order | Tab | What is on it |
|---|---|---|
| 1 | Leads | "Add Leads": CSV, SuperSearch, manual, Google Sheets, HubSpot, Pipedrive. Column mapping dropdown per column with predefined variables, custom variable, or "Do Not Import". |
| 2 | Sequences | Split screen. Step list on the left, editor on the right. Subject, body, "Add variant", "Add step", delay selector ("Send next message in x days/hours/minutes"). Variable picker (bolt icon in the subject, dropdown in the toolbar). "Templates" button. "AI Tools" menu. "Preview" button. |
| 3 | Schedule | Days of week, time range, one timezone. Start date (default "Now") and end date (default "No end date"). "Add Schedule" for extra layers, listed in a left sidebar. |
| 4 | Options | A long settings form, split into standard and "Advanced Options". 19 settings, listed in section 5. |
| After launch | Analytics, Subsequences | The Subsequences tab "only shows after you launch your campaign". |

Pre-launch: the help center gives a written checklist (leads uploaded and mapped, sequence saved, variables populate, preview and test, schedule configured, sending accounts assigned). I found no evidence of an in-product checklist or review screen. The "Launch" button simply sits on the campaign page. The Preview dialog has "Load data for lead" (search by email or name), a test-send field (comma-separated recipients), a "Send from" account selector and a deliverability checker.

### Smartlead [V]

Smartlead documents two versions. The older wizard was a strict sequence. The "new version" (article 442) is tabs on a draft campaign.

| Order | Tab / step | What is on it |
|---|---|---|
| 1 | Create | "+ Create Campaign", optional name, "Continue". The campaign exists immediately in "Draft". |
| 2 | Leads | "+ Add Leads": CSV, CRM, saved lists, SmartProspect. Upload settings are four checkboxes that act as named exclusions: "Global Block List", "Unsubscribe List", "Community Bounce List", "Existing Campaign Leads". Auto column mapping, then "Import Leads". |
| 3 | Sequence | "+ Create First Step". Step types: Email, Manual Task, Call. Steps are added from a left panel. Wait times between steps ("Wait for ___ day then"). "Add Variant". Editor tools: "Write with AI", "AI Spintax", "Email Templates", a readability check ("ABC") and a spam check. |
| 4 | Email Accounts | Pick sending mailboxes. Each row shows daily limit, warm-up status and other campaigns using it. Filter by status (Pre-warmed, Disconnected, Nearing limit). |
| 5 | Settings | Schedule (timezone, start date, active days, window, send interval, new leads per day). Campaign behaviour (stop on Replies / Clicks / Opens, variant distribution "Pattern-based (recommended)" or Randomized). Delivery optimisation (plain text mode, disable open or click tracking, provider distribution). AI categorisation. Protection (bounce auto-protection, domain rate limiting, unsubscribe text). Webhooks. |
| 6 | Launch | Documented required checklist of three items: leads added, at least one sequence step, email accounts assigned. Then "Launch Campaign". |

The older wizard (article 34) ends with a "Review Your Campaign" step: personalised copies with real data injected, per-recipient edit, a mobile preview, a SmartDelivery spam test and a test email. A third-party review (Sparkle) describes the same final screen as three actions: Spam test, Test email, Launch [3P]. The new-version article does not describe this screen, so I cannot confirm it still exists in the same form.

One inline warning worth noting [V]: "Distribution mode cannot be changed once the campaign is live."

Statuses: Draft, Active, Paused, Stopped.

### lemlist [V]

Tabs on the campaign: Sequence, Lead list, Launch, Performance, plus a gear icon for settings.

| Order | Tab | What is on it |
|---|---|---|
| 1 | Entry | "Create campaign" offers AI, Manual or Template. You land on the Sequence tab. |
| 2 | Sequence | Vertical step list. "Add step" opens a picker with two tabs: "Steps" (email, LinkedIn, call, task, API) and "Conditions". Clicking a step opens a right-side panel to write it and pick senders. lemAgent AI panel on the left. Campaign name is an inline field top left. |
| 3 | Settings (gear) | Sections: Automation (what happens on click / reply / meeting booked, "Also pause contacts from the same company"), Senders (provider matching), Tracking, "Schedules & launch" (days, hours, minutes between first-step sends, auto launch), General (tags, unsubscribe behaviour), CRM. |
| 4 | Lead list | "Import new leads": database, lists, CSV, CRM, signals, LinkedIn, manual, API. "+ Add" then "Create AI column" for AI variables. |
| 5 | Launch | Split view. Leads on the left, that lead's whole sequence previewed on the right. Click through each step. "Personalize" edits one lead's copy. Filter leads, including by missing variable [V-snippet]. Select leads, then "Launch for X leads". |
| 6 | Launch recap modal | "Campaign launch recap" pop-up: number of leads, time between each lead (first step only), stop conditions, sending schedule. Confirm with "Launch campaign for X leads". |
| 7 | Performance | Per-lead delivery stats, a "Negative stats signal" health summary, "Step details", CSV export. |

Important model difference: in lemlist a lead is launched, not a campaign. "1 lead launched = campaign goes live for that lead." You can launch 20 leads today and the rest next week from the same screen. lemlist recommends test batches of 10 to 20 leads.

### Others, briefly

- **Woodpecker [V]**: three sections per campaign, PATH (emails, delays, conditions), PROSPECTS, SUMMARY (preview and send). SUMMARY shows email count per path, prospect count, sending address, A/B versions. "Preview" marks missing snippets in red. "Send Test Campaign" sends the whole sequence to yourself. Green "RUN" button. One smart nudge: if the campaign has only one email, a pop-up asks whether to add follow-ups or "Run campaign anyway".
- **Mailshake [V]**: a mandatory five-step wizard. Basic settings (including "Lead Catcher" rules), import prospects, write sequence, manually personalise individual prospects' messages, "Start Campaign". A red exclamation mark warns when some recipients lack a text replacement [V-snippet].
- **Apollo [V-snippet]**: a sequence is a step list (automatic email, manual email, call, action item). "Settings" holds name, folder, owner; "Scheduling" picks a reusable schedule; "Ruleset" holds stop and safety rules. Contacts are added to a sequence afterwards, from search or lists.
- **Reply.io [3P, vendor blog]**: a three-step "Sequence Wizard": add contacts, add steps, set it up. Steps, conditions and channels are added from one screen.
- **Saleshandy [V]**: Sequences, "Create Sequence", "Add Step", write, save. Prospects and settings are tabs. A "Sequence Score" sits on the sequence tab (section 4).
- **Outreach / Salesloft**: sequences (cadences) are reusable objects owned by a team, with rulesets and shared templates. Built for managers governing reps, not relevant to a solo operator beyond their A/B handling (section 2).

### What is required before launch, and how each tool says so

| Tool | Mechanism | Tag |
|---|---|---|
| Smartlead | Three required items (leads, one step, mailboxes). Final review screen with spam test and test email in the older flow. | V |
| lemlist | Launch tab is itself the review. Launch recap modal restates lead count, pacing, stop conditions and schedule. | V |
| Woodpecker | SUMMARY section, red missing snippets in Preview, "only one email" pop-up. | V |
| Mailshake | Wizard step 4 is a review. Red exclamation for missing text replacements. | V / V-snippet |
| Instantly | Checklist exists only in the help article. | V |

Could not verify: whether Instantly blocks Launch when no sending account is attached (very likely, not documented on the pages I read).

---

## 2. The sequence and step editor

### Layout

The dominant layout is a vertical step list on the left with wait chips between steps, and the editor for the selected step on the right (Instantly, Smartlead, lemlist, Saleshandy). Variants appear as lettered tabs or rows inside a step. A third-party reviewer with two years on Instantly singles out the split screen as the reason they go "from blank page to live sequence in minutes" [3P]. Woodpecker stacks emails vertically on one page and G2 reviewers complain it has no drag and drop and that reordering takes many clicks [3P].

### Delays

| Tool | Units | How counted | Tag |
|---|---|---|---|
| Instantly | days, hours, minutes | Calendar time, then waits for the schedule window | V |
| Smartlead | days | "Wait for ___ day then" | V |
| lemlist | days only | **Scheduled sending days**, not calendar days. A 2-day delay set on Thursday in a Mon to Fri campaign lands on Monday. Follow-ups go out around the same clock time as the first email. | V |
| Woodpecker | days, hours, minutes | Defaults 3, 6, 12 days. Clock icon per step. | V |
| Reply.io | days | Each day is 24 hours from the previous step's send | V-snippet |
| QuickMail | business days | "wait for three business days" | 3P |

### Conditions and branches

- lemlist: conditions are a second tab in the "Add step" picker. They split into lead information and lead actions. Behaviour conditions cannot be first, and "If email is opened" must be preceded by a delay of at least 1 day so detection has time to work [V]. A Snov reviewer wrote "I felt a bit overwhelmed at this point" [3P].
- Woodpecker: "ADD CONDITION" creates Path YES and Path NO. Condition types: open, click, task, snippet value [V]. Woodpecker itself warns that A/B stats inside if-campaigns "may not be accurate due to a small number of prospects in each Path" [V].
- Reply.io: Yes/No branches, numbered [3P].
- Instantly: no branches in the main sequence. Instead "Subsequences", a separate tab that appears after launch, triggered by lead status, activity (opened, clicked, completed without reply) or reply keywords. Paid tiers only [V].
- Smartlead: subsequences with similar triggers [V, title only].

### Same thread or new thread, and subjects

Instantly, Smartlead, lemlist and Saleshandy all use the same convention [V]: **leave the follow-up's subject blank and it sends as a reply in the same thread; type a subject and it becomes a new thread.** Consequences they document:

- lemlist: the preview shows a blank subject on follow-ups and the help center has to reassure people "this is normal and expected". Changing sender or adding CC/BCC can break the thread. There is a separate article titled "Fix emails not threading".
- Instantly: if you A/Z test follow-ups, keep subjects identical and vary only the body, or threading breaks.
- Saleshandy: follow-up variants must have blank subjects.

Apollo is the exception, with an explicit step setting "Reply to a Previous Thread" versus new thread [V-snippet]. Woodpecker also has an explicit option for "Sending follow-ups as a separate message" [V, title only].

### Step-level variants

| Tool | Max per step | How created | Split | Same variant across steps? | Pause | Winner | Tag |
|---|---|---|---|---|---|---|---|
| Instantly | 26 (A to Z) | "Add variant" in the step | Balanced over the campaign's lifetime. A variant added later sends alone until it catches up. A global Preference "Reset A/Z variant usage tracking daily" changes this. | Not documented | Toggle, blue or grey, available in the editor and again in Analytics, Step Analytics | Manual, or "Auto optimize A/Z testing" in Options, Advanced. Pick reply, click or open rate. It "automatically deactivates" losers. No sample threshold is documented. | V |
| Smartlead | 10 | "Add Variant" | Equal, manual percentages (multiples of 10 only), or "AI percentage Distribution": test on 10 to 80 percent of the list, then send the winner to the rest | Not documented | Not documented | Auto by chosen metric: reply, positive reply, click, open | V |
| lemlist | 2 | Step menu, "A/B test this step". A separate feature A/B tests the entire sequence. | 50/50 random | Step test is per step | n/a | Manual, step menu, "Select as winner". **Permanent, cannot be undone.** Advice: 50 to 100 leads per version, wait 5 to 7 days. Leads who already got A stay on A. | V |
| Woodpecker | 5 (A to E) | Green plus, or duplicate a version | Random per step. "Each prospect can receive different versions across different steps." | No | Toggle. Active is green, inactive is grey. At least one must stay on. | Manual. A "winner icon" marks the best open, click, reply and interest rates. Advice: 100 prospects per version. CSV export has a VERSION column. | V |
| Saleshandy | 26 | "+ Add variants" | Equal. A prospect with B in step 1 does not necessarily get B in step 2. | No | Enable / Disable | Not documented | V |
| Apollo | several (C, D and on) | Add another email to the step | Even, random per step | No | Deactivate | Manual. "Only determine an A/B test winner if you have a 90% or greater confidence interval." | V-snippet |
| Mailshake | 10 (A to J) | "A/B Test" button | Roughly even | Unknown | Unknown | Unknown | V-snippet |
| Outreach | templates on a step | | Even | | Manual. Outreach "does not automatically deactivate the lower-performing template". | A real statistical test on reply rate with four named states: "Experiment in progress", "No clear winner found yet", "Issues discovered with your experiment", "You have a winner". | V |

Two findings matter for us.

1. **Almost everyone re-rolls the variant at each step** (Woodpecker, Saleshandy, Apollo all say so). That makes a reply after email 3 impossible to attribute cleanly. lemlist's whole-sequence A/B test is the only equivalent of our "one letter for the whole series", and ours is the cleaner design. Keep it.
2. **Only Outreach tells the user honestly when it is too early.** Instantly and Smartlead auto-pick winners without documented sample thresholds. A Smartlead review notes "no A/B test significance calculations" [3P]. Our confidence intervals and "too early to call" verdict are ahead of the cold email category and level with the enterprise tier.

### Where per-variant stats are shown

- Instantly: Analytics tab, scroll to "Step Analytics". One row per step and per variant with Sent, Opened, Replied, Clicked, Opportunities, and the on/off toggle in the same row [V]. This is the best placement found: the number and the action sit together.
- lemlist: Performance tab, versions side by side, only meaningful "once most leads have received the step" [V].
- Woodpecker: stats dashboard with winner icons [V].
- Saleshandy: you look in the "Emails" tab to see which variant each person received [V]. Weak.
- No cold email tool I could verify shows stats on the variant tab inside the editor itself.

---

## 3. Personalization

### Merge tag UI and fallbacks

| Tool | Syntax | Fallback | Tag |
|---|---|---|---|
| Instantly | `{{firstName}}`. Picker is a bolt icon in the subject and a toolbar dropdown in the body. Names are case-sensitive. | `{{companyName | your company}}`. Without a fallback a missing value becomes an **empty string, silently**. | V |
| Smartlead | `{{first_name}}` from a dropdown | Handlebars-style block: `{{#if first_name}} Hey {{first_name}}, {{else}} Hey there, {{/if}}`. They warn that `==` without quotes "will break". | V |
| lemlist | `{{firstName}}` | `{{firstName|there}}` | V |
| Woodpecker | `{{FIRST_NAME}}` via blue "snippets" buttons | `{{SNIPPET | "Filler Value"}}`. When you insert a fallback a dialog asks for the value and offers "Leave empty". | V |
| Mailshake | `{{company}}` "text replacements" | A 2023 hands-on test found missing tags went out as literal curly braces unless removed by hand [3P, may be outdated] | 3P |

Our `{suburb|your area}` matches the convention used by Instantly, lemlist and Woodpecker. Nothing to change in the syntax.

### Conditionals and spintax

- Instantly supports full LiquidJS: `{% if position == "founder" %}...{% endif %}`, time-of-day greetings, weekday cases. Their own docs suggest a hack of hiding a variable inside a `display:none` div so a conditional can read it [V]. That is a sign the feature outgrew its UI.
- Instantly spintax: `{{RANDOM | Hello | Hi | Greetings!}}`, variables can nest inside [V]. Smartlead has an "AI Spintax" button [V]. lemlist supports Liquid and spin text [V / 3P].
- None of the help pages describe linting for malformed syntax. Every one says to preview.

### AI first lines and AI variables

- lemlist "AI variables" [V]: created on the **Lead list** tab, "+ Add", "Create AI column". Template categories: cleaning, copywriting, extraction, research, segmentation. Recommended prompt shape: action, output format, examples. "Test prompt" runs it on sample leads first. Results fill a column, and empty rows are flagged "Empty output". Temperature setting, choice of model vendor, cost per request shown.
- Instantly [V-snippet]: "AI Prompts & Enrichment". Per-row actions such as "Write an opening line" at about 0.5 credits a row, written into a `{{Personalization}}` column.
- Clay [3P, consistent across several guides]: one narrow job per AI column (research, summarise, write one line), never "write the whole email". Filter out rows where the personalization column is empty before pushing to the sender. Column names must match the sender's variable names exactly.

The shared pattern: **AI output lives in a lead column that you can scan and fix, not inside the email template.** The email only references `{{icebreaker}}`. Generation becomes inspectable and the editor stays simple.

### Custom images (lemlist) [V]

In the email editor: "Add", "Custom media". A layered image editor with elements Text (with variables), Image, Photo (profile picture), Logo (from the email domain), Website variable (screenshot of the lead's site), Image variable. Known gap: logos do not resolve for gmail or yahoo addresses. Not relevant to a plain text product, but the website screenshot idea has a plain text cousin for us: a line that refers to something true from the business's Maps listing.

### Per-lead preview

- Instantly: Preview dialog, "Load data for lead", search by email or name [V].
- lemlist: the Launch tab, lead list on the left and full sequence on the right, step through leads and steps, "Personalize" to override one lead's copy. "Reset Override is permanent" [V].
- Smartlead: review step shows each lead's personalised copy with per-recipient edit and a mobile preview [V, older article].
- Woodpecker: "Preview" in SUMMARY with missing snippets in red, and per-prospect customising [V].

### Detecting broken or empty variables

| Tool | Behaviour | Tag |
|---|---|---|
| Woodpecker | Best guard rail. A prospect missing a snippet is not sent. Status becomes "PAUSED (SNIPPET ISSUE)" and they collect in a "To Check" tab with the empty fields marked red. Fixes: fill the field, remove the snippet, delete the prospect, or add a fallback. Weakness: detection happens at send time, not before launch, apart from the red in Preview. | V |
| lemlist | Launch stage can filter leads by missing variable. Advice is to skip them, enrich, un-skip, launch a second batch. | V-snippet |
| Mailshake | Red exclamation mark on the campaign when some recipients lack a replacement. | V-snippet |
| Saleshandy | "Invalid merge tags" is one input to the Sequence Score. | V |
| Instantly | Silent empty string. Preview is the only defence. | V |
| Smartlead | A search excerpt claims malformed syntax causes leads to be skipped. I could not confirm that on the page itself. | unverified |

---

## 4. Writing help that is actually smart

| Tool | What it does | Where it lives | Tag |
|---|---|---|---|
| Instantly | "AI Spam Words Checker": an LLM reads the copy in context, highlights risky words and offers replacement cards you click to accept. | Sequence editor, "AI Tools" | V |
| Instantly | Deliverability check in the Preview dialog, next to test send. | Preview dialog | V |
| Instantly | "Deliverability AI Agent" reviews DNS, blocklists, bounce rates, provider balance and campaign copy across the workspace. Paid tiers. | Workspace level | V-snippet |
| Smartlead | Readability ("ABC") highlights hard sentences. Spam checker tags phrases as Urgency, Shady, Overpromise or Unnatural. | Editor toolbar | V and 3P |
| Smartlead | SmartDelivery spam test (SpamAssassin score, inbox placement). | Review step, separate product | V |
| lemlist | "Deliverability Boost" panel with three checks: "Content - Copywriting", "Content & Tech Check" (structure, links, authentication, spam), "Inbox Placement". | **Right side of the email preview window** | V-snippet, and the preview article confirms checks "on the right" |
| Reply.io | "Email Quality" guidance with concrete targets: subject 3 to 7 words, body up to 125 words, about a third-grade reading level, questions in the body help, avoid words like "Opportunity", "Free", "Ultimate". | Editor | V-snippet |
| Saleshandy | "Sequence Score" from 1 to 100 in six bands, made of three parts. Email Account Setup (mailbox age, daily quota, seconds between sends with over 180 s as ideal, SPF, DKIM, DMARC, blacklists). Sequence Setup (tracking on or off, disconnected mailboxes, percent unverified prospects, number of follow-ups, variants in step 1). Email Writing (merge tags in subject and body, spintax, spam words, plain text vs HTML, word count, invalid merge tags; no thresholds published). | Sequence tab | V |
| Mailshake | In-app copy analyzer for spam words. "SHAKEspeare" AI writer. | Editor | 3P / V title |
| Templates | Instantly: "Templates" button in the editor, by category, plus "Save as Template" on the arrow beside Save. Smartlead: "Email Templates" in the editor. lemlist: template choice is the first screen of campaign creation and the library is multilingual. Apollo: templates are separate objects attached to steps. | | V / 3P |

Opinion: what is genuinely smart here is small. (a) Reply's concrete numeric targets. (b) Smartlead naming why a phrase is bad. (c) lemlist putting the checks beside the preview, which is where a person is already in a judging mindset. (d) Saleshandy's insight that most "email quality" problems are actually setup problems (mailbox age, pacing, unverified addresses), not wording. What is not smart: a single number from 1 to 100 that invites gaming, and spam word lists. lemlist's own blog is titled "Spam words won't send you to spam".

Could not verify: exact thresholds inside lemlist's copywriting check, Instantly's deliverability score mechanics, anything on Reply's page beyond the excerpt.

---

## 5. Scheduling and pacing controls

### Windows and timezones

| Tool | Timezone model | Tag |
|---|---|---|
| Instantly | **One timezone per campaign.** For mixed timezones they say to split the CSV and make separate campaigns. Multiple schedule layers exist for day-by-day variation only. | V |
| Smartlead | Campaign timezone by default. Per-lead timezone is possible if the CSV has a `timezone` column in IANA format. | V-snippet |
| lemlist | Toggle "Timezone based schedule": sends by each lead's timezone, with a required fallback timezone. Schedules can be saved as templates, several per campaign. | V |
| Woodpecker | Checkbox "Use the prospect's timezones if available". Delivery windows are set **per email step**, up to 3 windows each. | V |
| Apollo | Schedules are reusable objects. Option to use each contact's local timezone, falling back to the schedule's timezone. | V-snippet |

Our recipient-timezone windows are level with lemlist, Woodpecker and Apollo and ahead of Instantly. Because our leads come from Maps with an address, we can resolve timezone for essentially every lead, which the CSV-based tools cannot.

Holidays: no tool I read documents a holiday calendar. Unverified for all.

### Limits and pacing

| Control | Instantly [V] | Smartlead [V] | lemlist [V] | Woodpecker [V] |
|---|---|---|---|---|
| Daily cap | "Daily Limit" per campaign across all its mailboxes, plus a per-mailbox limit. Suggests 30 campaign + 10 warmup per mailbox. | Per-mailbox limits shown when assigning mailboxes. "New Leads per Day" per campaign. | Per sender, shared by all campaigns, on a **rolling 24-hour window**. "A maximum cap, not a guaranteed number." Suggests 20 to 40 a day for young mailboxes, 100 max. | "Daily opening email limit", default 50, capped by provider |
| Gap between sends | Minimum gap default 9 min, plus random extra default 5 min | "Send Interval" plus small automatic variations | "Reach a new lead every" X minutes (they suggest 15 to 20). Applies to first step only; follow-up timing is automatic. | Automatic |
| New leads vs follow-ups | "Max New Leads" per day. "Prioritize New Leads" toggle (higher plans only). | A percentage split (API name `follow_up_percentage`). Default favours follow-ups. | Shared cap, no stated priority | Opening limit only |
| Ramp-up | Belongs to the warm-up product, not the campaign | Same | Advice to raise limits by hand (50, 75, 100) | n/a |

### Stop and safety rules

| Rule | Instantly [V] | Smartlead [V] | lemlist [V] |
|---|---|---|---|
| Stop on reply | "Stop sending emails on reply" | Stop on Replies (recommended), Clicks or Opens | Automation: "When people reply" |
| Auto-replies and OOO | "Stop Sending Emails on Auto-reply". They recommend turning it off so "AI Smart Pause" can pause and resume instead. | AI labels OOO and re-evaluates follow-ups to OOO leads | Reply scoring includes OOO detection |
| Whole company | "Stop Campaign for Company on Reply" and "Limit emails per company" | Company-level auto-pause, domain rate limiting | "Also pause contacts from the same company" on each trigger |
| Bounce auto-pause | **On by default.** Pauses at 5 percent bounces, checked only after 200 emails. Threshold lives in global Preferences behind a gear icon. Campaign shows a "Bounces" error. 7-day grace after resuming. | "High Bounce Rate Auto Protection", per campaign, you type the percent. Also fires a webhook. | Not found |
| Risky addresses | "Allow Risky Emails" also switches off BounceProtect | Import-time "Community Bounce List" | Lead shows a deliverability status at review |
| Other auto-pauses | | Out of credits, mailbox disconnected, leads exhausted, billing | |

### Editing after launch (a quiet footgun area)

- lemlist [V]: you can edit future steps, and leads who have not received a step get the new text, **including leads already queued for it**. You can append steps. You cannot insert in the middle. For big changes they say to duplicate the campaign.
- Instantly [V]: "Always pause your campaign before adding new steps." And "campaign progress may reset after adding a new step, as previously completed leads will be reactivated." So appending a step to a finished campaign emails everyone again.
- Smartlead [V]: variant distribution mode locks at launch.
- lemlist [V]: "Select as winner" is permanent.

---

## 6. Analytics placement

### What the campaign overview shows first

- **Instantly [V]**, Analytics tab, top to bottom: headline tiles (Sequence started, open rate, click rate, reply rate, Opportunities), a campaign progress percent (share of leads who finished every step; hover for the breakdown; **no ETA or forecast**), a chart with a gear to choose metrics and a date range, then the "Step Analytics" table with a row per step and variant and the variant toggles, then an "Activity" log filterable by event and exportable to CSV. Bounce reasons are in the same tab.
- **lemlist [V]**, Performance tab: per-lead delivery stats, a "Negative stats signal" health block, "Step details" for step-by-step comparison, CSV export. Reviewers call reporting shallow and exports awkward [3P].
- **Smartlead [3P]**: opens, replies, bounces, positive replies. "You get open rates, reply rates, and bounce rates. That's about it."

Nobody leads with a funnel. The universal order is headline tiles, then a time chart, then a step by variant table. None of the cold email tools show confidence intervals. Our forecast of how long sending will take has no equivalent I could find; lemlist's launch recap showing "time between each lead" is the nearest thing.

### Reply categorisation

- Instantly [V]: lead statuses (Interested, Meeting Booked, Won, Not Interested, Out of Office, Referral, Objection, plus custom labels). "Automatically tag lead status in replies" uses AI. By default AI will not overwrite a label a human set; that needs a separate opt-in, "Update existing lead labels with AI". Statuses feed the "Opportunities" metric and can trigger subsequences.
- Smartlead [vendor blog]: six categories. Interested, Not Interested, Out of Office, Referral, Do Not Contact, Neutral / Needs Review. Temporary OOO is distinguished from "left the company". Manual corrections are allowed. "Positive reply rate" is a selectable A/B winning metric, which is the right metric for cold email.
- lemlist [V]: a manual interested / not interested mark in the lead panel, plus AI reply scoring. Their docs make the key point plainly: "Yes, let's schedule a call" and "Remove me from your list" both count as replies in your stats.

### Unified inbox

- Instantly "Unibox" [V]: all mailboxes in one list. Filter by status, campaign, sending account. Advanced search on from, to, subject, unread, date, campaign ID. Status is set from the thread. Reviewers like it consistently [3P]: "lets me see all my emails in one place".
- Smartlead "Master Inbox" [vendor blog]: left sidebar with Inbox, Sent, Important, Snoozed, Reminders, Scheduled, Archived. Filters by AI category, campaign, mailbox, date, tag. Saved "Views". Opening a lead shows the entire thread and the "Associated Campaign". Bulk categorise, archive, move to another campaign or subsequence, block.
- lemlist Inbox [V]: conversation lists (Unread, Favorites, Snoozed, Archived, Sent only, Untracked). A lead panel on the right with contact details, activities, campaigns, tasks, and the interested / not interested mark.

Common pattern: **thread in the middle, lead and campaign panel on the right, category control on the thread itself, filter by campaign on the left.** A reply always shows which campaign and step produced it.

---

## 7. What users complain about, and what they praise

All of this section is [3P] unless marked. G2 blocked direct fetching, so G2 quotes arrive via review blogs.

### Complaints and footguns

1. **Warm-up scores that do not match reality (Instantly).** A Salesforge tester reports mailboxes with heat scores above 85 while an inbox placement test showed 32, 38 and 41 percent spam. A Reddit thread is titled "Instantly.ai Just Admitted Their Warmup Network Got My Brand New Domains Reputation Blocked". Sparkle says 45 percent of Instantly's low-star reviews mention spam or bounces. Lesson: a green health number the user cannot check is worse than no number.
2. **Unpredictable daily volume.** "On some days platform reaches daily limit, on others only 2-3 emails send throughout day" (G2, via Sparkle). Campaign limit, mailbox limit, warm-up, follow-up priority and window all interact and nothing explains the result. lemlist has to state in docs that the limit is "a maximum cap, not a guaranteed number".
3. **Silent failures mid-campaign (Smartlead).** "A mailbox disconnected mid-campaign with no warning, and I lost half a day of sending before I noticed" (G2, via Sparkle). Reliability bugs are the most common Smartlead complaint: campaigns failing to send, warm-up pausing, analytics not loading.
4. **Dense UI (Smartlead, lemlist).** Smartlead is "denser and less intuitive", cluttered beyond 20 campaigns, and "needing days to get their first campaign running". Solo operators find it overwhelming. lemlist: "the first week with multiple sequences and teammates feels overwhelming"; the conditions UI gets dense.
5. **Wrong or blank personalization.** "Sometimes name and company name are not correct" (G2, Instantly AI). Instantly fills missing values with nothing [V]. Mailshake once sent literal braces (2023).
6. **Mandatory wizards and tedious per-lead review (Mailshake, older lemlist).** GMass's 2023 walkthrough counted six Back clicks to return to a campaign after editing settings in Mailshake, no way to send now, and one-by-one email review that "becomes impractical for large campaigns". It also noted lemlist had "no definitive send button". May be outdated, but the launch-per-lead model remains.
7. **Threading confusion.** lemlist keeps a dedicated "Fix emails not threading" article [V]. The blank subject convention plus sender rotation plus CC all break threads.
8. **Irreversible or surprising actions.** lemlist's permanent winner and permanent "Reset Override"; Instantly reactivating completed leads when a step is appended; Smartlead's locked distribution mode [all V].
9. **Open tracking harming delivery.** Instantly's own blog now says pixels hurt inbox placement and that roughly half of opens are Apple prefetches [vendor blog]. Yet open rate remains a selectable auto-optimise metric in Instantly and Smartlead. Optimising on opens is a trap.
10. **Shallow analytics.** Smartlead and lemlist both get this. No significance maths anywhere in the cold email tier.
11. **Pricing creep and paywalled basics.** Instantly moved behaviour triggers to a higher plan; "Prioritize New Leads" is plan-gated [V]; lemlist per-seat costs; Smartlead add-ons.
12. **Support during deliverability emergencies** is slow (Instantly on Trustpilot, Smartlead on G2).

### Praise

- Instantly: "The campaign builder is the cleanest in the cold email category." The split-screen editor. Zero-configuration warm-up. Unibox.
- Smartlead: unlimited mailboxes and rotation that spreads reputation; a clean master inbox; good API and webhooks.
- lemlist: depth of personalization (liquid, images, AI columns), a template library, deliverability checks inside the campaign, helpful support.
- Woodpecker: reliability, and the missing-snippet safety net [V for the feature].
- Saleshandy: Sequence Score catches setup mistakes before a first send [V for the feature].

Could not verify: specific Reddit threads about follow-ups being sent after a reply arrived from a different address (a well known failure in this category, but I found no citable thread today).

---

## 8. What to copy and what to avoid

Context: a solo operator, local-first, plain text, their own mailbox, lists of hundreds rather than tens of thousands. That changes the maths. With 200 leads, most of the scale features above (26 variants, auto-optimise, provider matching, subsequences) are noise, and the most valuable thing the product can do is stop one bad send.

### Patterns worth copying

1. **Turn the Launch section into a live pre-flight list, in the style of lemlist's recap but computed.** Each line is a fact with a state. Blocking: no audience, an empty email, a merge field that has no fallback and is missing for N leads, mailbox not connected. Warning: only one email in the series (Woodpecker's pop-up), 4 versions for 120 leads, a subject over 7 words. Information: "212 businesses, about 9 sending days, first emails go out Monday 9:00 their time, stops for a business on any reply, pauses itself at 3 bounces." The launch button reads "Launch to 212 businesses".
2. **Count fallbacks and missing fields against the real audience, inside the editor.** Under each email: "suburb: 14 of 212 will read 'your area'. owner_name: 61 of 212 missing, no fallback set." Each count opens those leads. This beats Woodpecker (finds out at send time) and Instantly (never finds out). We already have fallback syntax; the missing piece is the count.
3. **Adopt Woodpecker's hold-back as the runtime safety net.** If a lead would still render with an empty field or stray braces at send time, hold that one lead in a "Needs a look" list. Never send it, never stall the campaign.
4. **Preview with the lead list beside the email (lemlist Launch tab) plus search (Instantly "Load data for lead").** Add one button the others lack: "Show me the worst case", which jumps to the lead with the most fallbacks or the longest business name. Sample-based review of 5 to 10 leads, never a forced one-by-one pass.
5. **Offer "Launch to the first 20" next to the full launch.** lemlist's lead-level launch and their own advice both point at small test batches. For someone sending from their real mailbox this is the cheapest protection against a burnt domain. It also gives the forecast and the bounce guard early data.
6. **Put the variant on/off switch and the variant's numbers on the variant tab of the email card.** Instantly pairs toggle and stats, but in Analytics. Go one step further: the chip for version B reads "B, 48 sent, 3 replies, too early to call". Pausing must be reversible. Never copy lemlist's permanent "Select as winner".
7. **Make threading an explicit choice on emails 2 to 6**: "Send as a reply in the same conversation" (default) or "Start a new conversation", which reveals a subject field. Do not use the blank-subject convention. In preview show "Re: [first subject]", never a blank.
8. **Count gaps in sending days and say the outcome in words** (lemlist's model): "3 working days later. A Friday email is followed up on Wednesday." Keep days as the only unit. Hours and minutes are an Instantly feature for high-volume senders.
9. **Inline, deterministic copy hints beside the preview, not a score.** Use Reply.io's thresholds as a starting point: subject 3 to 7 words, body under about 125 words, at most one link, a question present, no pasted rich text. Name the reason the way Smartlead does ("sounds like urgency"). Each hint is one quiet line and none block launch. Skip the 1 to 100 score.
10. **A bounce guard that is on by default, visible in the Launch section, and scaled to small lists.** Instantly's 5 percent after 200 emails would never fire for a 150-lead campaign. Use an absolute early rule ("pause if 3 of the first 30 bounce") and a percent rule afterwards. When it fires, say so in plain words with the bounced addresses listed.
11. **Stop for the whole business when anyone there replies**, default on. For Maps leads "same company" means same place or same domain (info@ and owner@ at one cafe). All three leaders have this; Instantly hides it in Advanced Options. Put it in the pre-flight sentence.
12. **Treat out-of-office as pause and resume, not as a reply that ends the series.** Instantly (AI Smart Pause) and Smartlead (OOO re-evaluation) both moved this way.
13. **Make "interested" the headline result, not "replied".** lemlist's docs state the problem and Smartlead offers positive reply rate as the winner metric. A one-tap label on each reply (interested, not interested, out of office, wrong person, unsubscribe) is enough. Run the confidence interval on interested replies as well as all replies.
14. **Every reply shows which campaign, which email number and which version it answered,** with the lead panel on the right (the shared Unibox, Master Inbox, lemlist layout). Even a simple local replies list should carry those three facts.
15. **Keep AI personalization in a lead column.** If AI-written lines are ever added, follow lemlist, Instantly and Clay: generate into an `{opener}` field in the audience table, test the prompt on 5 leads first, flag empty outputs, let the user edit cells. The email references the field with a fallback as usual.
16. **Explain pacing in one sentence** so daily volume never feels random: "Today: up to 40 emails. 26 follow-ups go first, then 14 new businesses." If a control is needed at all, make it a two-option choice (finish follow-ups first, or reach new businesses first), not Smartlead's percentage.
17. **Keep what is already ahead of the market**: one letter per lead for the whole series, confidence intervals with "too early to call", the sending forecast (no competitor has one), recipient-timezone windows resolved from the Maps address, named exclusions (Smartlead's four import checkboxes are the same idea). The one long page is right for a solo operator; tabs suit teams with many campaigns. Add a small sticky rail showing the state of each section (Who, Emails, When, Launch) so the page has the orientation tabs provide.

### Patterns to avoid

1. **An Options tab with 19 settings** (Instantly) or a Settings tab with six groups (Smartlead). Make the safe choice the default and state it in the pre-flight sentence. Anything the user never needs to change should not be a control.
2. **Global preferences that silently change campaign behaviour.** Instantly keeps the bounce threshold and the variant balancing mode in account Preferences, away from the campaign they affect.
3. **Auto-picking winners with no sample threshold, or on opens.** With lists of hundreds this picks noise. Plain text has no open data anyway. Keep the human in the loop with an honest verdict, as Outreach does.
4. **More than 4 versions.** 26 exists because agencies send 50,000 emails. Guide the other way: "With 180 businesses, 2 versions is the most you can learn from."
5. **Re-rolling the version at each step** (Apollo, Saleshandy, Woodpecker). It makes replies to follow-ups impossible to attribute.
6. **Silent empty strings (Instantly) or literal braces (Mailshake).**
7. **Spintax and Liquid conditionals.** They exist to defeat pattern filters at volume and to serve mixed B2B lists. They make preview unpredictable and syntax errors likely, and Instantly's own docs resort to a hidden-div hack. Versions plus fallbacks cover a solo operator. If one conditional is ever wanted, make it a UI affordance ("only include this sentence if rating is known"), not a template language.
8. **Branching canvases (if opened, if clicked).** We have no opens or clicks in plain text, reviewers find conditions overwhelming, and Woodpecker admits branches wreck A/B statistics on small lists. "Replied, so stop" is the only branch needed.
9. **Irreversible actions with quiet consequences**: permanent winners, permanent override resets, appending a step that re-emails finished leads. If adding email 4 after launch is ever allowed, say exactly who will receive it before saving.
10. **Mandatory wizards with a Back-button maze** (Mailshake) and **forced one-by-one lead review** (older lemlist, Mailshake).
11. **Health numbers the user cannot verify** (warm-up heat scores, 1 to 100 sequence scores). Show facts: "0 bounces in 60 sent", "SPF and DKIM found for yourdomain.com".
12. **A daily "limit" that is really a maximum, unexplained.** If fewer emails went out than expected, say why.
13. **Text locked after launch with no escape hatch.** Our lock protects the test, which is good, but lemlist's rule is more humane and still sound: an email nobody has received yet can be corrected, an email someone has received cannot. Recommended: allow edits only on emails with zero sends, record the edit in the results, and offer "duplicate for the remaining businesses" for anything bigger. Always allow pausing a version.

---

## Comparison table

Y = present and verified on a vendor page. (Y) = vendor excerpt or third-party only. N = documented as absent. ? = not verified.

| Feature | Instantly | Smartlead | lemlist | Woodpecker | Apollo | Saleshandy | maps-leads today |
|---|---|---|---|---|---|---|---|
| Builder shape | Tabs: Leads, Sequences, Schedule, Options | Tabs: Leads, Sequence, Email Accounts, Settings | Tabs: Sequence, Lead list, Launch, plus gear | PATH, PROSPECTS, SUMMARY | Sequence steps plus Settings, Scheduling, Ruleset | Sequence plus tabs | One long page |
| Pre-launch review in product | ? (docs checklist only) | Y (3 required items; review step in older flow) | Y (Launch tab plus recap modal) | Y (SUMMARY, 1-email pop-up) | ? | Y (Sequence Score) | Launch section |
| Max variants per step | 26 | 10 | 2 (or whole sequence) | 5 | several | 26 | 4 |
| Lead keeps same variant all series | ? | ? | Only in whole-sequence test | N | N | N | Y |
| Weighted split | N (balanced) | Y (10 percent steps, AI sample) | N (50/50) | N | N | N | N |
| Pause a variant | Y toggle | ? | n/a | Y toggle | (Y) | Y | ? |
| Winner selection | Manual or auto-optimise | Auto by metric | Manual, permanent | Manual, winner icon | Manual, "90% confidence" advice | ? | Manual with CI and "too early to call" |
| Significance shown in product | N | N (3P) | N | N | N | N | Y |
| Delay units | d / h / m | days | sending days | d / h / m | (business days) | days | days |
| Same-thread control | Blank subject | Blank subject | Blank subject | Explicit option | Explicit option (Y) | Blank subject | ? |
| Branches | Subsequences after launch | Subsequences | Conditions in the sequence | YES / NO paths | (Y) | ? | N |
| Fallback syntax | `{{x | y}}` | `{{#if}}` block | `{{x|y}}` | `{{X | "y"}}` with dialog | (Y) | ? | `{x|y}` |
| Missing-variable guard | N (empty string) | ? | (Y) filter at launch | Y (pause prospect, To Check tab) | ? | Y (score input) | Fallbacks only |
| Spintax / Liquid | Y / Y | Y (AI Spintax) / block ifs | Y / Y | ? | ? | Y / ? | N |
| AI columns for first lines | (Y) | (Y) | Y | ? | (Y) | ? | N |
| Per-lead preview | Y (load lead) | Y (review step) | Y (split view, per-lead override) | Y (red highlights) | ? | ? | Y |
| Send test | Y | Y | Y | Y (whole sequence) | ? | ? | Y |
| Copy checks in editor | AI spam words, deliverability check | Readability, spam categories | Deliverability Boost in preview | ? | ? | Sequence Score | N |
| Recipient timezone | N | (Y) via CSV column | Y toggle with fallback | Y checkbox | (Y) | ? | Y |
| Sending forecast / ETA | N (progress percent only) | ? | Recap shows gap between leads | ? | ? | ? | Y |
| New leads vs follow-ups control | Toggle (paid) plus max new per day | Percentage | Shared cap | Opening-email limit | ? | ? | ? |
| Bounce auto-pause | Y (5 percent after 200, default on, global) | Y (per campaign) | ? | ? | ? | ? | ? |
| Stop for whole company | Y | Y | Y | ? | (Y) ruleset | ? | ? |
| Reply categories | Y (AI labels) | Y (6 categories) | Y (manual plus AI) | Y ("interest level") | ? | ? | ? |
| Unified inbox | Y Unibox | Y Master Inbox | Y Inbox | ? | (Y) | (Y) | ? |
| Editable after launch | Y (pause first; appended steps reactivate finished leads) | Partly (distribution locked) | Future steps yes, no mid-insert | Y | ? | ? | N (locked) |

---

## Sources

Vendor help centers and docs (primary)

- Instantly, complete setup guide: https://help.instantly.ai/en/articles/6386134-how-to-create-a-campaign-complete-setup-guide
- Instantly, Campaign Options: https://help.instantly.ai/en/articles/6222396-campaign-options
- Instantly, A/Z testing: https://help.instantly.ai/en/articles/6661549-a-z-testing-how-to-create-email-variants
- Instantly, Liquid syntax: https://help.instantly.ai/en/articles/6687668-liquid-syntax
- Instantly, Spintax and placeholders: https://help.instantly.ai/en/articles/6384663-how-to-use-spintax
- Instantly, AI Spam Words Checker: https://help.instantly.ai/en/articles/9921051-ai-spam-words-checker
- Instantly, AI Prompts and Enrichment: https://help.instantly.ai/en/articles/8317073-ai-prompts
- Instantly, Subsequences: https://help.instantly.ai/en/articles/7251329-subsequences
- Instantly, email threading: https://help.instantly.ai/en/articles/7914807-keep-email-sequences-in-the-same-thread
- Instantly, multiple schedules: https://help.instantly.ai/en/articles/6573695-multiple-sending-schedules
- Instantly, start and end date: https://help.instantly.ai/en/articles/6756707-campaign-start-end-date
- Instantly, Analytics: https://help.instantly.ai/en/articles/6602310-analytics
- Instantly, Campaign Progress: https://help.instantly.ai/en/articles/13681918-campaign-progress
- Instantly, High Bounce Auto-Pause: https://help.instantly.ai/en/articles/9823139-high-bounce-auto-pause-feature
- Instantly, adding steps to an active campaign: https://help.instantly.ai/en/articles/13924383-how-to-add-new-steps-to-an-active-campaign
- Instantly, Unibox: https://help.instantly.ai/en/articles/6576561-how-to-manage-unibox-best-practices-for-replying-to-leads
- Instantly, AI reply labels: https://help.instantly.ai/en/articles/9712488-ai-custom-reply-labels
- Instantly, Preferences overview: https://help.instantly.ai/en/articles/11864294-preferences-settings-overview
- Smartlead, create a campaign (new version): https://helpcenter.smartlead.ai/en/articles/442-how-to-create-an-email-campaign-in-smartlead-the-new-version
- Smartlead, creating a cold email campaign (older wizard): https://helpcenter.smartlead.ai/en/articles/34-creating-a-cold-email-campaign
- Smartlead, A/B testing: https://helpcenter.smartlead.ai/en/articles/146-how-to-do-ab-testing-with-smartlead
- Smartlead, AI auto-adjust A/B: https://helpcenter.smartlead.ai/en/articles/135-ai-auto-adjust-ab-testing
- Smartlead, fallbacks and conditionals: https://helpcenter.smartlead.ai/en/articles/26-how-to-use-liquid-syntax-to-win-leads-fallbacks
- Smartlead, bounce auto protection: https://helpcenter.smartlead.ai/en/articles/274-what-is-high-bounce-rate-auto-protection-in-smartlead
- Smartlead, why campaigns pause: https://helpcenter.smartlead.ai/en/articles/69-reasons-for-campaigns-getting-paused-in-smartlead
- Smartlead, how follow-ups work: https://helpcenter.smartlead.ai/en/articles/59-how-do-follow-ups-work-in-smartlead
- Smartlead, lead-level timezones: https://helpcenter.smartlead.ai/en/articles/230-how-to-setup-timezones-on-a-lead-level
- Smartlead, lead categories: https://helpcenter.smartlead.ai/en/articles/51-lead-categories
- Smartlead, Master Inbox (vendor blog): https://www.smartlead.ai/blog/master-inbox-new-features
- lemlist, create a campaign: https://help.lemlist.com/en/articles/4452686-create-a-lemlist-campaign
- lemlist, launch stage: https://help.lemlist.com/en/articles/4452680-understand-the-launch-stage
- lemlist, campaign sequencing: https://help.lemlist.com/en/articles/12875247-understand-campaign-sequencing-in-lemlist
- lemlist, delays between steps: https://help.lemlist.com/en/articles/4452783-set-up-delays-between-steps
- lemlist, A/B test a step: https://help.lemlist.com/en/articles/4494106-use-a-b-tests-on-a-sequence-step
- lemlist, choose a winner: https://help.lemlist.com/en/articles/5914746-choose-a-winning-a-b-test-sequence
- lemlist, A/B test a full sequence: https://help.lemlist.com/en/articles/4452796-a-b-test-a-full-campaign-sequence
- lemlist, custom variables and fallbacks: https://help.lemlist.com/en/articles/4518866-add-custom-variables-to-your-email
- lemlist, AI variables: https://help.lemlist.com/en/articles/9617068-how-to-use-ai-variables-to-personalize-and-clean-lead-data
- lemlist, custom images: https://help.lemlist.com/en/articles/4494110-add-personalized-text-to-images
- lemlist, preview before sending: https://help.lemlist.com/en/articles/10191432-preview-your-campaign-before-sending
- lemlist, same-thread follow-ups: https://help.lemlist.com/en/articles/7203038-keep-follow-up-emails-in-the-same-thread-in-lemlist
- lemlist, sending algorithm: https://help.lemlist.com/en/articles/4452763-understand-lemlist-s-sending-algorithm
- lemlist, sending schedule: https://help.lemlist.com/en/articles/4522667-set-a-sending-schedule
- lemlist, edit an active campaign: https://help.lemlist.com/en/articles/7219785-edit-an-active-campaign
- lemlist, skip and un-skip leads: https://help.lemlist.com/en/articles/4452758-how-to-skip-and-un-skip-leads
- lemlist, Inbox: https://help.lemlist.com/en/articles/10035229-use-the-lemlist-inbox
- lemlist, mark leads interested: https://help.lemlist.com/en/articles/4452776-mark-leads-as-interested-or-not
- Woodpecker, quickstart: https://woodpecker.co/help-center/en/articles/5234626-quickstart-vol-1-how-to-set-up-a-cold-email-campaign
- Woodpecker, A/B tests: https://woodpecker.co/help-center/en/articles/5241911-how-to-carry-out-an-a-b-test
- Woodpecker, A/B testing FAQ: https://docs.woodpecker.co/en/articles/5241940-a-b-testing-faq
- Woodpecker, missing snippet issue: https://woodpecker.co/help-center/en/articles/5738904-how-to-fix-the-missing-snippet-issue
- Woodpecker, snippet fallbacks: https://woodpecker.co/help-center/en/articles/6636519-how-can-i-set-up-the-snippet-fallbacks
- Woodpecker, follow-ups as separate message: https://woodpecker.co/help-center/en/articles/5259162-sending-follow-ups-as-a-separate-message
- Mailshake, advanced campaign: https://docs.mailshake.com/article/412-how-do-i-create-an-advanced-campaign
- Mailshake, A/B testing: https://docs.mailshake.com/article/176-how-do-i-get-started-with-a-b-testing
- Mailshake, FAQ: https://docs.mailshake.com/article/146-faq
- Saleshandy, Sequence Score: https://docs.saleshandy.com/en/articles/8006454-sequence-score-what-why-and-how-to-set-it-up
- Saleshandy, A-Z testing: https://docs.saleshandy.com/en/articles/7055206-a-z-testing-explained
- Apollo, A/B test in a sequence (403, excerpt only): https://knowledge.apollo.io/hc/en-us/articles/4410749683597-Use-an-A-B-Test-in-a-Sequence
- Apollo, sending schedule (403, excerpt only): https://knowledge.apollo.io/hc/en-us/articles/4409477927309-Configure-a-Sequence-Sending-Schedule
- Apollo, create a sequence (API): https://docs.apollo.io/reference/create-sequence
- Reply.io, email quality check (403, excerpt only): https://reply.io/email-quality-check/
- Reply.io, step delays (403, excerpt only): https://support.reply.io/en/articles/1303146-how-does-reply-count-step-delays
- Reply.io, conditional sequences (vendor blog): https://reply.io/blog/multichannel-conditional-sequences/
- Outreach, A/B testing overview: https://support.outreach.io/support/solutions/articles/159000426460-outreach-a-b-testing-overview

Third-party and competitor reviews (directional)

- Sparkle, Instantly review: https://sparkle.io/blog/instantly-ai-review/
- Sparkle, Smartlead review: https://sparkle.io/blog/smartlead-review/
- Salesforge, Instantly review (competitor): https://www.salesforge.ai/blog/instantly-ai-review
- Salesforge, Smartlead review (competitor): https://www.salesforge.ai/blog/smartlead-ai-review
- Ciela, Smartlead on Reddit: https://ciela.ai/blogs/smartlead-reddit-review
- MarketBetter, Smartlead review 2026: https://marketbetter.ai/blog/smartlead-review-2026/
- MarketBetter, Woodpecker review 2026: https://marketbetter.ai/blog/woodpecker-review-2026/
- Snov, lemlist review (competitor): https://snov.io/blog/lemlist-review/
- lemlist, Saleshandy review (competitor): https://www.lemlist.com/blog/saleshandy-review
- Instantly blog, Instantly vs Smartlead A/B testing (competitor): https://instantly.ai/blog/instantly-vs-smartlead-ab-testing-features/
- Instantly blog, tracking pixels and deliverability: https://instantly.ai/blog/email-tracking-and-deliverability-why-tracking-pixels-can-hurt-your-inbox-placement/
- GMass, lemlist and Mailshake creation flows (December 2023, may be outdated): https://www.gmass.co/blog/campaign-creation-lemlist-mailshake/
- LeadHaste, Clay to Smartlead workflow: https://leadhaste.com/blog/clay-to-smartlead-workflow
- Clay University, Smartlead walkthrough: https://university.clay.com/lessons/personalized-direct-email-campaigns-step-by-step-walkthrough-with-smartlead-automated-outbound
- Salesforge, QuickMail review (competitor): https://www.salesforge.ai/blog/quickmail-review
- G2 pages (blocked to direct fetch; cited via the blogs above): https://www.g2.com/products/smartlead/reviews and https://www.g2.com/products/lemlist/reviews
