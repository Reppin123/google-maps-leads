# Connecting inboxes: how the leaders do it, and what maps-leads should do

Research date: 2026-09-19. Scope: a local-first desktop web app (Python, macOS first, Windows later, no server of ours, no accounts) that sends cold email from the user's own mailbox and reads that mailbox for replies and bounces.

How to read this report:

- **[Verified]** means I opened a primary source (Google, Microsoft, or the vendor's own help center) on 2026-09-19 and the fact is on that page.
- **[Claimed]** means it comes from a vendor blog, a third-party article, or community reports. Treat as likely but unproven.
- **[Could not verify]** means I looked and could not confirm it from a source I could open.
- **[Needs a test]** means the answer is cheap to get by running a small experiment on a real mailbox, and I recommend doing so before building on it.

---

## Summary in one page

1. **Google app passwords still work in 2026** for SMTP and IMAP, on both personal Gmail and Google Workspace. Google turned off plain password access ("less secure apps") for Workspace in stages ending in spring 2025 and explicitly carved out app passwords as the exception. Google calls them "not recommended" but has announced no end date. An article headline saying "Gmail is phasing out app passwords in 2026" does not hold up: the article itself cites no Google source for that.
2. **Microsoft is the opposite.** Password login to IMAP has been dead in Exchange Online since late 2022 and cannot be re-enabled. Password login to SMTP still works today, but Microsoft will switch it off by default at the end of December 2026 (admins can turn it back on), new tenants after that do not get it, and a final removal date will be announced in the second half of 2027. For Microsoft mailboxes, OAuth is the only way to READ mail. There is no app-password shortcut.
3. **Google OAuth is the hard one for us.** Reading mail needs a "restricted" scope. A public app with restricted scopes needs Google verification (about 6 weeks by Google's own estimate, longer in practice), and if any mail data touches a server, a paid yearly security assessment (CASA). Unverified apps are capped at 100 users. Apps left in "Testing" lose their tokens every 7 days. Every leading SaaS tool has passed this verification. We cannot soon.
4. **There is a legitimate bring-your-own-client path on Google**, and one vendor (Smartlead, "Private Infrastructure") sells it as a feature. A Workspace customer creates their own Google Cloud project, marks the consent screen "Internal", and gets no verification, no user cap, and no 7-day expiry. It is about 15 to 25 clicks in the Cloud Console. It is fine as an "advanced" option. It is too painful to be the default.
5. **Microsoft OAuth is achievable for a no-server product.** A multi-tenant "public client" app registration is free, has no security assessment, and publisher verification is free. The catch since late 2025: many tenants now require an admin to approve third-party apps that access mail. Solo operators are their own admin, so this is one extra click for them.
6. **Multiple inboxes:** every leader assigns a lead to one inbox at the first send and keeps the whole sequence there. When an inbox breaks, the good ones hold that inbox's leads rather than switching sender mid-thread. Typical 2025-2026 advice is 20 to 50 cold emails per inbox per day, 2 to 3 inboxes per domain, and separate lookalike domains so the main brand domain is never at risk.
7. **Warmup** (robot mailboxes mailing each other and dragging messages out of spam) is against Google's API policy. Google forced GMass to shut its warmup network in early 2023 under threat of losing Gmail API access. Survivors moved warmup to IMAP/SMTP. A local-first tool with no server cannot run a peer network anyway. We should not offer it. We should offer a slow volume ramp, which we already have.

**Recommended path:** keep SMTP + IMAP with an app password as the main Google route and make the wizard excellent; add generic SMTP/IMAP with provider presets; move secrets behind a cross-platform keychain layer; add per-inbox state and rotation. Next, add Microsoft through our own Entra app (OAuth, Graph or XOAUTH2) and offer Google bring-your-own-client as an advanced route. Later, apply for Google verification as a local-only app, which may avoid the paid assessment.

---

## 1. How the leading tools connect a single inbox

### 1.1 What each vendor offers

| Tool | Google | Microsoft 365 / Outlook | Other providers | Source quality |
|---|---|---|---|---|
| Instantly | Two options shown side by side: "Option 1: OAuth" and "Option 2: App Password" | Admin enables IMAP and Authenticated SMTP on the mailbox, waits about an hour, then signs in | SMTP/IMAP, single or bulk CSV | [Verified] vendor help |
| Smartlead | One-click OAuth (recommended), or SMTP/IMAP with app password. Also "Private Infrastructure": the customer's own Google Cloud or Azure OAuth app | OAuth, or SMTP/IMAP | SMTP/IMAP, bulk CSV | [Verified] titles and summaries; full private-infrastructure steps [Could not verify], page body did not load |
| lemlist | OAuth + Gmail API only. Their help says Google-hosted addresses must use the API, not SMTP | OAuth sign-in. Business tenants need the admin to allow third-party apps | Custom SMTP/IMAP | [Claimed] from search summaries of lemlist help |
| Apollo | OAuth (Google) | OAuth (Microsoft) | Other providers through Nylas, which supports SMTP/IMAP | [Claimed]; Apollo help page returned 403 |
| Woodpecker | OAuth | "Native, one-click" OAuth. Their help also tells users to turn off 2-step verification during connection, which is dated advice | SMTP/IMAP | [Verified] vendor help |
| Mailshake | Google OAuth | Microsoft OAuth, "highly recommended" | SMTP + IMAP both required. IMAP is how it stops sequences on reply | [Verified] vendor help |
| Saleshandy | OAuth ("verified Google partner"), or SMTP/IMAP with app password | OAuth, or SMTP/IMAP | SMTP/IMAP, single or bulk CSV | [Verified] vendor help |
| Reply.io | OAuth | OAuth | SMTP/IMAP | [Could not verify] in detail; only marketing pages surfaced |

Pattern: OAuth is the front door everywhere. App password or raw SMTP/IMAP is kept as the second door because OAuth gets blocked by Workspace admins and because resellers hand out inboxes as SMTP/IMAP credentials in a CSV.

### 1.2 Google Workspace: the exact user steps

**Route A, OAuth (Instantly's flow, [Verified]):**

1. In the tool, choose Google, then "Option 1: OAuth". Copy the tool's OAuth Client ID.
2. In admin.google.com go to Security, then Access and data control, then API controls, then "Manage app access".
3. "Configure new app", paste the Client ID in the search box (searching by name does not work), pick the app.
4. Scope it to all users or to an organisational unit. Set access to "Trusted". Finish.
5. Back in the tool, click Login, choose the Google account, Continue, Allow.

Why the admin step exists [Verified, Google Workspace admin help]: admins can mark each third-party app Trusted, Limited, Specific Google data, or Blocked, and can mark Google services (Gmail among them) as restricted so only Trusted apps reach them. The default is that users may sign in to any third-party app, so on a fresh tenant steps 2 to 4 are often unnecessary, but every vendor documents them because skipping them is the most common failure.

Common failures: "This app is blocked" (the app is not Trusted for that user's organisational unit); the wrong Google account picked because another session is open (vendors tell users to use an incognito window); the user is not actually in the Workspace.

**Route B, app password (Instantly and Saleshandy, [Verified]):**

1. Turn on 2-Step Verification on the Google account. This is required before app passwords appear [Verified, Google Account help].
2. Open myaccount.google.com/apppasswords, name it, Generate, copy the 16 characters. It is shown once.
3. In the tool choose Google, then App Password. Enter the email address and the 16 characters. Host and port are pre-filled (smtp.gmail.com, imap.gmail.com).

Admin side:

- IMAP must be allowed for the user's organisational unit: Admin console, Apps, Google Workspace, Gmail, End user access, "Enable IMAP access for all users" [Claimed by vendor and third-party guides, consistent with Google's admin help title "Turn POP and IMAP on or off for users"]. For personal Gmail the IMAP toggle was removed in January 2025 and IMAP is always on [Verified via Instantly help; Google help text surfaced in search].
- The admin must allow users to turn on 2-Step Verification.
- App passwords are NOT available if 2-Step Verification is set to security keys only, or if the account is in Advanced Protection [Verified, Google Account help]. Some third-party guides describe an admin toggle for app passwords; I [could not verify] that a separate toggle exists.
- All app passwords are revoked when the Google account password changes [Verified, Google Account help]. This is the most common cause of a connection that "just stopped working".

Common failures: "Application-specific password required" (the user typed their normal password); "Username and Password not accepted" (typo, spaces pasted, or revoked after a password change); the App passwords page says "The setting you are looking for is not available for your account" (2-Step Verification off, security-key-only, Advanced Protection, or admin policy).

### 1.3 Microsoft 365 / Outlook: the exact user steps

**Route A, OAuth (every vendor):** click Connect, sign in with Microsoft, accept the consent screen. If the tenant requires it, an admin must approve the app first (see 2.6).

**Route B, SMTP/IMAP with password:** this route is effectively dead for reading. Basic authentication for IMAP, POP, EWS and others was disabled in all Exchange Online tenants from October 1, 2022, and "no one (you or Microsoft support) can re-enable" it [Verified, Microsoft Learn, page updated 2026-07-16]. Microsoft also notes that this removal "prevents the use of app passwords" with such apps. Personal Outlook.com, Hotmail and Live accounts lost basic auth on September 16, 2024 [Claimed, multiple Microsoft Q&A threads and third-party posts].

Admin settings that matter even with OAuth:

- **SMTP AUTH is off by default.** Microsoft disabled it in all tenants where it was not in use, and recommends leaving it off org-wide and enabling it per mailbox: Microsoft 365 admin center, Users, Active users, pick the user, Mail, Manage email apps, tick "Authenticated SMTP" (and IMAP), save. PowerShell: `Set-CASMailbox -Identity user@domain -SmtpClientAuthenticationDisabled $false` [Verified, Microsoft Learn]. Instantly tells users to wait an hour after changing it [Verified].
- **Security defaults** in Entra block SMTP AUTH even when the mailbox switch is on: "If security defaults is enabled in your organization, SMTP AUTH is already disabled" [Verified, Microsoft Learn].
- The SMTP AUTH protocol switch governs the protocol, not just password login. SMTP with OAuth (XOAUTH2) uses the same SMTP AUTH submission endpoint, so it still needs the mailbox switch on. Sending through Microsoft Graph does not use SMTP AUTH at all. [The first half is my reading of the Microsoft Learn page; Needs a test.]
- The per-mailbox "IMAP" email-app switch must be on for IMAP with OAuth.

Common failures: `535 5.7.139 Authentication unsuccessful, SmtpClientAuthentication is disabled for the Tenant` or "for the Mailbox"; `535 5.7.3 Authentication unsuccessful` [Verified in Microsoft's XOAUTH2 example]; "Need admin approval" consent screen; the change not having propagated yet.

### 1.4 Generic SMTP/IMAP

Host, port, username, password for SMTP and again for IMAP, with a "test connection" button. Providers such as Zoho, Fastmail, Yahoo, iCloud and most cPanel hosts need an app-specific password when two-factor is on. Mailshake states the important product truth plainly: IMAP is required because it is how the tool knows a reply came in and stops the sequence [Verified].

### 1.5 Current state of the platform policies (2025-2026)

| Policy | State on 2026-09-19 | Status |
|---|---|---|
| Google "less secure apps" (plain password over IMAP/SMTP/POP/CalDAV) for Workspace | Admin setting removed and new connections blocked in summer 2024. Access shut off for all Workspace accounts on March 14, 2025 per the Workspace admin page. A second Google help page surfaced in search says "starting May 1, 2025". Either way it is finished. Personal Gmail lost it in May 2022. | [Verified] March 14, 2025 date; May 1, 2025 [Claimed] |
| Google app passwords | Still supported. Google's transition page says password access ends "with the exception of app passwords". Need 2-Step Verification. Not recommended by Google. Revoked on password change. No announced end date. | [Verified] |
| Google OAuth for IMAP/SMTP (XOAUTH2) | Supported. Needs the `https://mail.google.com/` scope, which is restricted. | [Verified] scope class |
| Microsoft basic auth for IMAP/POP/EWS | Gone since October 2022, cannot be re-enabled | [Verified] |
| Microsoft basic auth for SMTP AUTH | Unchanged until end of December 2026. Then disabled by default for existing tenants, admins can re-enable. New tenants after December 2026 do not get it. Final removal date to be announced in the second half of 2027. This was announced on January 27, 2026 and replaced an earlier plan (start rejecting on March 1, 2026, reach 100% by April 30, 2026). | [Verified] via Microsoft Learn linking to the Exchange team post, and office365itpros.com summary. The Microsoft blog body itself did not load for me. |
| Microsoft OAuth for IMAP/POP/SMTP (XOAUTH2) | Supported since 2020 for Microsoft 365 and Outlook.com. Scopes `https://outlook.office.com/IMAP.AccessAsUser.All`, `https://outlook.office.com/SMTP.Send`, plus `offline_access`. Authorization code flow and device code flow are both supported. | [Verified] |
| Microsoft per-mailbox external recipient limit (2,000 per day) | Cancelled on January 6, 2026. Classic limits stay: 10,000 recipients per day, 30 messages per minute per mailbox, plus a tenant-wide external recipient limit that depends on licence count (trial tenants capped at 5,000 per day) and a 100 external recipients per day cap for `onmicrosoft.com` sender domains. | [Verified] limits page updated 2026-09-09; cancellation [Claimed] by several news sites and a Microsoft blog title |
| Gmail bulk sender rules | Since February 2024: SPF, DKIM and DMARC, one-click unsubscribe for marketing mail, spam rate under 0.3% (aim for under 0.1%). Since November 2025 Gmail rejects non-compliant mail outright rather than sending it to spam. The formal rules bind at 5,000+ messages a day to Gmail, but the authentication and spam-rate parts affect everyone in practice. | [Claimed] from Google FAQ title plus several deliverability vendors |

---

## 2. OAuth for a product like ours

### 2.1 Google scopes

| Scope | What it allows | Class |
|---|---|---|
| `gmail.labels` | Manage labels only | Non-sensitive |
| `gmail.send` | Send only | **Sensitive** |
| `gmail.readonly` | Read all mail and settings | **Restricted** |
| `gmail.metadata` | Headers and labels, no bodies | **Restricted** |
| `gmail.compose` | Drafts and send | **Restricted** |
| `gmail.insert` | Insert messages | **Restricted** |
| `gmail.modify` | Read, send, label, archive | **Restricted** |
| `https://mail.google.com/` | Everything, and the only scope that works for IMAP/SMTP XOAUTH2 | **Restricted** |

[Verified, Gmail API scopes page.]

To send and detect replies and bounces we need read access to message bodies (bounce reports carry the failed address in the body). The smallest workable set over the API is `gmail.send` + `gmail.readonly`. Over IMAP/SMTP with OAuth the only option is the full `https://mail.google.com/`. There is no way to read mail without a restricted scope.

### 2.2 What Google verification requires

[Verified unless marked, from Google's verification docs and FAQ.]

- Brand verification: a homepage on a domain you have verified in Search Console, which describes the app, and a privacy policy on the same domain that explains how Google user data is handled. 2 to 3 business days.
- Sensitive scope verification: justification for each scope and a demo video that shows the consent screen and the feature using the scope. About 10 business days.
- Restricted scope verification: all of the above, plus the app must be a **permitted application type**. About 6 weeks by Google's estimate. Third-party write-ups put a first-time run at 6 to 12 weeks [Claimed].
- Permitted types for Gmail include "applications that enhance the email experience for productivity purposes (such as ... delayed sending of email or mail merge ...)". The same policy prohibits mass mailing apps that distribute "spam or unsolicited commercial mail". Cold outreach tools sit between those two sentences. Instantly, Smartlead, lemlist and Saleshandy have all been verified, so it is clearly possible, but this is a real review risk for a product whose front page says "cold email".
- **Security assessment (CASA):** mandatory if the app "accesses or has the capability to access Google user data from or through a server". It is done by an independent authorised lab, renewed every 12 months. Google charges nothing; the lab does. Reported prices range from about 540 USD for a scan-based Tier 2 to several thousand USD, and much more for a full penetration test [Claimed, third-party blogs].
- **Local-only exemption:** a search result quoting Google community guidance says "Local client applications don't need to undergo a security assessment because data is run, stored, and processed only on the user's device." That is consistent with the primary wording above (the trigger is access "from or through a server"), but I [could not verify] the exemption sentence on a primary page I could open. If true, a genuinely local app still needs restricted scope verification (homepage, privacy policy, video, permitted type) but not the paid yearly assessment. This is the most important thing to confirm with Google before choosing the long-term route.

### 2.3 Caps on unverified and testing apps

[Verified.]

- Unverified apps that request sensitive or restricted scopes have a **100 new-user cap** for the lifetime of the project. Users see the "Google hasn't verified this app" warning and must click Advanced, then continue.
- Apps with publishing status **Testing** and user type External: up to 100 listed test users, and "authorizations by a test user will expire seven days from the time of consent", refresh tokens included.
- Moving the app to "In production" without completing verification removes the 7-day expiry but keeps the warning screen and the 100-user cap [Claimed, widely used by rclone and similar projects; consistent with Google's pages].
- Other reasons a Google refresh token dies: the user revoked access; **the user changed their password and the token has Gmail scopes**; unused for 6 months; more than 100 live refresh tokens per account per client; an admin restricted the service; session-control policies.

### 2.4 The "Internal" exemption

[Verified.] If the Google Cloud project belongs to a Google Workspace or Cloud Identity organisation and the consent screen user type is **Internal**, the app needs no verification, shows no unverified warning, has no 100-user cap and no 7-day expiry. Only accounts in that organisation can authorise it (others get an `org_internal` error). The Workspace admin may still need to tick "Trust internal apps" in API controls for restricted Gmail scopes.

This does not help us as the vendor: an Internal app works only for users in OUR organisation. It helps only when the customer owns the project.

### 2.5 Bring-your-own-client (each customer creates their own Google OAuth client)

Is it legitimate? Yes. Google's own exemption list covers "internal use" apps and "personal use" apps with a few users known to the owner. Smartlead sells this as "Private Infrastructure (OAuth)" for both Google Cloud and Azure [Verified that the feature exists; details Claimed]. An open-source gateway (BreazyLabs/OutreachEmailMCP) uses the same model: the operator registers their own OAuth apps and mailboxes consent against them [Verified, project README]. rclone and many self-hosted tools have worked this way for years.

What the customer has to do (Google Workspace owner):

1. Go to console.cloud.google.com signed in as a Workspace user who can create projects. Create a project.
2. APIs and Services, Library, enable "Gmail API" (not needed if using IMAP/SMTP XOAUTH2 only, but harmless).
3. Google Auth Platform (OAuth consent screen): app name, support email, **User type: Internal**.
4. Data access: add the scopes (`gmail.send` and `gmail.readonly`, or `https://mail.google.com/`).
5. Clients, Create client, **Application type: Desktop app**. Copy the client ID and client secret into maps-leads.
6. If the tenant restricts Gmail API access: Admin console, Security, API controls, tick "Trust internal apps".
7. In maps-leads click "Sign in with Google" for each mailbox.

How painful: 15 to 25 clicks across two Google consoles, with jargon on every screen. Google redesigns these screens often, so screenshots rot. Fine for an agency with a technical person, and it is a one-time job per Workspace (one client serves every mailbox in that organisation). For a solo operator it is far worse than an app password (3 steps). Personal @gmail.com users cannot choose Internal; they would have to use External in production, accept the warning screen, and would count against a 100-user cap that they will never reach since it is their own project.

One client per Workspace organisation is the catch for agencies: an agency with 10 client domains in 10 separate Workspaces needs 10 projects (Internal), or one External unverified project with the warning screen.

### 2.6 How desktop apps do OAuth

[Verified, Google "OAuth 2.0 for installed apps" and Microsoft identity docs.]

- Open the **system browser** (never an embedded web view) to the authorisation URL.
- Redirect to a **loopback address**: `http://127.0.0.1:<port>` with a listener in the app. maps-leads already runs a local web server, so it can receive the redirect on its own port. Google's Desktop client type accepts any loopback port. Custom URI schemes and the old copy-paste "out of band" flow are no longer supported by Google.
- Use **PKCE** (code verifier and challenge) and a random `state`.
- A desktop app cannot keep a secret. Google still issues a `client_secret` for Desktop clients and expects it in the token request, but it is not treated as confidential; shipping it inside the app is normal. Microsoft public clients have no secret at all.
- Store the refresh token in the OS keychain. Refresh access tokens about every hour.

### 2.7 Microsoft (Entra ID)

**Registration** [Verified]: register an app in any Entra tenant with a work account, choose "Accounts in any organizational directory and personal Microsoft accounts" (multi-tenant), add a "Mobile and desktop applications" redirect URI of `http://localhost`, and allow public client flows. No client secret. Free.

**Permissions** (delegated):

| Option | Scopes | Notes |
|---|---|---|
| IMAP + SMTP with XOAUTH2 | `https://outlook.office.com/IMAP.AccessAsUser.All`, `https://outlook.office.com/SMTP.Send`, `offline_access` | Reuses our existing IMAP/SMTP code. Works for Microsoft 365 and Outlook.com. Still needs the per-mailbox Authenticated SMTP and IMAP switches on, and Security defaults can interfere with SMTP AUTH. |
| Microsoft Graph | `Mail.Send`, `Mail.Read` (or `Mail.ReadWrite`), `offline_access`, `User.Read` | No dependency on the SMTP AUTH or IMAP switches. Delta queries give cheap polling. Different code path from Google. |

**Publisher verification** [Verified, page updated 2026-06-15]: free. Needs a Microsoft AI Cloud Partner Program account that has passed Microsoft's business verification, an app registered with a work account (not a personal Microsoft account), and a publisher domain that matches (not `onmicrosoft.com`). "Developers who have already met these requirements can be verified in minutes." Without it, since November 2020, users in other tenants generally cannot consent to a multi-tenant app that asks for more than sign-in; they see an "unverified" warning or a block. There is **no equivalent of CASA** and no user cap.

**Admin consent** [Verified via Message Center archive MC1163922 and third-party coverage]: tenants that use the Microsoft-managed default consent policy stopped letting ordinary users consent to third-party apps for files and sites in mid-July to August 2025, and from late October to late November 2025 the same was applied to "third-party apps accessing Exchange and Teams content via Microsoft Graph, EWS, EAS, POP3, and IMAP4". A short allow-list of well-known mail clients is exempt (Apple Mail, Thunderbird, eM Client, Spark, Samsung and Android mail were named in one write-up [Claimed]). Users who consented earlier are not interrupted. For us this means: expect a "Need admin approval" screen for most new Microsoft 365 connections, and give the user an admin consent link (`https://login.microsoftonline.com/{tenant}/adminconsent?client_id=...`). A solo operator is usually the global admin of their own tenant and can approve in one click.

**Bring-your-own-client on Microsoft** is also possible and is easier than on Google: a single-tenant app registration in the customer's own tenant needs no publisher verification, and the admin can grant consent in the portal. About 10 clicks.

---

## 3. Gmail API versus SMTP/IMAP

| Topic | SMTP + IMAP | Gmail API |
|---|---|---|
| Auth options | App password, or XOAUTH2 with the full `https://mail.google.com/` scope | OAuth only: `gmail.send` (sensitive) + `gmail.readonly` or `gmail.modify` (restricted) |
| Threading when sending | Gmail threads on `In-Reply-To` and `References` plus a matching Subject. We already set these. | To join a thread, all three must hold: `threadId` is given, `References` and `In-Reply-To` are set per RFC 2822, and the Subject matches [Verified, Gmail API threads guide]. |
| Client-set Message-ID | Community reports say smtp.gmail.com keeps a well-formed Message-ID and only rewrites malformed ones, moving the original to `X-Google-Original-Message-ID` [Claimed]. Our code relies on this today. **[Needs a test]**: send one message and compare the header in Sent Mail with what we generated. | Reports say the API does not honour a custom Message-ID [Claimed, one search summary; I could not find it in Google's docs]. If so, after `messages.send` we would call `messages.get` with metadata format and store the real Message-ID header. **[Needs a test]** |
| Copy in Sent Mail | Automatic for smtp.gmail.com | Automatic |
| Daily send limits (apply to both) | Workspace: 2,000 messages per day (500 on trial), 3,000 external recipients per day, 2,000 unique external recipients per day (500 on trial), rolling 24 hours. Going over blocks sending for up to 24 hours; receiving still works [Verified, Workspace sending limits page]. Personal Gmail is commonly cited as 500 per day [Claimed]. | Same account limits. |
| API quotas | Not applicable. IMAP has its own connection and bandwidth limits (Google documents a cap of 15 simultaneous IMAP connections per account) [Claimed, from memory of Google help, not re-opened today]. | For Cloud projects created on or after May 1, 2026: 1,200,000 quota units per minute per project and 6,000 per minute per user. Costs: `messages.send` 100, `messages.get` 20, `threads.get` 40, `messages.list` 5, `history.list` 2, `watch` 100. A daily threshold of 80,000,000 units per project is free; Google says exceeding quota limits "is planned to incur charges to your Google Cloud billing account later in 2026" with at least 90 days notice [Verified, quota page updated 2026-09-10]. Irrelevant at our volumes, but it shows that a shared vendor project carries a cost risk that a bring-your-own project does not. |
| Push versus poll | IMAP IDLE gives near-instant push on one folder per connection with no server. Polling by UID every 2 minutes is simpler and is what we do. | `users.watch` needs a Cloud Pub/Sub topic in the OAuth client's project and must be renewed at least every 7 days. A pull subscription avoids a public webhook but still needs Pub/Sub credentials on the desktop, which is not sensible for a shipped app. Without push, poll `history.list` from a saved `historyId`; history is kept "typically at least one week", and a 404 means do a full resync [Verified]. |
| Reading bounces | Bounce reports arrive in the inbox like any mail. Read All Mail and Spam. Our parser already does this. | Same messages. `q=from:mailer-daemon` works. Labels are easy. |
| Drafts, labels | IMAP folders stand in for labels; clumsy but workable | First-class |
| Works for non-Google providers | Yes, the same code | No |

**Which is more reliable and lower-friction for a local app?** SMTP + IMAP. The reasons:

1. It is the only route that needs no verification from Google today (app password).
2. One code path covers Google, Zoho, Fastmail, cPanel hosts, reseller inboxes, and (with XOAUTH2) Microsoft.
3. We keep control of the Message-ID, which is what our reply and bounce matching hangs on.
4. The Gmail API's real advantages (push, labels, batch) need a server or do not matter at 40 emails a day.

The Gmail API becomes worth adding only if and when we hold a verified Google client, because `gmail.send` + `gmail.readonly` is a narrower request than the full-mailbox IMAP scope and therefore an easier review.

---

## 4. Multiple inboxes

### 4.1 How the leaders rotate

| Behaviour | What they do | Source |
|---|---|---|
| Assignment | lemlist: round-robin across the senders chosen for the campaign. Hunter: divides recipients as evenly as possible up front. Woodpecker: weighted by each mailbox's limits, send speed, use in other campaigns and connection state, so bigger-capacity mailboxes get more prospects. | [Verified] vendor help pages |
| Thread continuity | Universal: "Each lead keeps the same sender that was assigned at the beginning of the sequence" (lemlist). Follow-ups go from the same mailbox (Woodpecker, Hunter, Mailmeteor). | [Verified] |
| Inbox disconnected or removed | Woodpecker: that mailbox's prospects are "placed on hold until they are assigned to another mailbox". lemlist: sending stops until the account is reconnected. Hunter: follow-ups may come from another account, which Hunter itself says is "not recommended to avoid seeming spammy". | [Verified] |
| Inbox hits its limit | Wait for the daily reset; other inboxes carry on. lemlist caps at 30 to 40 per mailbox per day through its own product. | [Verified] |
| Signature and sender name | Per mailbox. Woodpecker: "the email signature will always be matched to the mailbox currently sending the message". Tools expose `{{sender name}}` style variables so copy stays correct whichever inbox sends. | [Verified] Woodpecker; variables [Claimed] |
| Sending windows | Usually per campaign, with per-mailbox daily caps and minimum gaps between sends. | [Claimed] |
| Unified inbox | Instantly "Unibox", Smartlead "Master Inbox": replies from every mailbox in one list, answered from the mailbox that owns the thread. | [Claimed] |
| Bulk connect | CSV upload of SMTP/IMAP credentials (Smartlead validates warmup numbers and passwords on upload; Saleshandy and Instantly also offer bulk). Inbox resellers (Zapmail, InboxKit, Mailforge, Mailscale and others) export that CSV or push inboxes straight into the sequencer; InboxKit advertises 24+ sequencer integrations, Zapmail 50+. | [Verified] Smartlead and Saleshandy bulk exists; reseller claims [Claimed] |

### 4.2 Typical numbers in 2025-2026 and why

All [Claimed]; these are community norms, not platform rules.

- **Cold emails per inbox per day: 20 to 50**, counting follow-ups. Most careful senders sit at 30 to 40. Some vendors say up to 100 for a mature inbox. lemlist enforces 30 to 40.
- **New inbox ramp:** start at 5 to 10 a day and climb over 2 to 4 weeks. Our current ramp (10, plus 3 a day, to 40) is inside the norm.
- **Inboxes per domain: 2 to 3** (some say 3 to 5). About 100 to 250 cold emails per domain per day.
- **Domains:** never send cold mail from the main brand domain. Buy lookalike domains, forward them to the main site, and spread inboxes across them. Rule of thumb from one vendor: daily target divided by 33 gives the inbox count; divide that by 2 or 3 for the domain count. So 200 a day is about 6 inboxes on 2 to 3 domains.

The reasoning: the platform limit (2,000 a day on Workspace) is irrelevant. What matters is reputation, which mailbox providers track per sending domain and per sender. Gmail's spam-complaint ceiling is 0.3%. At 40 emails a day a single complaint is 2.5% for that day, so volume per identity has to stay low enough that a few complaints do not define the sender. Small per-inbox volume also looks like a human. Spreading over domains limits the damage when one domain is burned.

### 4.3 What "warmup" is, and whether to offer it

**Technically:** the tool holds credentials for thousands of customer mailboxes. It makes them send each other templated emails, and on the receiving side it logs in, opens the message, marks it important, replies, and if it landed in spam moves it to the inbox. The aim is to manufacture the engagement signals that spam filters reward. Instantly's "health score" is simply the share of warmup emails that landed in the inbox rather than spam, with above 90% called good [Verified, Instantly help summary].

**Is it against Google's terms?** For Gmail API access, yes. Google's notice to GMass cited its policy that apps which "use multiple accounts to abuse Google policies, bypass Gmail account limitation, circumvent filters and spam, or otherwise subvert restrictions are prohibited from accessing Gmail API scopes" [Claimed, quoted by ISIPP and others from Google's notice]. Google told GMass to shut its warmup network (80,000+ accounts) or lose Gmail API access; GMass shut it on January 31, 2023, ahead of a February 13, 2023 deadline [Verified, GMass blog; deadline Claimed]. GMass reported Google's position as not wanting "warmup taking place at all".

**What happened next:** lemlist said it had already moved lemwarm from the API to IMAP in August 2022 [Claimed]. Other tools did the same: warmup runs over IMAP/SMTP (app password or a separate connection) where Google's API policy has no lever. Warmbots stopped serving Google accounts in May 2023 [Claimed]. Warmup is still sold by Instantly, Smartlead, lemlist, Mailreach and others in 2026. I [could not verify] any specific Google action against Instantly. GMass's own warning is worth repeating: "Google isn't dumb. They'll know."

**Should a local-first tool offer it?** No.

1. A warmup network needs a central server that holds or coordinates many mailboxes. We have no server by design.
2. It needs peers. A one-time-purchase desktop tool has no network to offer.
3. It is the single feature most likely to sink a future Google verification.
4. Its benefit is disputed; filters increasingly weigh real recipient behaviour.

What to offer instead: the gradual ramp we already have, per inbox; a "new inbox" preset that starts lower; advice in the UI to use the mailbox for some real mail first; and plain wording that users who want warmup can run a third-party service against the same mailbox in parallel (it will not conflict with us because we only read, never move or delete).

---

## 5. Credential storage and durability for a local app

### 5.1 Where secrets live

| Platform | Store | Notes |
|---|---|---|
| macOS | Keychain (we use the `security` CLI today) | The login keychain unlocks with the user session. Calling the `security` binary means any process running as the user can read the item; acceptable for this threat model. A signed app using the Keychain API directly gets per-app access control. |
| Windows | Credential Manager (DPAPI-protected) | Credential blobs are limited to about 2.5 KB [from memory; Needs a test]. App passwords fit. Microsoft refresh tokens can be over 1 KB, so either split the value or store a DPAPI-encrypted file. |
| Linux | Secret Service (GNOME Keyring, KWallet) | Absent on headless machines; fall back to an encrypted file with a clear warning. |

Use the Python `keyring` library as the single interface; it maps to all three. Keep one item per mailbox, keyed by a stable mailbox id, not by project, so a mailbox can serve several projects. Store for each mailbox: auth type (app password, OAuth Google, OAuth Microsoft, generic password), the secret or refresh token, and for bring-your-own-client the client id and secret. Never write secrets to `leads.db`, logs, or crash reports.

### 5.2 Token refresh and detecting dead credentials

- Refresh access tokens lazily, a few minutes before expiry, under a per-mailbox lock so the reader and the sender do not refresh at once. Microsoft may return a NEW refresh token on each refresh; always save the latest.
- Classify failures into three kinds and treat them differently:

| Kind | Examples | Action |
|---|---|---|
| Transient | Network down, timeouts, IMAP `BYE`, SMTP 421/451, HTTP 429/5xx | Retry with backoff. Do not alarm the user until it has failed for about 30 minutes. |
| Rate limit | Gmail `550 5.4.5 Daily user sending limit exceeded`, Microsoft `5.2.252`-style throttling, 30 per minute exceeded | Pause SENDING on that inbox until the rolling window clears (24 hours for Google). Keep reading. Say so in the UI. |
| Credential dead | SMTP `535`, `534 5.7.9 Application-specific password required`, IMAP `AUTHENTICATIONFAILED`, OAuth `invalid_grant`, Microsoft `AADSTS` errors for revoked or expired grants, `535 5.7.139` | Mark the inbox "needs reconnect" at once. Stop sending from it. Hold its follow-ups. Notify. Do not retry in a loop: repeated failed logins can trip provider lockouts. |

- The usual causes of a dead credential, to name in the UI so the user knows what happened: Google password changed (kills app passwords AND Gmail-scoped refresh tokens); 2-Step Verification turned off; admin policy changed; token unused for 6 months; consent revoked; on Microsoft, a conditional access or password-change policy.

### 5.3 Re-connect experience

- One red state per inbox with one button: "Reconnect". It reopens the same wizard with the email prefilled, and on success resumes held leads automatically.
- A desktop notification and a banner in the app. Since there is no server, also consider an optional "email me at another address when an inbox breaks", sent through any still-healthy inbox.
- Never silently move a lead's follow-ups to another inbox.

### 5.4 Health checks

| Check | How | When |
|---|---|---|
| SMTP login | Connect, EHLO, AUTH, quit. No message sent. | On connect, daily, and before the first send after any failure |
| IMAP login and folders | Login, LIST, confirm All Mail and Spam (Gmail) or Inbox and Junk (others) are visible. On Gmail, a hidden "All Mail" label ("Show in IMAP" off) breaks us. | On connect, daily |
| Round trip | Send one message to the mailbox itself, confirm it arrives by IMAP within a minute, confirm the Message-ID we set survived, and read `Authentication-Results` on the received copy for `spf=pass`, `dkim=pass`, `dmarc=pass` | On connect, then weekly |
| MX | DNS MX lookup on the sending domain. Also tells us the provider (Google, Microsoft, other) so the wizard can preselect the route. | On connect, daily |
| SPF | TXT lookup for `v=spf1`. Exactly one record, includes the provider (`_spf.google.com`, `spf.protection.outlook.com`), under the 10-lookup limit | On connect, daily |
| DKIM | TXT lookup at `google._domainkey` (Workspace default selector) or `selector1._domainkey` and `selector2._domainkey` (Microsoft). Selectors can be custom, so the round-trip test is the real proof. | On connect, daily |
| DMARC | TXT lookup at `_dmarc.<domain>`. Present, valid, `p=` at least `none`; warn that `none` is the minimum and `quarantine` is better | On connect, daily |
| Domain blocklist | Spamhaus DBL and similar. Caveat: Spamhaus refuses queries that come through large public resolvers (8.8.8.8, 1.1.1.1), so results from a desktop are unreliable unless the user has a free Spamhaus DQS key. IP blocklists are pointless for Google and Microsoft shared IPs. Treat this as optional. | Weekly, best effort |
| Domain age | RDAP lookup. Warn if the domain is under about 30 days old. | On connect |
| Behavioural health | Per inbox, last 7 and 30 days: hard bounce rate, reply rate, count of our own sends whose round-trip copy landed in spam | Continuous |

### 5.5 How leaders present "inbox health"

Instantly's accounts table shows, per mailbox: a status (Active, Sending error / Disconnected, DNS error), a warmup flame toggle, emails sent today against the daily limit, and a health score percentage. A "Test domain setup" action checks MX, SPF, DKIM and DMARC and shows pass or fail for each [Verified, Instantly help summaries]. Others follow the same shape.

For us, without warmup, the honest version is a three-state badge per inbox (Healthy, Attention, Disconnected) driven by the checks above, with the reasons listed in plain words underneath ("DMARC record missing", "4 of the last 50 leads bounced", "Google refused the app password on 18 Sep, reconnect"). Avoid a made-up numeric score.

---

## Comparison table: method by provider

Friction: steps for a non-technical user. Durability: how long it keeps working untouched. Verification burden: what WE must pass as the vendor.

| Method | Provider | User friction | Durability | Verification burden on us | Capabilities |
|---|---|---|---|---|---|
| App password + SMTP/IMAP | Google Workspace, Gmail | Low to medium. 3 steps, needs 2-Step Verification on. Blocked for security-key-only and Advanced Protection accounts. | Good. Breaks on password change or if 2-Step Verification is turned off. Policy risk: Google dislikes it, no end date announced. | None | Send, read, bounces, client-set Message-ID, full mailbox access |
| OAuth, our verified client, Gmail API | Google | Lowest (one click) once verified; Workspace admin may need to trust the app | Very good. Breaks on password change (Gmail scopes), revoke, 6 months idle | Heavy. Restricted scope review of about 6 to 12 weeks, permitted-use risk for cold email, yearly re-verification, paid CASA if any server touches data (possibly exempt if local-only, unconfirmed) | Send, read, labels, threads. Message-ID behaviour needs a test |
| OAuth, our UNverified client | Google | Medium. Scary warning screen | Poor. 100-user lifetime cap; 7-day expiry if left in Testing | None, but not shippable | Same as above |
| OAuth, customer's own client, Internal | Google Workspace | High. 15 to 25 console clicks, once per Workspace | Very good. No cap, no expiry, no warning | None | Same, works with API or XOAUTH2 |
| OAuth, customer's own client, External unverified | Personal Gmail, multi-Workspace agencies | High, plus warning screen | Good if published to production | None | Same |
| Password + SMTP AUTH | Microsoft 365 | Medium. Admin must enable SMTP AUTH per mailbox, Security defaults must be off | Poor. Off by default from end of December 2026, removal date to come in second half of 2027. Cannot read mail at all (IMAP basic auth dead since 2022). | None | Send only. Not viable for us |
| OAuth, our multi-tenant public client, IMAP/SMTP XOAUTH2 | Microsoft 365, Outlook.com | Low to medium. One sign-in, often plus admin approval since late 2025; mailbox IMAP and SMTP AUTH switches must be on | Good. Refresh tokens roll; conditional access can revoke | Light. Free app registration, free publisher verification (needs a verified Partner Center account and a work account) | Send, read, reuses our IMAP/SMTP code |
| OAuth, our multi-tenant public client, Graph | Microsoft 365, Outlook.com | Low to medium. Same consent, no mailbox switches needed | Good | Light, same as above | Send, read, delta polling. Second code path. Message-ID behaviour needs a test |
| OAuth, customer's own single-tenant app | Microsoft 365 | Medium to high. About 10 portal clicks | Good | None | Same as the two rows above |
| Password or app-specific password + SMTP/IMAP | Zoho, Fastmail, Yahoo, iCloud, cPanel hosts, reseller inboxes | Low. Presets fill host and port | Good | None | Send, read |

---

## 6. Recommendation for maps-leads

### 6.1 The short answer

**(a) One Google Workspace inbox:** app password over SMTP + IMAP, which is what we have. It is the only Google route that needs nothing from Google, works today, has no user cap, and keeps our Message-ID based matching intact. The work is in the wizard and the health checks, not the protocol.

**(b) Many inboxes across providers:** one "mailbox" abstraction with pluggable auth (app password, generic password, OAuth Google, OAuth Microsoft) over ONE transport pair (SMTP + IMAP, with XOAUTH2 where OAuth is used). Add bulk CSV import because that is how reseller inboxes arrive. Microsoft needs OAuth from day one of Microsoft support, because reading with a password is impossible there.

### 6.2 Staged plan

**NOW (make one inbox solid, prepare for many)**

1. Split "mailbox" out of "project settings" into its own table: id, email, display name, signature, provider, auth type, hosts and ports, daily cap, ramp start date, send window, status, last ok, last error, IMAP cursors. A project links to one or more mailboxes.
2. Put every enrollment on a mailbox: `mailbox_id` set at the first send and never changed by the system.
3. Move secret storage behind the Python `keyring` library, one item per mailbox. Keep reading the old per-project Keychain item once, then migrate it.
4. Rebuild the connection wizard (6.3) and the health checks (6.4).
5. Classify errors into transient, rate limit, and credential dead (5.2), with per-mailbox pause and a Reconnect button.
6. Run the two cheap experiments: does smtp.gmail.com keep our Message-ID (send to self, read back), and is "All Mail" visible over IMAP on a fresh Workspace account.
7. Add provider presets for generic SMTP/IMAP (Zoho, Fastmail, Yahoo, iCloud, Outlook hosts for later) with an MX lookup that picks the preset.

**NEXT (many inboxes, Microsoft, advanced Google)**

1. Rotation: per tick, read every mailbox (stagger them), then for each mailbox that is healthy, inside its window, under its cap, and past its random gap, send at most one email. New leads go to the mailbox with the most remaining capacity today, skipping any that are not Healthy; follow-ups always use the lead's own mailbox and go first.
2. Broken mailbox policy: hold that mailbox's follow-ups; alert; after 72 hours offer the user a choice per campaign ("keep waiting" or "restart these leads from another inbox as a new thread"). Never switch silently.
3. Per-mailbox sender name and signature, exposed as merge fields.
4. Unified replies list across mailboxes; reply from the owning mailbox with correct `In-Reply-To` and `References`.
5. Bulk import by CSV: email, display name, password, smtp host, smtp port, imap host, imap port, daily cap. Validate each row with a live login, import the good ones, report the bad ones.
6. Bounce guard per mailbox AND per domain, since reputation is per domain.
7. Microsoft OAuth: register our multi-tenant public-client Entra app; complete publisher verification; implement loopback + PKCE on the existing local server; start with IMAP/SMTP XOAUTH2 to reuse code, and move sending to Graph if the SMTP AUTH switch proves to be a support burden. Give users an admin-consent link.
8. Google bring-your-own-client as an "Advanced" route for Workspace owners whose admins forbid app passwords: a step-by-step guide with a checklist, Internal user type, Desktop client, then the same loopback flow with XOAUTH2.

**LATER (remove Google friction, only if sales justify it)**

1. Ask Google, in writing through the verification process, whether a local-only desktop app with restricted Gmail scopes is exempt from the security assessment.
2. If yes: publish a homepage and a privacy policy on a verified domain, record the demo video, request `gmail.send` + `gmail.readonly` (narrower than the IMAP scope, so add a Gmail API transport), and frame the product truthfully as one-to-one personalised outreach with opt-out, do-not-contact lists and bounce guards. Budget 2 to 3 months.
3. Keep app password and bring-your-own-client forever as fallbacks; verification can be withdrawn.
4. Optional: IMAP IDLE for faster reply detection. Not needed at a 2-minute poll.

### 6.3 The connection wizard the user should see

**Step 0. Enter the email address.** We do an MX lookup and say what we found: "This address is hosted by Google Workspace." Branch on provider.

**Google path (app password):**

1. "Turn on 2-Step Verification." A button opens `https://myaccount.google.com/signinoptions/two-step-verification`. A tick box: "It is on."
2. "Create an app password." A button opens `https://myaccount.google.com/apppasswords`. Text: "Name it maps-leads. Google shows 16 letters once. Paste them here." The field strips spaces.
3. "Test." We run SMTP login, IMAP login, folder check, the send-to-self round trip, and the DNS checks, each with a live tick or cross.
4. "Sender details." Display name, signature, daily cap (default ramp 10 rising to 40), sending hours.
5. Done. Show the health card.

Inline help for the failures that really happen:

- "Google says app passwords are not available for your account": your account uses security keys only or Advanced Protection, or your Workspace admin blocks 2-Step Verification. Show the admin checklist, or offer the Advanced route (own Google Cloud client).
- "Username and password not accepted": you pasted your normal password, or you changed your Google password since creating the app password. Create a new one.
- "IMAP is turned off by your administrator": Admin console, Apps, Google Workspace, Gmail, End user access, enable IMAP.
- "We cannot see All Mail": Gmail settings, Labels, tick "Show in IMAP" for All Mail and Spam.

A copyable "message for your Workspace admin" listing the three settings.

**Microsoft path (OAuth, NEXT stage):**

1. "Sign in with Microsoft." Opens the system browser; we listen on the loopback address.
2. If Microsoft says "Need admin approval": show an "I am the admin" button (opens the admin-consent link) and a "Send this to my admin" text.
3. Test. If sending fails with `5.7.139`, show: Microsoft 365 admin center, Users, Active users, pick the user, Mail, Manage email apps, tick Authenticated SMTP and IMAP, wait up to an hour. Also mention Security defaults.
4. Sender details. Done.

Until OAuth ships, the Microsoft branch should say plainly: "Microsoft mailboxes are not supported yet, because Microsoft no longer allows password sign-in for reading mail."

**Other provider path:** preset or manual host and port, username, password (hint: "if you use two-factor sign-in, create an app-specific password at your provider"), Test, Sender details.

**Bulk path:** upload CSV, live progress per row, summary of connected and failed with reasons.

### 6.4 Health checks to run

**On connect:** MX and provider detection; SMTP login; IMAP login; folder visibility (All Mail and Spam, or Inbox and Junk); send-to-self round trip with Message-ID survival and `Authentication-Results` parse; SPF, DKIM, DMARC lookups; domain age; warn if the sender domain is the same as the project's main website domain.

**Every tick (2 minutes):** nothing extra. The read and the send ARE the check. Record last success and last error per mailbox. Apply the three-way error classification.

**Daily:** SMTP and IMAP login if the mailbox has been idle for 24 hours; SPF, DKIM, DMARC, MX lookups (records get broken by unrelated DNS edits); recompute 7-day bounce rate and reply rate per mailbox and per domain; check the cap and ramp; for OAuth mailboxes, a token refresh so a 6-month idle expiry can never happen.

**Weekly:** the round trip again (catches DKIM breakage and our own mail landing in spam); best-effort domain blocklist lookup.

### 6.5 Risks

1. **Google ends app passwords.** No date announced, but Google labels them "not recommended" and has tightened steadily. Mitigation: bring-your-own-client in the NEXT stage so a fallback exists before it is needed; verification in LATER.
2. **Workspace tenants that block app passwords** (security-key enforcement, Advanced Protection, strict admins). These customers cannot connect until the Advanced route ships. Expect this mostly at larger agencies, less among solo operators.
3. **Password change silently kills the connection** for both app passwords and Gmail-scoped OAuth tokens. Mitigation: fast detection, a clear reason, one-click reconnect, held follow-ups.
4. **Microsoft admin-consent friction** since late 2025, and the SMTP AUTH default-off change at the end of December 2026. Mitigation: admin-consent link; prefer Graph for sending if SMTP AUTH causes tickets. Publisher verification needs a verified business identity in Partner Center, which takes calendar time.
5. **Google verification may refuse a cold-email product** under the "unsolicited commercial mail" clause, and the local-only exemption from the security assessment is unconfirmed. Do not promise customers one-click Google sign-in.
6. **Message-ID assumptions.** Our reply and bounce matching depends on the Message-ID we generate surviving. Reported to hold for Gmail SMTP with a well-formed id; reported NOT to hold for the Gmail API; unknown for Microsoft Graph MIME sends. Test each transport before relying on it, and store the id read back from the Sent copy rather than the one we generated.
7. **A laptop is not a server.** When the lid is closed nothing sends and nothing is read. With several inboxes, a long sleep means a burst of due follow-ups on wake. Mitigation: keep the one-per-mailbox-per-tick pacing and the random gaps after wake; never "catch up".
8. **Secrets on the user's disk.** Keychain items are readable by other software running as the same user. An app password grants full mailbox access. State this honestly in the docs; never log secrets; offer "remove this inbox and delete its secret".
9. **Deliverability is the user's responsibility but our reputation.** Without warmup and with user-owned domains, some users will burn domains and blame the tool. Mitigation: conservative defaults, DNS checks that block sending when SPF or DKIM is missing, per-domain bounce guard, and plain guidance on domains and volumes (4.2).
10. **Bring-your-own-client instructions rot** because Google and Microsoft rearrange their consoles. Keep the guide as a hosted page we can update without shipping a new build.

---

## Sources

Google, primary:

- Transition from less secure apps to OAuth (Workspace admin help): https://knowledge.workspace.google.com/admin/sync/transition-from-less-secure-apps-to-oauth
- Workspace Updates blog, winding down less secure apps and Google Sync: https://workspaceupdates.googleblog.com/2023/09/winding-down-google-sync-and-less-secure-apps-support.html
- Sign in with app passwords (Google Account help): https://support.google.com/accounts/answer/185833
- Less secure apps and your Google Account: https://support.google.com/accounts/answer/6010255
- Gmail API scopes: https://developers.google.com/workspace/gmail/api/auth/scopes
- Restricted scope verification: https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification
- OAuth app verification help center: https://support.google.com/cloud/answer/13463073
- OAuth verification FAQ (100-user cap, timelines, assessment cost policy): https://support.google.com/cloud/answer/13463817
- Verification requirements: https://support.google.com/cloud/answer/13464321
- Security assessment: https://support.google.com/cloud/answer/13465431
- Restricted scopes list: https://support.google.com/cloud/answer/13464325
- Manage app audience (Internal vs External, Testing, 7-day expiry): https://support.google.com/cloud/answer/15549945
- Using OAuth 2.0 (refresh token expiry reasons): https://developers.google.com/identity/protocols/oauth2
- OAuth 2.0 for desktop apps (loopback, PKCE): https://developers.google.com/identity/protocols/oauth2/native-app
- Google Workspace API user data and developer policy (permitted Gmail app types): https://developers.google.com/workspace/workspace-api-user-data-developer-policy
- Google API Services User Data Policy: https://developers.google.com/terms/api-services-user-data-policy
- Control which apps access Google Workspace data (API controls, Trusted, Trust internal apps): https://knowledge.workspace.google.com/admin/apps/control-which-apps-access-google-workspace-data
- Turn POP and IMAP on or off for users: https://support.google.com/a/answer/105694
- Gmail sending limits in Google Workspace: https://knowledge.workspace.google.com/admin/gmail/gmail-sending-limits-in-google-workspace
- Gmail API usage limits (updated 2026-09-10): https://developers.google.com/workspace/gmail/api/reference/quota
- Gmail API, managing threads: https://developers.google.com/workspace/gmail/api/guides/threads
- Gmail API, synchronising clients (history.list): https://developers.google.com/workspace/gmail/api/guides/sync
- Gmail API, push notifications: https://developers.google.com/workspace/gmail/api/guides/push
- Email sender guidelines FAQ: https://support.google.com/a/answer/14229414

Microsoft, primary:

- Deprecation of Basic authentication in Exchange Online (updated 2026-07-16): https://learn.microsoft.com/en-us/exchange/clients-and-mobile-in-exchange-online/deprecation-of-basic-authentication-exchange-online
- Updated Exchange Online SMTP AUTH Basic Authentication deprecation timeline (Exchange team blog, 2026-01-27; body did not load for me): https://techcommunity.microsoft.com/blog/exchange/updated-exchange-online-smtp-auth-basic-authentication-deprecation-timeline/4489835
- Exchange Online to retire Basic auth for Client Submission (original announcement): https://techcommunity.microsoft.com/blog/exchange/exchange-online-to-retire-basic-auth-for-client-submission-smtp-auth/4114750
- Enable or disable SMTP AUTH in Exchange Online: https://learn.microsoft.com/en-us/exchange/clients-and-mobile-in-exchange-online/authenticated-client-smtp-submission
- Authenticate an IMAP, POP or SMTP connection using OAuth: https://learn.microsoft.com/en-us/exchange/client-developer/legacy-protocols/how-to-authenticate-an-imap-pop-smtp-application-by-using-oauth
- Publisher verification overview (updated 2026-06-15): https://learn.microsoft.com/en-us/entra/identity-platform/publisher-verification-overview
- Manage app consent policies: https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/manage-app-consent-policies
- Exchange Online limits (updated 2026-09-09): https://learn.microsoft.com/en-us/office365/servicedescriptions/exchange-online-service-description/exchange-online-limits
- Exchange Online cancelling the Mailbox External Recipient Rate Limit: https://techcommunity.microsoft.com/blog/exchange/exchange-online-canceling-the-mailbox-external-recipient-rate-limit/4483498
- Message Center MC1163922, Secure by Default changes for Exchange and Teams APIs (archive): https://mc.merill.net/message/MC1163922

Microsoft, secondary:

- SMTP AUTH client submission retirement delayed (2026-01-29): https://office365itpros.com/2026/01/29/smtp-auth-basic-retirement/
- App consent policy to block third-party apps (2025-06-19): https://office365itpros.com/2025/06/19/app-consent-policy-user-app-consent/
- Exchange mailbox external recipient rate limit cancelled (2026-01-08): https://office365itpros.com/2026/01/08/mailbox-external-recipient-rate/
- Microsoft-managed default app consent policy now blocks 20 additional permissions (returned 403 for me): https://blog-en.topedia.com/2025/11/microsoft-managed-default-app-consent-policy-now-blocks-20-additional-permissions/

Vendor help centers:

- Instantly, connect Google via OAuth: https://help.instantly.ai/en/articles/6697278-how-to-connect-google-accounts-via-google-oauth-method
- Instantly, connect Google via app password: https://help.instantly.ai/en/articles/6502998-how-to-connect-google-accounts-to-instantly-via-app-password-method
- Instantly, Google blocking app access: https://help.instantly.ai/en/articles/7930507-google-blocking-app-access
- Instantly, Microsoft 365 account setup: https://help.instantly.ai/en/articles/7938418-microsoft-365-account-setup
- Instantly, email accounts dashboard: https://help.instantly.ai/en/articles/11991261-getting-started-with-email-accounts-dashboard
- Instantly, warmup health score: https://help.instantly.ai/en/articles/13939939-warmup-health-score
- Smartlead, connect Gmail with SMTP: https://helpcenter.smartlead.ai/en/articles/4-connect-gmail-with-smtp
- Smartlead, Google OAuth one-click: https://helpcenter.smartlead.ai/en/articles/18-gmailgoogle-oauth-1-click-authentication
- Smartlead, Private Infrastructure (OAuth) for Google: https://helpcenter.smartlead.ai/en/articles/296-how-to-set-up-private-infrastructure-oauth-in-smartlead-for-google
- Smartlead, bulk add email accounts: https://helpcenter.smartlead.ai/en/articles/12-bulk-add-email-account
- lemlist, connect your email provider: http://help.lemlist.com/en/articles/4536030-connect-your-email-provider-to-lemlist
- lemlist, inbox rotation: http://help.lemlist.com/en/articles/8263428-use-inbox-rotation-for-campaigns
- Woodpecker, connect Microsoft/Outlook: https://woodpecker.co/help-center/en/articles/5214094-how-to-connect-microsoft-outlook-email-account-to-woodpecker
- Woodpecker, inbox rotation: https://woodpecker.co/help-center/en/articles/8398672-inbox-rotation-how-to-send-from-multiple-email-accounts
- Hunter, email account rotation: https://help.hunter.io/en/articles/8278231-email-account-rotation
- Mailmeteor, inbox rotation: https://mailmeteor.com/docs/campaigns/inbox-rotation
- Mailshake, SMTP/IMAP: https://docs.mailshake.com/article/189-how-do-i-send-emails-with-smtp
- Saleshandy, connect an email account: https://docs.saleshandy.com/en/articles/6948265-how-to-connect-email-account-provider-with-saleshandy
- Saleshandy, SMTP/IMAP any provider: https://docs.saleshandy.com/en/articles/6942767-smtp-imap-how-to-connect-any-email-account-provider-with-saleshandy
- Apollo, link your mailbox (returned 403 for me): https://knowledge.apollo.io/hc/en-us/articles/4409127806093-Link-Your-Mailbox-to-Apollo

Warmup history and deliverability:

- GMass, warmup system is shutting down: https://www.gmass.co/blog/warmup-shutting-down/
- ISIPP, Google gives Gmail mass email services the boot (text of Google's notice): https://www.isipp.com/blog/google-gives-gmail-mass-email-services-the-boot/
- Growbots, Google bans cold email warmup: https://www.growbots.com/blog/google-bans-cold-email-warmup/
- GMass, Gmail bulk sender guidelines: https://www.gmass.co/blog/gmail-bulk-sender-guidelines/
- Red Sift, Gmail enforcement ramps up: https://redsift.com/blog/gmails-enforcement-ramps-up-what-bulk-senders-need-to-know
- Mailreach, how many cold emails per day: https://www.mailreach.co/blog/how-many-cold-emails-to-send-per-day
- Litemail, how many domains and inboxes: https://litemail.ai/blog/how-many-email-inboxes-do-you-need-for-cold-email-in-2026

Other:

- BreazyLabs/OutreachEmailMCP (open-source gateway, bring-your-own OAuth apps): https://github.com/BreazyLabs/OutreachEmailMCP
- Mixmax, moving to the Gmail API: https://www.mixmax.com/engineering/moving-to-the-gmail-api
- Gmail overwriting Message-Id header (comp.mail.sendmail thread): https://groups.google.com/g/comp.mail.sendmail/c/gkRdBwka4iw
- rclone forum, 7-day reconnect of Google OAuth: https://forum.rclone.org/t/7-day-reconnect-of-google-drive-oauth/50148
- Mailbird, Gmail OAuth changes article (headline claim about 2026 app password phase-out is not supported by its own body): https://www.getmailbird.com/gmail-oauth-changes-app-password-phase-out/
