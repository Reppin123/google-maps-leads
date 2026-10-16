# How the big platforms send mass email, how the numbers are measured, and what maps-leads should do

Date: 2026-09-19. Scope: research only, no code was changed.

How to read this report. Every claim carries one of four tags.

- **[V]** Verified today against a primary source (the page was fetched on 2026-09-19). Note: pages were read through a fetch tool that summarises, so re-read the source before quoting any line in a legal or public document.
- **[K]** Long-standing, widely documented industry knowledge. Not re-fetched today.
- **[C]** A vendor or blogger claim. Usually self-interested. Treat as a hint, not a fact.
- **[?]** Could not verify. Stated so you know the gap.

I also read `outreach/mailer.py` (read only) so the recommendations in section 6 point at real behaviour in our code, not at a generic sender.

---

## 1. How Mailchimp, Loops, Klaviyo, SendGrid, SES, Postmark, Resend and Mailgun send mass email

### 1.1 The architecture in plain terms

A mailbox (Google Workspace, Microsoft 365) is a product for a person writing to people. An email service provider (ESP) is a product for software writing to many people. They are built differently.

1. **Intake.** The customer hands the ESP a message through an HTTP API or SMTP submission. The ESP answers "accepted" at once and puts the message on a queue. Nothing has been delivered yet.
2. **Pre-send gates.** Before the message reaches a mail server, the ESP checks it against the customer's suppression list (past hard bounces, spam complaints, unsubscribes) and sometimes a platform-wide list. A suppressed address is dropped silently or returned as an error. This gate is the single most important reputation control the platforms have, and it cannot be bypassed by the customer.
3. **MTAs.** The message goes to a Mail Transfer Agent: server software whose only job is to deliver over SMTP to the recipient's MX host. Large ESPs run commercial or in-house MTAs (PowerMTA, Momentum, KumoMTA, Halon, or custom, [K]). An MTA keeps one queue per destination (gmail.com, outlook.com, yahoo.com, each corporate domain) and per sending IP.
4. **IP pools.** Each MTA sends from a set of IP addresses.
   - **Shared pool:** many customers send from the same IPs. Reputation is shared. The ESP protects the pool by vetting customers, banning cold lists, and throwing out bad senders fast. Good for low or uneven volume. Default at Mailchimp, Loops, Resend, Postmark, SendGrid lower tiers, Klaviyo.
   - **Dedicated IP:** one customer owns the reputation of the IP. Only makes sense with steady volume. Klaviyo's own guidance is to consider it when you consistently send over 1,000,000 emails a month [V, Klaviyo help]. SES offers "standard" dedicated IPs (you warm them) and "managed" dedicated IPs (SES warms and scales them) [K].
   - Platforms also split pools by mail type. Postmark separates transactional and broadcast "message streams" so newsletters cannot hurt password resets [K].
5. **Warmup.** Mailbox providers distrust a new IP or a new domain that suddenly sends a lot. Warmup means starting small and growing over weeks so the receivers can watch engagement and build a reputation. Klaviyo defines a cold IP as one not used in 30 days and a cold domain as one registered in the last 30 days or never used to send [V, Klaviyo help]. On a shared pool the IPs are already warm; the customer's **domain** still has to earn its own reputation, because Gmail in particular weighs domain reputation heavily [K].
6. **Rate shaping per receiver.** The MTA limits connections, messages per connection and messages per minute for each destination, per IP. Limits come from published guidance and from live feedback: when Gmail answers `421 4.7.28` (unusual rate) or Yahoo answers a `421 4.7.0 [TSS04]` deferral, the MTA slows that queue down automatically and speeds up again later ("adaptive delivery", "backoff mode" in PowerMTA) [K].
7. **Queues and retries.** A 4xx answer means "try later". The MTA re-queues with growing delays (minutes, then hours) for a maximum of roughly 1 to 5 days depending on the platform, then gives up and records a soft bounce that expired. A 5xx answer means "never", is recorded at once as a bounce and classified (see section 3). SES retries internally and reports final outcome through events [K].
8. **Feedback intake.** The ESP owns the bounce address (Return-Path), so asynchronous bounce messages come back to the ESP, not the customer. The ESP is also signed up to complaint feedback loops at the mailbox providers that offer them. Bounces and complaints flow into the suppression list, which closes the loop with step 2.
9. **Events out.** Delivered, bounced, complained, opened, clicked, unsubscribed are published to the customer as webhooks or dashboards.

### 1.2 Authentication and the DNS records customers are asked to add

The idea: mail is physically sent by the ESP's servers, but it must prove it speaks for the customer's domain. Four records do this.

- **SPF** authorises the sending IPs for the **envelope sender domain** (Return-Path, also called MAIL FROM or bounce domain). It is checked against the Return-Path domain, not the visible From.
- **DKIM** is a cryptographic signature in the header. `d=` names the signing domain. Platforms sign with the **customer's** domain by asking the customer to publish CNAME records that point at keys the platform hosts. CNAME delegation lets the platform rotate keys without the customer touching DNS again.
- **DMARC** is the customer's policy at `_dmarc.domain`. It passes if SPF passes **and** the Return-Path domain aligns with the From domain, **or** DKIM passes **and** `d=` aligns with the From domain. One aligned pass is enough.
- **Custom Return-Path (bounce domain).** By default the Return-Path is the ESP's domain (for example `amazonses.com`), so SPF passes but does not align. A custom MAIL FROM subdomain (for example `bounce.customer.com`) fixes SPF alignment and still routes bounces to the ESP, because its MX points at the ESP.
- **BIMI** shows a brand logo next to the message. Needs DMARC at enforcement (`p=quarantine` or `p=reject`), an SVG logo, and for Gmail a Verified Mark Certificate or Common Mark Certificate [K]. Irrelevant for cold email from a mailbox; listed for completeness. Resend lists BIMI as a domain feature [V].

Records requested, by platform:

| Platform | What the customer adds | Status |
|---|---|---|
| Amazon SES | Easy DKIM: 3 CNAMEs `<token>._domainkey.domain` -> `<token>.dkim.amazonses.com`, 2048-bit key by default. Optional custom MAIL FROM: MX `bounce.domain` -> `feedback-smtp.<region>.amazonses.com` plus TXT `v=spf1 include:amazonses.com ~all`. DMARC TXT is the customer's job. | 2048-bit default [V]; record shapes [K] |
| SendGrid | "Automated security" on: 3 CNAMEs: `em1234.domain` -> `u1234567.wl123.sendgrid.net` (this is the Return-Path and SPF host), `s1._domainkey` and `s2._domainkey` -> `s1.domainkey.u1234567.wl123.sendgrid.net` etc. Plus `_dmarc` TXT `v=DMARC1; p=none;`. Link branding adds 2 more CNAMEs. Automated security off: MX + SPF TXT + DKIM TXT on the `em` host. | [V] |
| Postmark | DKIM TXT at `<selector>._domainkey.domain`, and a Return-Path CNAME `pm-bounces.domain` -> `pm.mtasv.net`. DKIM is mandatory for verification. | [V] |
| Mailchimp | 2 CNAMEs for DKIM (shown in the account; historically `k2._domainkey` and `k3._domainkey` -> `dkim2.mcsv.net`, `dkim3.mcsv.net`) plus a `_dmarc` TXT. | 2 CNAME + DMARC [V]; exact hostnames [K] |
| Klaviyo | "Branded sending domain": up to 3 CNAMEs (static routing) or 4 NS records (dynamic routing, which delegates a whole subdomain to Klaviyo) plus 1 TXT for ownership. The records cover SPF and DKIM. | [V] |
| Resend | Built on SES. On a `send.` subdomain: MX -> `feedback-smtp.<region>.amazonses.com` and TXT SPF `include:amazonses.com`; DKIM TXT at `resend._domainkey`. Also offers custom Return-Path, tracking domain, enforced TLS, BIMI. | features [V]; record shapes [K] |
| Loops | Built on SES. MX and SPF TXT on `envelope.<sendingdomain>` (MX value seen in their docs: `10 feedback-smtp.us-east-1.amazonses.com`), DKIM CNAMEs, and a DMARC record "so that you have one". Recommends sending from a subdomain such as `mail.company.com`. | [V] |
| Mailgun | TXT SPF `v=spf1 include:mailgun.org ~all`, DKIM TXT at a selector such as `pic._domainkey` or `smtp._domainkey`, MX to `mxa/mxb.mailgun.org` for bounce and inbound handling, CNAME `email.domain` -> `mailgun.org` for open and click tracking. Recommends a subdomain. | [K] |

Verification flow is the same everywhere: the platform generates the records, the customer pastes them at the DNS host, the platform polls DNS until they resolve, then marks the domain verified and starts signing with it.

### 1.3 Suppression lists and how they are enforced

- **Per account.** Every platform keeps a list per customer (or per stream/audience) of hard bounces, spam complaints and unsubscribes, checked before each send.
- **SES.** Account-level suppression list is on by default for accounts created after 2019-11-25. Only **hard** bounces are added. Addresses stay until removed. Sends to a suppressed address are accepted but not delivered and do not count toward the reputation bounce rate. SES also keeps a **global** suppression list across all customers: hard bounces are added there as well. Important detail: "Gmail doesn't provide complaint data to SES", so Gmail spam clicks never reach the suppression list [V].
- **Postmark.** A hard bounce or spam complaint deactivates the address. Hard bounces can be reactivated by the customer; a spam complaint cannot. Soft bounces are not suppressed [V via Postmark docs search].
- **Mailchimp.** Hard bounces are "cleaned" at once; repeated soft bounces are converted to cleaned (commonly documented as after 7 soft bounces for a contact with no activity, 15 for one with activity) [K]. Unsubscribes are per audience and the unsubscribe link is mandatory and must be Mailchimp's own [V].
- **Global enforcement** works because the platform, not the customer, sits at the pre-send gate. The customer cannot email a suppressed address even by re-importing it.

### 1.4 What Loops adds on top of SES

SES is plumbing: an API, MTAs, IP pools, events. It has no contacts, no editor, no unsubscribe pages, no automation. Loops (and Resend) buy deliverability infrastructure from SES and add the product:

- contact database, mailing lists, segmentation, event-triggered "loops" (automations);
- an editor and templates, and a transactional API in the same tool;
- hosted unsubscribe and preference pages, List-Unsubscribe headers, automatic suppression of bounces and complaints by consuming SES events;
- a guided domain setup that wraps the SES identity, custom MAIL FROM and DKIM records behind one screen, and adds a DMARC record if you have none [V];
- customer vetting and an acceptable-use policy, because Loops' SES account reputation is shared by all its customers. If one Loops customer sends cold mail, SES's 5%/0.1% review thresholds hit Loops as a whole. That is why a platform built on SES is **stricter** than SES itself about list sources.

### 1.5 Why platforms can send millions and a Workspace mailbox is capped near 2,000 a day

Google Workspace limits [V, Google Workspace Admin Help]: 2,000 messages per day per user (500 on trial accounts, 1,500 for mail merge), 3,000 external recipients per day, 2,000 **unique** external recipients per day, 100 recipients per message over SMTP. Going over means the user "can't send new messages for up to 24 hours". These are hard product limits and have nothing to do with the 5,000/day bulk sender rule.

Reasons for the gap:

1. A mailbox sends through **Google's shared outbound IPs**, the same ones used by every other Workspace customer. Google caps each user so one account cannot damage those IPs. The cap is an anti-abuse control, not a capacity limit.
2. An ESP delivers **directly to recipient MX hosts from its own IPs** with its own reputation, its own feedback loops, its own per-receiver rate shaping, and no per-user quota. Its limit is reputation, not a counter.
3. An ESP enforces permission. It can afford high volume because complaint rates on opted-in mail stay low. Cold mail at that volume would burn the pool in days, which is why every ESP bans it (next section).

Microsoft 365 for comparison: 10,000 recipients per day and 30 messages per minute per mailbox [K]. The planned per-mailbox External Recipient Rate limit of 2,000 per day was **cancelled** on 2026-01-06; a tenant-level limit (TERRL) is rolling out instead [V via Office365 IT Pros and Microsoft community posts].

### 1.6 What the acceptable-use policies say about cold, purchased and scraped lists

Every platform in the question bans it. Quotes:

- **Mailchimp** (Acceptable Use Policy, last updated 2025-09-26) [V]. Prohibited: "Upload or send email Campaigns to purchased, rented, third-party, co-reg, publicly available data, or partner lists of any kind." Also: "You must be able to point to an opt-in form or show other evidence of consent for any commercial or marketing email you send." And spam "can be in the form of bulk emails or one to one commercial emails". Note "publicly available data": that is scraped Google Maps addresses, named directly.
- **Twilio SendGrid** (Twilio Email Policy, last updated 2026-04-09) [V]. Prohibited: "Using purchased or rented email lists or email lists of recipients that have not affirmatively consented to receive emails from you" and "Sending unsolicited or unwanted emails in bulk". Also: "you must obtain affirmative consent prior to sending any emails to a recipient via the Email Services".
- **Amazon SES** (Sending review process FAQ) [V]. "Don't buy, rent, or share email addresses. Send email only to recipients who explicitly requested to receive email from you." And: "Unsolicited emails are emails that the recipient didn't explicitly ask to receive." Thresholds: bounce rate 5% puts the account under review, 10% may pause sending; complaint rate 0.1% review, 0.5% pause. "For best results, you should maintain a bounce rate below 2%."
- **Postmark** (Terms of Service, 2024-12-10 for new customers) [V]. "Use of a list that has been purchased or rented from a third party is prohibited." "All email lists contained and/or used with respect to the Service must be permission-based subscriptions." Spam complaint rate "must be lower than 1 in 1,000 emails (0.1%)"; bounce rate "has to be lower than 10% of all emails sent".
- **Loops** (Terms of Service, last updated 2025-12-15) [V]. "Purchased lists may not be used with the Services, regardless of the source or permission status." "All recipients must have registered with your software product, have otherwise explicitly engaged with your software, signed up for your marketing email list, or engaged in a business relationship with you."
- **Resend** (Acceptable Use Policy, last updated 2026-08-27) [V]. "You are prohibited from sending unsolicited messages of any kind, including cold outreach, purchased lists, or scraped contact data." "Your bounce rate must be lower than 4%." "Your complaint rate must be lower than 0.08%."
- **Klaviyo, Mailgun**: not fetched today [?]. Both are known to require permission-based lists [K].

Consequence for us: a cold outreach tool **cannot** be built on any of these platforms. Sending from the user's own mailbox is the only compliant architecture, and it is what every cold email vendor does (section 4). It also means the user's mailbox provider terms apply: Google's Gmail program policies prohibit spam and bulk unsolicited mail too [K], which is why volume, targeting and bounce discipline matter so much.

---

## 2. The Google, Yahoo and Microsoft bulk sender rules

### 2.1 What the rules are

**Google** (Email sender guidelines and FAQ) [V]:

- Took effect 2024-02-01. One-click unsubscribe deadline was 2024-06-01. "Starting November 2025, Gmail is ramping up its enforcement on non-compliant traffic."
- A bulk sender is "any email sender that sends close to 5,000 messages or more to personal Gmail accounts within a 24-hour period". Counted per primary domain, subdomains included. "Senders who meet the above criteria at least once are permanently considered bulk senders."
- The guidelines "don't apply to messages sent to Google Workspace accounts". They cover mail to personal Gmail accounts (`@gmail.com`, `@googlemail.com`).
- **All senders:** SPF **or** DKIM; valid forward and reverse DNS (PTR) for the sending IP; TLS; spam rate in Postmaster Tools below 0.3%; RFC 5322 format (one Message-ID, no duplicate single-instance headers); do not impersonate Gmail From headers.
- **Bulk senders add:** SPF **and** DKIM; a DMARC record (`p=none` is enough); From domain aligned with SPF or DKIM; one-click unsubscribe plus a visible unsubscribe link on marketing mail.
- Spam rate: "keep their spam rate below 0.1%" and avoid ever reaching 0.3%. Above 0.3% a bulk sender is "ineligible for mitigation" until the rate stays under 0.3% for 7 consecutive days.
- Unsubscribes: honour within 48 hours.
- On mailto: "We'll continue to support mailto links but they don't meet our one-click unsubscribe requirement."
- Temporary rejection codes used during enforcement include `4.7.27` (SPF), `4.7.30` (DKIM), `4.7.31` (no DMARC policy); permanent versions are `5.7.26`, `5.7.27`, `5.7.30`.
- Postmaster Tools v1 was retired 2025-09-30. The domain and IP reputation charts are gone. v2 keeps spam rate, feedback loop and delivery errors and adds a compliance status dashboard [V via Google help page title plus consistent secondary sources].

**Yahoo** (Sender Hub best practices) [V]: same shape. All senders: "Implement SPF or DKIM at a minimum", "Keep your spam rate below 0.3%", valid forward and reverse DNS, RFC 5321/5322 compliance. Bulk senders: both SPF and DKIM, "a valid DMARC policy with at least p=none", alignment, a working List-Unsubscribe header where "The Post (RFC 8058) method is highly recommended", "Honor unsubscribes within 2 days". Yahoo never published a number for "bulk".

**Microsoft** (Outlook.com, Hotmail.com, Live.com consumer mail) [V via Mailgun, dmarcian, PowerDMARC and others; Microsoft's own page would not render today]: from 2025-05-05, domains sending over 5,000 emails a day must pass SPF, DKIM and DMARC (`p=none` minimum, aligned with SPF or DKIM). Non-compliant mail first went to Junk, then is rejected with `550 5.7.515 Access denied, sending domain [X] does not meet the required authentication level`. Recommended but not enforced: a valid replyable From or Reply-To, a working unsubscribe link, list hygiene and bounce management, honest subject lines.

### 2.2 What applies to a sender under 5,000 a day from a Workspace mailbox

| Requirement | Applies under 5,000/day? | Who satisfies it | Wise anyway? |
|---|---|---|---|
| SPF or DKIM | **Yes, all senders** | The user, in DNS | Do both |
| Valid PTR, TLS | Yes | Google's servers do this for you | Nothing to do |
| RFC 5322 format | **Yes** | Our code | Must be right |
| Spam rate under 0.3% | **Yes, all senders** | The user's targeting and copy | Aim under 0.1% |
| SPF and DKIM both | Bulk only | The user | **Yes.** Workspace signs with a Google-owned domain (`*.gappssmtp.com`) until the admin turns on DKIM for their own domain [K]. Without that step DKIM does not align |
| DMARC record | Bulk only | The user | **Yes.** Cheap, and Microsoft and Yahoo look for it too |
| Alignment | Bulk only | Automatic once DKIM uses the user's domain | Yes |
| One-click unsubscribe (RFC 8058) | Bulk only, marketing mail only | Needs an HTTPS endpoint | Optional, see 2.3 |
| Visible unsubscribe line in the body | Bulk only | Our footer (we already have `unsub_line`) | **Yes**, also a legal requirement in most countries |
| Honour opt-outs within 2 days | Bulk only | We do it instantly on reply | Yes |

Two cautions. First, "bulk sender" is counted per **domain**, not per mailbox, and the status is permanent. A user running 10 mailboxes on one domain adds up. Second, the thresholds are about formal rule enforcement. Gmail's spam filter judges every sender on complaints and engagement at any volume. A cold sender with 50 mails a day and a 1% complaint rate lands in spam without ever touching the 5,000 rule [K].

### 2.3 Can RFC 8058 one-click unsubscribe be done without a web server?

**No.** RFC 8058 [V]: the List-Unsubscribe header "MUST contain one HTTPS URI"; the receiver performs an HTTPS POST with the body `List-Unsubscribe=One-Click`; and "The List-Unsubscribe and List-Unsubscribe-Post headers MUST be covered by the signature" of a valid DKIM signature. A mailto URI may sit next to the HTTPS one but does not count as one-click. Something on the public internet has to answer that POST.

A second, less obvious obstacle for mailbox senders: **we do not control the DKIM signature.** Google signs the message after we submit it, and chooses which headers go in `h=`. Whether Google's signature covers `List-Unsubscribe` and `List-Unsubscribe-Post` on mail submitted over SMTP **[?] could not verify**. Test: send a message with both headers to yourself and read the `h=` tag of the `DKIM-Signature`. If they are not covered, strict RFC 8058 compliance is impossible from a Workspace mailbox no matter what endpoint exists.

**The honest minimum** is what we already do: `List-Unsubscribe: <mailto:user+unsubscribe@domain?subject=unsubscribe>` plus a plain unsubscribe sentence in the body.

Effect on Gmail's unsubscribe button:

- Gmail supports mailto List-Unsubscribe: when it shows the "Unsubscribe" link next to the sender name, clicking it makes Gmail send an email to that address on the user's behalf [K]. So the button can work with mailto only.
- Gmail does not always show it. Display depends on sender reputation and on Gmail classing the mail as bulk or promotional [secondary sources, consistent]. For a low-volume, plain-text, person-to-person style message from a new domain, expect it to be **absent most of the time**. That is fine: for that kind of mail a reply of "no thanks" is the normal opt-out and we already catch it.
- Why it still matters: when there is no easy unsubscribe, the easy button is "Report spam". Every opt-out path we offer lowers the complaint rate.

Risks in our current header: the `+unsubscribe` plus-address only works where the mailbox supports plus addressing. Gmail and Workspace do. Microsoft 365 does by default since 2022 [K]. Many cPanel, Zoho and ISP mailboxes do not, and an unsubscribe mail would bounce. That needs a setup-time self-test (section 6, item 9).

Options if the owner wants true one-click later, none needing a server of ours:

1. **User-deployed endpoint.** Ship a tiny Cloudflare Worker (or Vercel/Netlify function) template the user deploys on their own account and domain. It accepts `POST /u/<token>`, stores the token in KV, returns 200. The local app polls the Worker's list of tokens each tick and suppresses. Free tier is plenty. Cost: a setup step that needs a Cloudflare account and one DNS record.
2. **Generic webhook inbox** the user already has (for example a Zapier/Make/Pipedream catch hook) with the token in the URL path. Works because the POST body carries no identity; the URL does. Depends on a third party staying up.
3. **Do nothing** under 5,000/day. This is compliant today.

---

## 3. How each metric is measured, and how far to trust it

### 3.1 Delivered

- **ESP definition:** the receiving MX answered `250` to the end of DATA. It means "accepted by the receiving server", not "reached the inbox". Spam folder placement counts as delivered. Some servers accept and then silently drop or quarantine.
- **From a mailbox (our case):** we never talk to the recipient's server. We talk to `smtp.gmail.com`, which answers `250` meaning "Google queued it". Real delivery happens later, from Google's MTA. The only evidence of failure is a bounce message arriving in the mailbox. So for us: **delivered = sent minus bounces received so far**, an assumption that firms up over about 72 hours. Trust: medium.

### 3.2 Bounces

- **Synchronous rejection:** the receiving server answers 5xx during the SMTP conversation. ESPs see this directly and record code and text. It is the cleanest signal there is. We only see synchronous answers from **our own provider's submission server**, which are about our account (auth, quota, policy), almost never about the recipient.
- **Asynchronous bounce (DSN, RFC 3464):** the server accepted the mail, failed later, and sent a `multipart/report; report-type=delivery-status` message to the **envelope sender** (Return-Path). It contains a human part, a `message/delivery-status` part (`Final-Recipient`, `Action: failed|delayed|delivered|relayed|expanded`, `Status: x.y.z`, `Diagnostic-Code`), and usually the original headers. For a mailbox sender **every** recipient-side bounce arrives this way, written by Google's or Microsoft's MTA.
- **VERP (Variable Envelope Return Path):** ESPs give every message a unique Return-Path such as `bounce+<msgid>=<rcpt-hash>@bounces.esp.com`. Any bounce, however malformed, identifies the message and recipient by the address it was sent to, with no parsing. **We cannot use VERP**: Gmail and Microsoft force the envelope sender to the authenticated account. That is why we must parse DSNs and match on Message-ID, and why our matching has to be robust (section 6, item 5).
- **Enhanced status codes (RFC 3463):** `class.subject.detail`. Class 2 success, 4 persistent transient failure, 5 permanent failure. Subject: x.1 addressing, x.2 mailbox, x.3 mail system, x.4 network and routing, x.5 protocol, x.6 content, x.7 security and policy.
- **How ESPs classify.** Not by the first digit alone. They keep rule tables over code plus text, per receiver:
  - Hard (suppress now): 5.1.1 unknown user, 5.1.2 bad domain, 5.1.10 (Microsoft "recipient not found"), 5.1.0/5.1.3 bad address, 5.2.1 disabled.
  - Soft (retry, suppress after repeats): 4.2.2 or 5.2.2 mailbox full, 4.2.1, 4.4.x network, 4.3.x system, 4.7.x deferrals, greylisting.
  - **Block / policy (never suppress the recipient; it is about the sender):** 5.7.1, 5.7.26, 5.7.27, 5.7.30, 5.7.515, anything mentioning spam, blocked, blacklist, reputation, policy, DMARC. SES excludes these from its bounce rate: "bounces due to blocked IP addresses, don't count toward your bounce rate" [V].
  - Postmark exposes the finer buckets by name: HardBounce, SoftBounce, Transient, DnsError, SpamNotification, SpamComplaint, AutoResponder, AddressChange, Blocked, Unknown [V via Postmark docs search].
- **Provider quirks:**
  - **Gmail** uses `550 5.1.1` for unknown users, `452 4.2.2` for over quota and `552 5.2.2` for "out of storage space and inactive", `550 5.2.1` for disabled or rate-limited recipient, `550 5.7.1` for spam and policy, `421 4.7.28` for rate limiting, `550 5.4.5` for the **sender's** daily limit [V, Google SMTP error reference]. Gmail DSNs come from `mailer-daemon@googlemail.com`, include `X-Failed-Recipients`, and attach the original message.
  - **Microsoft** uses `550 5.1.10` and `550 5.1.1` for unknown users, `550 5.4.1` "recipient address rejected: access denied" (often a directory-based edge block, usually a real non-existent address, sometimes a tenant policy), `550 5.7.1` and `5.7.5xx` for policy, `5.2.2` full. Outlook.com uses `S3150`/`S3140` text codes for IP blocks [K].
  - **Yahoo** uses `554 5.7.9` and `553 5.7.1/5.7.2 [TSS..]`/`[BL..]` text codes for policy, `554 delivery error: dd This user doesn't have a yahoo.com account` for unknown users, and defers with `421 4.7.0 [TSS04]` when it dislikes the sender [K]. Yahoo also accepts RCPT for some dead accounts and bounces later.
  - **Catch-all and accept-then-bounce corporate servers** accept everything at SMTP and bounce later or never. A missing bounce is not proof of delivery.
- Trust: hard bounces with a parsed 5.1.x code: **high**. Anything classified from free text: medium. Absence of a bounce: medium-low.

### 3.3 Opens

- **How:** a unique 1x1 image URL in the HTML part. When the image is fetched, an open is logged. Plain text mail cannot be open-tracked at all.
- **Apple Mail Privacy Protection (since September 2021):** for users who opt in (most do), Apple downloads all images through its proxies shortly after delivery, whether or not the person reads the mail. Every such message shows as "opened", with Apple's IP and a generic user agent. This applies to any account read in Apple Mail, including Gmail and Outlook accounts. lemlist puts Apple at about 65% of tracked opens [C]; Instantly cites 49% for January 2025 [C]. The exact share is disputed; "around half" is safe.
- **Gmail image proxy (since 2013):** images load through `googleusercontent.com` proxies. It hides IP and device and caches the image, so repeat opens may not register. Gmail does fetch on real open in most cases, but prefetch near delivery time is reported in some situations [C, Suped].
- **Security scanners** (Proofpoint, Mimecast, Barracuda, Microsoft Defender) fetch images and links at delivery time to inspect them. These are common on exactly the corporate domains that B2B cold email targets.
- **How ESPs filter "machine opens":** by source IP ranges (Apple's proxy ranges), user agent (`Mozilla/5.0` with no detail), and timing (open within seconds of delivery, or all links hit in the same second). SendGrid flags each open event with `sg_machine_open: true` [V via Twilio docs search]. Klaviyo tags Apple Privacy Opens and lets you exclude them from segments and reports [V via Klaviyo help search]. Mailchimp added an option to exclude MPP opens [C, EmailToolTester]. The filtering is heuristic and misses scanners that imitate browsers.
- **What open rate means in 2025-2026:** an upper bound mixed with noise. Useful only as a relative signal between two sends to the same audience, and as an alarm when it collapses (mass spam-foldering stops even machine opens at some providers). Hunter's 2026 State of Cold Email quotes an expert calling open data "fiction" and reports that Belkins stopped tracking opens on 7.5 million cold emails [C]. Trust: **low**.

### 3.4 Clicks

- **How:** every link is rewritten to `https://track.example.com/c/<token>`, which logs the hit and answers with a 302 redirect to the real URL. The tracking host is either the platform's shared domain or a **custom tracking domain**: a CNAME from the customer's subdomain to the platform (Instantly: `inst.yourdomain.com` -> `prox.itrackly.com` [V]; Smartlead: `emailtracking.yourdomain.com` -> `open.sleadtrack.com` [V]; lemlist: `trail.yourdomain.com` -> `custom.lemlist.com` [V]; SendGrid link branding; Mailgun `email.domain` -> `mailgun.org`).
- **Problems:** security gateways click every link at delivery. Microsoft Safe Links and Proofpoint URL Defense also rewrite links themselves, so the click may come from their cloud. Visible link text that differs from the real target (because of the redirect) is a classic phishing pattern and is penalised by filters. Instantly itself says tracked links look "identical to a phishing redirect" to a secure email gateway [V, Instantly blog, 2026-03].
- **Bot filtering:** user agent and IP lists, timing (click within seconds of delivery, several links in the same second), a hidden "honeypot" link no human can see, HEAD-instead-of-GET requests. Heuristic.
- Trust: **medium-low** for B2B recipients behind gateways, medium for consumers.

### 3.5 Replies

- **How:** match the inbound message's `In-Reply-To` and `References` headers against Message-IDs we sent. Fallback: sender address equals a recipient we mailed. Then separate humans from machines with `Auto-Submitted` (RFC 3834), `X-Autoreply`, `Precedence`, and subject patterns.
- **Misses:** replies from a different address (a colleague, an alias), replies that start a new thread, replies through a ticketing system that strips headers.
- Trust: **high**. It is the only metric that proves a human saw the mail in an inbox. It is also what the industry now leads with for cold email.

### 3.6 Unsubscribes

- **ESP:** clicks on the hosted unsubscribe link, plus RFC 8058 POSTs, plus mailto unsubscribes. Exact, trust high.
- **Us:** mailto List-Unsubscribe mails and replies that match opt-out wording. Trust: high for what we catch. Undercounts people who silently hit "Report spam" instead.

### 3.7 Spam complaints

- **Traditional feedback loops (ARF reports, RFC 5965):** the mailbox provider sends the ESP a copy of each message a user marked as spam. Offered by Yahoo/AOL (the "CFL", keyed on the **DKIM domain**), Microsoft consumer mail (JMRP, keyed on **sending IP**, with SNDS for IP-level data), Comcast, and many regional ISPs, often through Validity's Universal Feedback Loop [K, consistent secondary sources].
- **Gmail has no per-message feedback loop.** Al Iverson (Spam Resource): "Gmail, on the other hand...has no feedback loop. Yes, they have some other thing called a feedback loop, that helps correlate aggregate complaint stats in Google Postmaster Tools." It "does not provide enough information to identify individual complaints" [V]. SES confirms from the other side: "Gmail doesn't provide complaint data to SES" [V].
- **Postmaster Tools spam rate** = messages marked as spam by users divided by messages delivered **to the inbox** of active users, per day, for DKIM-authenticated mail from your domain [K]. Mail that went straight to spam is not in the denominator, so a sender who is already mostly spam-foldered can show a low rate. Data appears only above a minimum daily volume to Gmail that Google does not publish (commonly reported as a few hundred a day) [K]. **A low-volume cold sender will often see an empty chart.**
- **Consequence for ESP complaint rates:** they are computed only over domains that send feedback. SES says so directly: the rate is "the percentage of complaints on mail sent to domains that send complaint feedback to SES" [V]. Gmail, often more than half of a consumer list, is invisible in it.
- **For a mailbox sender:** Microsoft JMRP and SNDS are IP-based and the IPs are Google's, so they are unavailable. Yahoo's CFL is domain-based, so a Workspace domain with its own DKIM **can** enrol and would receive ARF reports by email, which an IMAP reader can parse [K on the mechanism, **[?]** whether Yahoo accepts small Workspace senders in practice].
- Trust: ESP complaint rate: medium, systematically low. Postmaster Tools: authoritative for Gmail but aggregate, delayed and volume-gated. For us today: **no direct signal at all**.

### 3.8 Metrics table

| Metric | How measured | Trust | Usual formula | What leaders show |
|---|---|---|---|---|
| Sent | Message handed to the MTA or submission server | High | count | Sent |
| Delivered | ESP: 250 from recipient MX. Us: sent minus bounces seen | ESP high (accept only, not inbox); us medium | delivered / sent | Delivery rate |
| Hard bounce | 5.1.x style permanent failure, sync or DSN | High | hard bounces / **sent** | Bounce rate on sent (SES, Postmark, Instantly) |
| Soft bounce | 4.x.x, mailbox full, expired retries | Medium | soft bounces / sent | Shown separately or merged |
| Block / policy | 5.7.x and reputation text | Medium (text rules) | blocks / sent | Often a separate "blocked" count; SES excludes from bounce rate |
| Open | Tracking pixel fetch | **Low** (Apple MPP, proxies, scanners) | unique opens / **delivered** | Open rate, increasingly with "excluding Apple MPP" toggle |
| Click | Redirect link hit | Medium-low | unique clicks / delivered (CTR); clicks / opens (CTOR) | CTR; CTOR is now unreliable since opens are |
| Reply | In-Reply-To / References match, minus auto-replies | **High** | unique leads replied / unique leads **delivered** (cold tools often use contacted) | Cold tools lead with reply rate; "positive reply rate" is a manual or AI label |
| Unsubscribe | Link click, RFC 8058 POST, mailto, or reply text | High for what is caught | unsubscribes / delivered | Unsubscribe rate |
| Spam complaint | ARF feedback loops (not Gmail); Postmaster Tools aggregate | Medium, undercounts | ESP: complaints / sent to FBL domains. Google: spam reports / inbox-delivered to active Gmail users | Complaint rate; Google's number is the one that matters |

Denominator rule of thumb: failures (bounces) over **sent**, engagement (opens, clicks, replies, unsubscribes) over **delivered**. For sequences, count **unique leads**, not messages, or a 4-step sequence quarters your reply rate.

---

## 4. Tools that send through the user's own mailbox

Instantly, Smartlead, lemlist, Woodpecker, Mailshake (full SaaS: they hold the mailbox credentials or OAuth token on their servers and send from the cloud) and GMass, Mailmeteor, YAMM (Gmail add-ons using the Gmail API or Apps Script).

### 4.1 Open and click tracking

All of them do it the same way: **their servers** host the pixel and the redirect. The message leaves the user's mailbox, but contains an `<img>` and rewritten links that point at the vendor. This is the one part that a tool with no server cannot copy.

The shared tracking domain is a reputation risk: thousands of cold senders of mixed quality put the same hostname in their mail, and filters score URLs. Hence the custom tracking domain CNAME (hostnames in 3.4). lemlist now **requires** a custom tracking domain before it will send with tracking on [V, lemlist help]. Note that a CNAME only hides the vendor in the visible URL; filters can and do follow the CNAME and see the shared target [K].

### 4.2 Reported deliverability cost, and what they recommend now

- **Instantly** (blog, updated 2026-03) [V that they say it; the numbers are C]: tracking pixels "can hurt your inbox placement"; recommends a custom tracking domain, or turning open tracking off, treating reply rate as the primary metric. Their search snippet also claims a 2 to 10 point inbox placement lift from disabling open tracking; the article provides no original test data, so treat as [C].
- **Smartlead** (deliverability guide) [C]: recommends disabling open tracking for cold outreach and measuring replies.
- **Hunter, State of Cold Email 2026** [V that the report says it]: "Campaigns without open tracking see a +68% higher reply rate (7.4% vs 4.4%)", from 31 million emails sent by Hunter users in 2025. **This is observational, not a controlled test.** Senders who switch tracking off are probably more careful senders in other ways. Do not read it as "tracking costs 40% of replies".
- **Independent view** (Suped, summarising Email Geeks deliverability practitioners) [V]: "a tracking pixel alone is not a reason to expect spam placement. Reputation still does the heavy work." The real risk they name is the **shared tracking domain** and its history.
- **Mechanisms that are real regardless of the numbers** [K]: (1) tracking forces an HTML part, and an HTML mail with one invisible image and rewritten links looks like marketing mail, not like a person writing; (2) a link whose text and target differ is a phishing signal; (3) the tracking hostname carries other senders' reputation; (4) security gateways detonate the links, generating fake clicks and occasionally quarantining.
- **Where the industry has landed in 2025-2026:** open tracking off, or off for the first email; link tracking off or no links at all in email one; plain text; reply rate and bounce rate as the headline numbers; inbox placement tests with seed accounts for anyone who wants more. I could not find a published, controlled A/B test with a stated method that isolates the effect of the pixel alone **[?]**.

Our current stance (no tracking at all, plain `text/plain`) is not a missing feature. It is the configuration the vendors now recommend.

### 4.3 How they detect bounces

- They cannot use VERP either. They read the connected mailbox over IMAP or the Gmail/Graph API and parse bounce messages, the same as we do. Instantly: "you'll receive a bounce report in your inbox detailing why delivery failed" and those reports feed the Bounces tab [V, Instantly help]. GMass tells users to find bounces by searching Gmail for `from:mailer-daemon@googlemail.com` and parses those [V via GMass blog search].
- Synchronous SMTP errors from the submission server are handled as account problems (disconnect, pause), not as bounces.
- **Auto-pause:** Instantly pauses a campaign when the bounce rate exceeds **5%** by default, after at least **200** emails, user-configurable [V]. Smartlead's threshold is user-set, their example is 3%, formula `(total bounce count + latest bounce) / total_lead_count * 100`, per campaign [V].
- **Soft bounces, mailbox full, greylisting:** I found no vendor documentation of a retry table **[?]**. In practice the retrying is done by Google's or Microsoft's MTA, not by the tool: the provider retries 4xx answers on its own for up to a few days, may send a "delayed" DSN (`Action: delayed`, 4.x.x) and finally a "failed" DSN (5.x.x, often 5.4.x "retry timeout exceeded"). Greylisting is therefore invisible to mailbox-based tools. Generic vendor advice is to retry a soft bounce once or twice and drop the address after about three [C].
- **Catch-all domains:** handled before sending, through verification. Instantly, Smartlead, Woodpecker and Mailmeteor (BounceShield) bundle or integrate a verifier [C]. Common policy: send to "valid", skip "invalid", and make "catch-all / risky" a user choice, often capped to a small share of each day's sends.

---

## 5. Email verification before sending

### 5.1 How the services work

In order, cheapest first:

1. **Syntax** (RFC 5322 shape, plus provider rules such as Gmail's 6 to 30 characters).
2. **Domain and MX lookup.** No MX and no A record means undeliverable. Parked-domain MX patterns and null MX (RFC 7505) are flagged.
3. **Lists:** disposable domains, role accounts (info@, sales@, admin@: not invalid, but higher complaint risk and often shared), known complainers and litigators, typo domains (gmial.com), known spam-trap patterns.
4. **SMTP probe.** Connect to the MX from port 25, send `EHLO`, `MAIL FROM:<probe@verifier>`, `RCPT TO:<target>`, read the answer, `QUIT` before DATA. `250` suggests the mailbox exists, `550 5.1.1` says it does not. No mail is sent.
5. **Catch-all test.** Probe a random address at the same domain. If that is accepted too, the domain accepts everything and the real probe proves nothing: result "accept-all / risky".
6. **Proprietary signals.** Historical bounce data across customers, engagement data, breach and activity data (ZeroBounce sells "activity" scoring), provider-specific side channels [C].

### 5.2 Accuracy limits

- **Catch-all domains** cannot be resolved by SMTP. They are a large share of B2B lists (small businesses on Microsoft 365 or Google with catch-all routing, and most gateways).
- **Yahoo/AOL** answer 250 to RCPT for some disabled accounts; **Microsoft 365** tenants behind gateways (Proofpoint, Mimecast) accept at the edge and bounce later [K].
- **Greylisting** answers 450/451 to unknown probers; the verifier must come back later or report "unknown".
- **Anti-harvesting:** servers rate-limit or tarpit repeated RCPT probing and blocklist the probing IPs.
- **Spam traps cannot be detected by probing.** A pristine trap is a working mailbox by design. Vendors can only flag traps they already know from data sharing. Any "spam trap detection" claim covers a small known subset [K; SES docs confirm trap addresses are kept confidential, V].
- Vendor accuracy claims of 98 to 99% refer to the "valid" and "invalid" buckets and exclude "unknown" and "catch-all", which can be 10 to 30% of a scraped B2B list [C].

### 5.3 Why probing from the user's machine is a bad idea

- Most residential and many office ISPs **block outbound port 25**, so it often does not work at all.
- Residential IP ranges are on policy blocklists (Spamhaus PBL). Many MX hosts refuse or lie to them, producing false "invalid" results.
- No PTR record and a dynamic IP make the probe look like a botnet.
- Repeated RCPT probing is address harvesting behaviour. It can get the user's **home or office IP** listed, which then hurts their normal mail and browsing reputation. Probing with the user's real address as MAIL FROM risks that address's reputation too.
- It cannot solve catch-all anyway.

What is safe to do locally: syntax, MX lookup (we already store `mx_status`), null-MX and parked-MX detection, disposable and role lists, typo-domain suggestions, provider detection from the MX (google, outlook, proofpoint, mimecast) which also feeds per-provider throttles.

### 5.4 Pricing per 1,000 (pay as you go, small volumes)

All from secondary comparison pages fetched today, not from vendor price pages: treat as approximate [C].

| Service | About per 1,000 at 10k volume | At high volume |
|---|---|---|
| ZeroBounce | about $8 | about $4 at 250k+ |
| NeverBounce | $8 ($80 per 10k) | $3 to $4 at 100k+ |
| Bouncer | about $8 ($0.008 each) | lower in bulk |
| MillionVerifier | about $3.70 ($37 per 10k) | about $0.55 ($549 per 1M) |
| Reoon | **[?]** could not verify today | |

### 5.5 Should a local tool integrate a bring-your-own-key verifier?

**Yes, as an optional step.** Reasons: bounce rate is the one reputation input we can control before sending; scraped Google Maps addresses are exactly the high-risk kind (old, typo-prone, role-based); a verifier's infrastructure is the right place for SMTP probing; cost is small next to the cost of a burned mailbox ($4 to $8 per 1,000). Bring-your-own-key keeps us serverless and keeps the user as the data controller. Design notes in section 6, item 8. Privacy note: it does send the address list to a third party, so it must be opt-in and say so plainly.

### 5.6 What bounce rate is dangerous

- **Google** publishes no bounce threshold [K]. Bounces feed reputation indirectly.
- **Microsoft** publishes none for recipients either [K].
- **SES:** under 2% "for best results", 5% review, 10% pause [V].
- **Postmark:** under 10% [V]. **Resend:** under 4% [V].
- **Instantly:** auto-pause default 5% after 200 sends [V]. **Smartlead:** user-set, example 3% [V].
- **Cold email vendor consensus:** under 2% hard bounces is healthy, 3 to 5% is a warning, above 5% stop [C].

Our guard (at least 3 bounces in the last 50 first-emails **and** over 4%, which in practice means 3 of 50 = 6%, with a 20-send minimum) is in the same range as the vendors and reacts faster than Instantly's 200-send minimum. Keep it. Section 6 item 1 fixes what gets counted in it.

---

## 6. Recommendations for maps-leads, ranked by value

Grounding: observations from `outreach/mailer.py` as of today. What is already right: Message-ID uses the sender's domain (`make_msgid(domain=...)`); plain `text/plain` body; mailto List-Unsubscribe; threading headers on follow-ups; mailbox is read before each send; suppression is checked at the last moment; reads All Mail and Spam; IMAP cursor handles UIDVALIDITY; bounce guard exists.

### 6.1 SMTP reply code table

Codes seen at **submission time** (from `smtp.gmail.com` / `smtp.office365.com`) are nearly always about **our account**. Codes seen inside a **DSN** are about the recipient or about our reputation at the recipient's provider. Decide on the enhanced code first, the 3-digit code second, the text third.

| Code | Meaning | What our sender should do |
|---|---|---|
| 250 / 2.x.x | Accepted by the submission server | Record as sent. Not proof of delivery |
| 421 4.3.0, 451 4.3.0 | Temporary system problem | Do not advance. Retry same message with backoff 5 min, 15 min, 1 h, 4 h. After 4 tries in a day, stop for the day and tell the user |
| 421 4.7.0 | Temporary block: reputation, TLS, or suspicious traffic | **Account-level slow-down.** Pause all sending 1 h, then resume at half rate for 24 h. Second hit in 24 h: pause until the user looks |
| 421 4.7.28 | "Unusual rate of email" rate limit | Same as above, and halve the daily cap for 3 days |
| 450 4.2.1 | Recipient receiving mail too fast, or mailbox temporarily unavailable, or greylisting | Recipient-level soft failure. Leave to provider if in a DSN. If synchronous, retry that recipient in 1 h, then 6 h, then next day. **Never** mark dead |
| 451 4.7.x, 450/451 greylist text | Greylisting / temporary policy | Same as 450. Normally invisible to us because the provider retries |
| 452 4.2.2 | Mailbox full (temporary) | Soft bounce. Skip this step, try the next step on its normal date. 3 strikes across any campaigns: suppress locally as "mailbox full". **Do not** add to the cross-project dead list |
| 452 4.5.3 | Too many recipients | Bug on our side (we send one recipient per message). Log loudly |
| 454 4.7.0 | Too many login attempts / temp auth problem | Account-level. Back off 30 min. Reuse one SMTP connection for a tick instead of logging in per message |
| 535 5.7.8 / 5.7.80, 534 5.7.9/5.7.14 | Bad credentials, app password revoked, "please log in via web browser" | **STOP.** Pause with a clear "reconnect your mailbox" message. No retries: repeated bad logins lock accounts |
| 550 5.4.5 | **Our** daily sending limit exceeded | **STOP for 24 h** from first occurrence. Not a bounce. Lower the daily cap below what triggered it |
| 550 5.1.1, 5.1.10, 5.1.0, 5.1.3 | Mailbox does not exist / bad address | Hard bounce. Suppress, add to dead list, count in bounce guard |
| 550/553 5.1.2, 5.4.4, 5.1.8 | Domain does not exist / no route / bad sender domain | Hard bounce for the **domain**. Suppress every address at that domain |
| 550 5.2.1 | Mailbox disabled, or receiving too fast | Hard if text says disabled/inactive; otherwise soft. Default soft with 2 strikes |
| 552 5.2.2, 5.2.2 in DSN | Mailbox full (Gmail: "out of storage space and inactive") | Soft-with-strikes as for 452 4.2.2. Count in bounce guard at half weight or not at all |
| 552 5.2.3, 5.3.4 | Message too large | Our problem. Stop the campaign step, tell the user |
| 5.4.x in a DSN after "delayed" notices (5.4.1 timeout, 5.4.7 expired) | Provider gave up after days of retries | Soft failure of the domain's server. Retry once in 7 days, then suppress locally. Exception: Microsoft `550 5.4.1 Recipient address rejected: Access denied` is normally a non-existent address: treat as hard |
| 550 5.7.1, 554 5.7.1, 5.7.9, text with spam / blocked / policy / reputation / blacklist / "unsolicited" | **Policy block. The recipient may be fine; our mail or reputation is the problem** | **Not a bounce.** Do not suppress the address, do not add to dead list, do not count in bounce rate. Count in a separate **block guard**: 2 blocks in the last 50 sends, or 2 from the same provider in a day, pauses all sending with the full server text shown |
| 550 5.7.26, 5.7.27, 5.7.30, 5.7.515, 4.7.27, 4.7.30, 4.7.31 | SPF, DKIM or DMARC failed or missing | **STOP immediately.** Run the DNS health check and show exactly which record fails. Every further send fails the same way |
| 554 5.6.0, 5.6.x | Malformed message | Our bug. Stop, log the raw message |
| 5.3.x, 5.5.x, unknown 5xx | System or protocol error | Treat as soft with 2 strikes, log the raw text, never add to the cross-project dead list on a code we do not understand |

### 6.2 Ranked engineering changes

**1. Classify failures by enhanced status code. Stop treating every 5xx as a dead address.** (Highest value: it is a live correctness bug.)
- Today: `handle_inbound` does `if status.startswith("5"): _hard_bounce(...)`, and `send_one` turns **any** `SMTPRecipientsRefused` into a hard bounce whatever the code. `_hard_bounce` suppresses, writes the **cross-project dead list**, and feeds the bounce guard.
- Failure without the fix: the day our domain's reputation dips, Gmail or Microsoft answers `550 5.7.1` for good addresses. We mark each one dead forever across all projects, the bounce guard reports "bad list" when the real message is "you are being blocked", and the user keeps sending. Mailbox-full and 4xx-at-RCPT addresses are also lost for good. The dead list becomes poisoned and nobody can tell.
- Change: one `classify(code, enhanced, text, provider) -> {hard, soft, block, auth, quota, account, unknown}` function driven by the table above, used by both the synchronous path and the DSN path. Only `hard` touches the dead list. `block`, `auth`, `quota`, `account` pause sending with their own plain-language reason. Store the raw code and diagnostic text on every event. Extend `selftest.py` with one fixture per class (the Gmail 5.7.1 DSN, a Microsoft 5.4.1, a 5.2.2).

**2. Idempotent sends: write the intent before SMTP, reconcile after a crash.**
- Today: `transport.send(msg)` runs first, the `out_messages` row is inserted after. A crash, kill, sleep or power loss between the two means the next tick sends the same email again. A generic exception after DATA was accepted (for example a timeout while reading the final 250) has the same effect.
- Failure: a prospect gets the same cold email twice, two minutes apart. That is the single most spam-like thing the tool can do, and it invites a complaint.
- Change: (a) before SMTP, insert the row with the final Message-ID and `state='sending'` and commit; (b) send; (c) update to `state='sent'`. (d) On start-up, for any row stuck in `sending`, search the provider's **Sent** folder over IMAP for that Message-ID (`HEADER Message-ID`): found means sent, not found after a grace period means safe to retry. Gmail and Microsoft both file SMTP-submitted mail in Sent automatically. (e) Take a claim before sending, `BEGIN IMMEDIATE` plus a `locked_until` column or a file lock, so the 120-second LaunchAgent tick and any manual "send now" from the web app can never send the same enrollment at once. (f) Add a unique index on `(enrollment_id, step_position)`.

**3. Account-level circuit breaker and backoff.**
- Today: any non-recipient exception (`SMTPSenderRefused`, `SMTPDataError`, `SMTPAuthenticationError`, timeouts) stores `last_error` and the next tick, 2 minutes later, tries again, forever.
- Failure: after `550 5.4.5` (daily limit) or `421 4.7.28` (rate limited) we hit Google every 2 minutes all night. After a revoked app password we make 700 failed logins a day, which is how accounts get locked or flagged.
- Change: persist `breaker_state`, `breaker_until`, `consecutive_failures`. Exponential backoff with jitter for transient errors (5 min, 15 min, 1 h, 4 h, stop), fixed 24 h for quota, full stop for auth and for DMARC/SPF/DKIM codes. Show the reason in plain words on the board.

**4. Authentication health check: real, daily, and before the first send.**
- Why: SPF, DKIM with the user's own domain, and DMARC are what Google, Yahoo and Microsoft check on every message. Workspace signs with a Google domain until the admin enables DKIM for their own domain, so a fresh Workspace domain passes DKIM but **fails alignment**, and with no DMARC record nobody notices.
- Failure: mail quietly goes to spam for weeks, reply rate is near zero, and nothing in the tool says why. Or a DNS change by someone else breaks SPF and we find out from `5.7.26` rejections.
- Change, two layers: (a) **Send-to-self probe:** send one message to the user's own address, fetch it over IMAP, parse `Authentication-Results` for `spf=pass`, `dkim=pass header.d=<their domain>`, `dmarc=pass`. This tests the real path and needs no selector guessing. It also reveals the DKIM `h=` list (answers the RFC 8058 question in 2.3). Run at setup and weekly. (b) **Daily DNS check** with `dnspython`: SPF TXT exists, is a single record, includes the provider (`_spf.google.com` / `spf.protection.outlook.com`), stays under 10 lookups; DKIM selector resolves (`google._domainkey` by default for Workspace, `selector1/selector2._domainkey` for Microsoft 365); `_dmarc` exists and parses; MX resolves (needed so replies and bounces come back). Block the first send on a failed probe; warn, do not block, on later DNS drift unless DMARC would fail.
- Also tell the user: free `@gmail.com` and `@outlook.com` mailboxes are the wrong tool for cold outreach (lower limits, no domain reputation of their own, DMARC `p=none`/`quarantine` owned by the provider).

**5. Make message matching survive provider rewrites.**
- Finding: **Outlook's SMTP rewrites the Message-ID** and moves ours to `X-Microsoft-Original-Message-ID` [V via Microsoft Q&A and claws-mail list]. Gmail preserves it [C, consistent reports]. Our reply, bounce and thread matching all key on the Message-ID we generated.
- Failure: for Microsoft mailboxes, replies and bounces fall back to address-only matching, follow-ups thread under an ID the recipient never saw (threading breaks in their client), and item 2's Sent-folder reconciliation cannot find the message.
- Change: after each send, read the message back from Sent (search by our ID in `Message-ID` **or** `X-Microsoft-Original-Message-ID`), and store the **provider's final Message-ID** next to ours. Match inbound mail against both. Use the final ID for `In-Reply-To` and `References`. Keep the address fallback but require the inbound date to be after our send date.

**6. Throttles: per inbox, per recipient domain, per receiving provider, with a slow ramp.**
- Have: daily cap with ramp, random gaps, send windows, per-lead time zone.
- Add: (a) cap per **recipient domain** per day (for example 2 to 3) so one company never sees a burst from us; (b) cap per **receiving provider** inferred from MX (google, outlook, yahoo, proofpoint, mimecast) so a provider-level block costs a small part of the day; (c) on any `block` classification from a provider, freeze that provider for 24 to 72 h while the rest continue; (d) a hard ceiling well under provider limits whatever the user types. Cold email vendors advise roughly 30 to 50 cold emails per mailbox per day [C]; Google's real ceiling of 2,000 is irrelevant at the reputation level.
- Failure without it: a campaign sorted by company sends 15 emails to one Microsoft tenant in an hour, the admin's filter flags the sender, and every later mail to that tenant is junked.

**7. Append-only send log, separate from the working tables.**
- Why: `out_messages` and `out_events` are mutable SQLite rows. For "durable and solid" there should be one record nothing can rewrite: what was sent, to whom, when, which template version, the exact headers, the SMTP answer, and every later event.
- Change: a JSONL file per project (`logs/send-log.jsonl`), opened in append mode, `flush` plus `fsync` per line, each line carrying the SHA-256 of the previous line so tampering or truncation is detectable. Write `intent`, `smtp_result`, `reconciled`, `bounce`, `reply`, `unsubscribe`, `pause` records. Never update or delete. It doubles as the legal record of opt-outs and their timestamps, as the source for rebuilding the database after corruption, and as the diagnostic trail for item 1.
- Failure without it: after a database problem or a bug, nobody can prove who was emailed or that an unsubscribe was honoured, and re-importing leads can re-contact people who opted out. Related: keep the suppression list in its own file, exportable and importable, and honour it across projects the way the dead list already is.

**8. Optional bring-your-own-key verifier, plus better free local checks.**
- Change: a `Verifier` interface with adapters for two or three services (MillionVerifier for cost, ZeroBounce or NeverBounce for quality; Reoon and Bouncer if wanted). Key stored in the macOS Keychain like the mailbox password. Cache results by address with a date; re-verify after 90 days. Map all vendors to four buckets: `valid`, `invalid`, `catch_all`, `unknown`. Policy: send to valid; never send to invalid (and add to the dead list with reason "verifier"); catch-all and unknown are a user choice, default **on but limited to about 20% of a day's new sends**, so one bad batch cannot trip the guard. Show cost before running.
- Free local checks to add now: null MX (RFC 7505), MX points to a parking service, disposable-domain list, common typo domains, role-account flag (informational; on Google Maps data `info@` is often the owner), provider detection from MX (reused by item 6).
- **Do not** implement local SMTP RCPT probing (5.3).
- Failure without it: the first campaign on a fresh scrape bounces at 8%, the guard pauses it correctly, but the reputation damage on a new domain is already done.

**9. Unsubscribe: keep mailto, prove it works, make HTTPS one-click an optional user-hosted add-on.**
- Keep the mailto header and the visible line. It is the honest minimum and is compliant under 5,000 a day (2.3).
- Add a **setup self-test**: send a message to `local+unsubscribe@domain` and confirm it arrives. If the provider has no plus addressing, fall back to the plain address with `?subject=unsubscribe` and match on subject. Today a non-plus mailbox would bounce every unsubscribe request, which converts opt-outs into spam complaints.
- Treat a mail to the unsubscribe address as an unsubscribe even with an empty body, from any sender address, matching the lead by `In-Reply-To` first, sender second.
- Widen opt-out detection in replies across languages the user targets, and treat hostile replies ("stop", "remove me", "reported") as opt-outs. Suppress at the **domain** level when the reply says "remove our company".
- Optional: ship the Cloudflare Worker template for RFC 8058 (2.3, option 1), only after the send-to-self probe shows that the provider's DKIM signature covers the List-Unsubscribe headers. Do not pretend compliance if it does not.

**10. Tracking: default none. If offered at all, user-supplied endpoint, never on email one, never a shared domain.**
- Opens: do not build. It forces HTML, the number is mostly machine noise (3.3), and the vendors who sell it now advise switching it off (4.2).
- Clicks: if the owner wants a signal, the clean serverless answer is **no redirect at all**: put a per-lead UTM or short token on links to the user's **own website** and let the user read their own analytics. No third hostname, link text matches target, nothing for a gateway to distrust.
- If redirect tracking is ever required: the user deploys the same Worker as in item 9 on a subdomain of **their sending domain**, the app polls it, links are only tracked from email two onward, and hits within 2 minutes of send or from known scanner user agents are labelled "probably a scanner".
- Reporting: lead with **replies per unique lead delivered**, then bounce rate, block count, unsubscribe rate. Do not show an open rate.

**11. A complaint and placement signal, since Gmail gives us none per message.**
- Add a Postmaster Tools guide in the app: add the sending domain at postmaster.google.com (one TXT record), check **spam rate** and the **compliance status** dashboard weekly, stay under 0.1%, stop and rethink at 0.3%. Say plainly that v2 no longer shows domain or IP reputation (retired 2025-09-30) and that the charts stay empty at low volume.
- Seed placement test: let the user list 3 to 5 mailboxes they own (Gmail, Outlook, Yahoo, their Workspace). Once a week the app sends the live template to them and reads those inboxes over IMAP to see Inbox versus Spam. This is the only direct placement signal available without a server, and it is what paid inbox-placement tools do.
- Parse ARF reports (`multipart/report; report-type=feedback-report`) in the IMAP reader and treat them as complaint plus suppression, so users who enrol their DKIM domain in Yahoo's Complaint Feedback Loop get real complaint data. Low cost, since the reader already walks `multipart/report`.
- Count as soft complaint signals: replies containing "spam", "reported", "how did you get my email". Pause for review at 2 in 100 sends.

**12. Soft-bounce and "delayed" handling.**
- Today a 4.x.x DSN is logged as `bounce_soft` and the cadence carries on. Correct in spirit: the provider is still retrying.
- Add: if a `delayed` DSN exists for email N and no `failed` DSN has arrived, **hold the follow-up** until the outcome is known or 5 days pass. Otherwise the follow-up can arrive before, or without, the original. Add the strikes counter from the table (mailbox full, 5.4.x timeouts): three strikes across campaigns means local suppression, never the dead list.

**13. MIME and header correctness (mostly already right, lock it in with tests).**
- Keep single-part `text/plain; charset=utf-8`. For person-to-person cold mail this is the best format. If HTML is ever added, it must be `multipart/alternative` with the text part first and a real text version, never HTML alone.
- Google requires RFC 5322 compliance from **all** senders. Assert in `selftest.py`: exactly one each of From, To, Subject, Date, Message-ID; no line over 998 characters and body wrapped near 78; non-ASCII names and subjects RFC 2047 encoded (Python's `EmailMessage` does this); `Date` within a minute of now; From display name free of characters that need quoting; `Reply-To` absent or same domain.
- Do not add vanity `X-Mailer` or custom `X-` headers. They fingerprint the tool across all users, which turns one bad user into a filter rule that hits everyone. Same reason to keep the default footer and unsubscribe sentence **user-editable and varied**, not one fixed string across every install.
- Reuse one SMTP connection per tick and close it cleanly (avoids `454 4.7.0 too many login attempts` as volume grows).
- For Workspace and Microsoft 365, plan a move from app passwords to **OAuth2 (XOAUTH2)** for SMTP and IMAP. Microsoft has been disabling basic auth for SMTP submission across 2025-2026 [K, exact dates **[?]**], and Google already requires 2-step verification for app passwords. Failure without it: the tool stops working for Microsoft users on a date we do not control.

**14. Guidance the app should give, because the platforms' rules are really about behaviour.**
- Send from a **separate domain or subdomain** used only for outreach, so a mistake cannot hurt the user's main business mail. Age it and ramp it (we have the ramp).
- Volume advice in plain words: reputation, not the 2,000 limit, is the ceiling. Small, relevant, well-verified batches beat volume.
- Every platform in section 1 bans scraped and purchased lists. Sending from the user's own mailbox is legal in many places for relevant B2B contact, but the law differs by country: CAN-SPAM (US) needs a postal address and an opt-out honoured within 10 business days; Australia's Spam Act needs consent (which can be inferred from a conspicuously published business address when the message relates to that role), sender identification and a working unsubscribe honoured within 5 working days; GDPR/PECR and CASL are stricter [K, not legal advice, **[?]** not re-verified today]. The app should require a postal address in the footer setting and never let the unsubscribe line be removed.

### 6.3 What not to build

- Local SMTP RCPT probing (5.3).
- A shared tracking domain or any server of ours. It would make us the shared reputation that every vendor is trying to escape, and make us a processor of every user's recipient data.
- Warmup pools (automated mailboxes that email each other and mark each other "not spam"). Google has acted against them and they violate mailbox provider terms [K]. A slow honest ramp is enough.
- An open rate.

---

## Sources

Primary, fetched 2026-09-19:

- Google, Email sender guidelines: https://support.google.com/a/answer/81126
- Google, Email sender guidelines FAQ: https://support.google.com/a/answer/14229414
- Google, Gmail sending limits in Google Workspace: https://knowledge.workspace.google.com/admin/gmail/gmail-sending-limits-in-google-workspace
- Google, Gmail SMTP errors and codes: https://knowledge.workspace.google.com/admin/support/troubleshooting/gmail-smtp-errors-and-codes
- Google, deprecation of the old Postmaster Tools interface: https://support.google.com/a/answer/16594218
- Yahoo Sender Hub, best practices: https://senders.yahooinc.com/best-practices/
- Microsoft, Outlook's new requirements for high-volume senders (page would not render; facts taken from the secondary sources below): https://techcommunity.microsoft.com/blog/microsoftdefenderforoffice365blog/strengthening-email-ecosystem-outlook%E2%80%99s-new-requirements-for-high%E2%80%90volume-senders/4399730
- RFC 8058, one-click unsubscribe: https://www.rfc-editor.org/rfc/rfc8058.txt
- RFC 3463, enhanced status codes: https://www.rfc-editor.org/rfc/rfc3463.txt (not re-fetched today)
- RFC 3464, delivery status notifications: https://www.rfc-editor.org/rfc/rfc3464.txt (not re-fetched today)
- Amazon SES, sending review process FAQ: https://docs.aws.amazon.com/ses/latest/dg/faqs-enforcement.html
- Amazon SES, account-level suppression list: https://docs.aws.amazon.com/ses/latest/dg/sending-email-suppression-list.html
- Amazon SES, Easy DKIM: https://docs.aws.amazon.com/ses/latest/dg/send-email-authentication-dkim-easy.html
- Mailchimp, Acceptable Use Policy (updated 2025-09-26): https://mailchimp.com/legal/acceptable_use/
- Mailchimp, set up email domain authentication: https://mailchimp.com/help/set-up-email-domain-authentication/
- Twilio, Email Policy (updated 2026-04-09): https://www.twilio.com/en-us/legal/service-country-specific-terms/email
- Twilio SendGrid, domain authentication: https://www.twilio.com/docs/sendgrid/ui/account-and-settings/how-to-set-up-domain-authentication
- Twilio SendGrid, Apple MPP and open events: https://www.twilio.com/docs/sendgrid/for-developers/tracking-events/understanding-apple-mail-privacy-protection-and-open-events
- Postmark, Terms of Service: https://postmarkapp.com/terms-of-service
- Postmark, getting started (DKIM and Return-Path): https://postmarkapp.com/support/article/1002-getting-started-with-postmark
- Postmark, bounce webhook and bounce types: https://postmarkapp.com/developer/webhooks/bounce-webhook
- Postmark, reactivating inactive addresses: https://postmarkapp.com/support/article/903-an-address-has-been-marked-as-inactive-how-can-i-reactivate-it
- Loops, Terms of Service (updated 2025-12-15): https://loops.so/terms
- Loops, sending domain: https://loops.so/docs/sending-domain
- Resend, Acceptable Use Policy (updated 2026-08-27): https://resend.com/legal/acceptable-use
- Resend, domains: https://resend.com/docs/dashboard/domains/introduction
- Klaviyo, branded sending domain: https://help.klaviyo.com/hc/en-us/articles/115000357752
- Klaviyo, dedicated vs shared IPs: https://help.klaviyo.com/hc/en-us/articles/7675517826587
- Klaviyo, dedicated IP warming: https://help.klaviyo.com/hc/en-us/articles/7521152741403
- Klaviyo, identifying Apple MPP opens: https://help.klaviyo.com/hc/en-us/articles/4416791883163
- Instantly, high bounce auto-pause: https://help.instantly.ai/en/articles/9823139-high-bounce-auto-pause-feature
- Instantly, tracking pixels and deliverability: https://instantly.ai/blog/email-tracking-and-deliverability-why-tracking-pixels-can-hurt-your-inbox-placement/
- Smartlead, bounce autopause and webhook: https://helpcenter.smartlead.ai/en/articles/210-bounce-autopause-and-webhook
- Smartlead, custom tracking domain: https://helpcenter.smartlead.ai/en/articles/50-setting-up-smartlead-custom-tracking-domain-for-better-email-engagement
- Smartlead, deliverability guide: https://www.smartlead.ai/blog/email-deliverability-guide
- lemlist, custom tracking domain: https://help.lemlist.com/en/articles/4452708-custom-tracking-domain
- lemlist, cold email open rates: https://www.lemlist.com/blog/cold-email-open-rates
- Hunter, The State of Cold Email 2026: https://hunter.io/the-state-of-cold-email
- GMass, pulling bounces from Gmail: https://www.gmass.co/blog/a-hack-to-pull-your-bounces-from-your-gmail-account/
- GMass, skewed Gmail open tracking: https://www.gmass.co/blog/why-your-gmail-open-tracking-statistics-may-be-skewed/

Deliverability writers and secondary sources:

- Al Iverson, Spam Resource, "Nope. No Gmail feedback loop, sorry.": https://www.spamresource.com/2023/07/nope-no-gmail-feedback-loop-sorry.html
- Suped, do tracking pixels cause spam placement: https://www.suped.com/learn/email-deliverability/do-tracking-pixels-directly-cause-emails-to-be-marked-as-spam
- Suped, Gmail image proxy and fast opens: https://www.suped.com/learn/email-deliverability/how-does-gmails-image-proxy-affect-email-open-tracking-and-what-could-cause-very-fast-opens
- EmailToolTester, how ESPs handle Apple MPP: https://www.emailtooltester.com/en/blog/apple-mpp-open-rate/
- Mailgun, Microsoft sender requirements 2025: https://www.mailgun.com/blog/deliverability/microsoft-sender-requirements/
- dmarcian, Microsoft enforces SPF, DKIM, DMARC: https://dmarcian.com/microsoft-enforces-spf-dkim-dmarc/
- PowerDMARC, Microsoft sender requirements: https://powerdmarc.com/dmarc-outlook-email-authentication/
- MessageGears, Google sunsets Postmaster Tools v1: https://messagegears.com/resources/blog/google-sunsets-v1-postmaster-tools/
- Office365 IT Pros, mailbox External Recipient Rate limit cancelled (2026-01-08): https://office365itpros.com/2026/01/08/mailbox-external-recipient-rate/
- Microsoft, Exchange Online tenant outbound email limits: https://techcommunity.microsoft.com/blog/exchange/introducing-exchange-online-tenant-outbound-email-limits/4372797
- Microsoft Q&A, Outlook SMTP rewrites Message-ID: https://learn.microsoft.com/en-gb/answers/questions/1337178/custom-message-id-modified-by-the-outlook-smtp-ser
- claws-mail list, MS Outlook SMTP rewrites Message-ID: https://lists.claws-mail.org/pipermail/users/2024-April/032884.html
- Barracuda, unwanted link clicks: https://campus.barracuda.com/product/sentinel/doc/498468311/unwanted-link-clicks/
- Mautic issue on gateway link scanning: https://github.com/mautic/mautic/issues/16263
- Litmus, guide to List-Unsubscribe: https://www.litmus.com/blog/the-ultimate-guide-to-list-unsubscribe
- Batch, why Gmail does not always show the unsubscribe button: https://doc.batch.com/guides-and-best-practices/email-deliverability/list-hygiene-and-recipients-management/why-doesnt-gmail-always-show-the-unsubscribe-button-in-your-marketing-emails
- DEV Community, no clean way to verify an email address: https://dev.to/apa512/theres-no-clean-way-to-verify-an-email-address-heres-what-works-anyway-36bn
- RFC 6647, greylisting: https://datatracker.ietf.org/doc/html/rfc6647
- Verifier pricing comparisons (secondary, approximate): https://instantly.ai/blog/2026-email-verification-benchmark-accuracy-scores-for-8-top-tools/ , https://puzzleinbox.com/blog/millionverifier-pricing-guide/ , https://puzzleinbox.com/blog/neverbounce-pricing-guide/ , https://myemailverifier.com/blog/email-verification-api-pricing/

Not reached or not verified today: Word to the Wise, Validity and Spamhaus articles (no specific page fetched; nothing in this report rests on them alone); Klaviyo and Mailgun acceptable-use policies; Reoon pricing; vendor price pages for verifiers; whether Google's DKIM signature covers List-Unsubscribe headers on SMTP-submitted mail; Microsoft's exact 2026 dates for ending basic auth on SMTP submission; a controlled A/B test isolating the deliverability cost of an open pixel.
