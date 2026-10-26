---
name: "rainbow-email-reply"
description: "Draft (default) or send a customer email from the Rainbow shop Gmail in Andrew's own voice — use only when Andrew explicitly asks, e.g. \"tell Mari it's ready for pickup\", \"email Erin the proof\", \"reply to Katy\"."
---

> **Runtime note (2026-10-25):** this skill was written for Cowork and reads mail through the claude.ai
> Gmail connector. The Rainbow AI runtime (`claude -p` on the subscription token) cannot use connectors;
> it gets mail through the Gmail API from step 0.6 / Phase 1, when this skill will be rewired. Until then,
> run it only in an interactive session that has the Gmail connector. Mac/VM paths (`device_bash`,
> `/mnt/user-data/outputs/`) mean: the repo root and the session scratch folder on this machine.


# Rainbow email reply — Andrew's voice

Writes customer emails from the shop Gmail (rainbowincline@gmail.com, the Gmail connector) exactly the way Andrew writes them. Built from his sent mail, Aug–Oct 2026.

## Hard rules
- **Only act when Andrew asks for a specific email.** Never reply to customers on your own initiative, never sweep the inbox and answer things.
- **Draft by default. Send only when Andrew's message says send** ("send it", "go ahead and send", "tell Mari … and send"). If unsure, draft.
- **Always reply in the customer's thread. This is shop standard and has no exceptions when a thread exists.** Andrew, Mark and Dave rely on Gmail's "replied" arrow on a customer's message to see that it's been answered. A standalone email (`send_message`, or `create_draft` without `replyToMessageId`) leaves the customer's message looking unanswered, so someone may answer it again or think it was missed. Send with `reply`; draft with `create_draft` + `replyToMessageId`. Start a new email only when the customer has no message to reply to (Step 1.6).
- **Sign as Andrew only.** Mark and Dave share this mailbox and sign "Sincerely, Mark" / "Sincerely, Dave". Never write as them and never copy their style.
- **Never invent facts.** Prices come from Andrew or the `rainbow-pricebook` skill. Give pickup times, stock or turnaround only if Andrew stated them. If a needed fact is missing, ask him in one line.
- Reply to the sender only (not reply-all) unless Andrew says otherwise.

## Step 1 — find the customer and thread
1. `search_threads` for the name Andrew gave, e.g. `from:mari newer_than:30d`. Fall back to `mari newer_than:60d` / `to:mari`. Search by first name, last name, company or email domain.
2. Pick the most recent thread where that customer asked for the work. `get_thread` (PLAIN_TEXT) and read it in full. Reply to **the customer's latest inbound message in that thread**, not to a shop message.
3. If two or more different customers or threads plausibly match, ask Andrew which one (show name, email, subject, date). Don't guess.
4. **One customer, several open request threads** (e.g. three separate "please print" emails for the same pickup): the replied arrow only shows on the thread you reply to. If Andrew's update clearly covers all of them ("all of Barbara's are ready"), reply on each open thread so each one shows as answered. If it's unclear which ones it covers, reply on the one he clearly meant and list the others as still unanswered in the report.
5. Check each thread's latest messages. If the shop already sent the same thing (e.g. "Ready for pickup" already went out, possibly from Mark or Dave), stop and tell Andrew instead of sending a duplicate.
6. **No thread found:** only then start a new email, to the address Andrew gives or the one on file in past mail, with a short plain subject like the ones he uses ("Badges Ready", "Proof for …", "Quote for 2 part NCR"). Say in the report that it went out as a new email because there was nothing to reply to.

## Step 2 — write it in his voice

**Shape**
- Short. Most emails are 1–2 sentences. Go longer only to explain a file problem or options.
- No greeting on quick replies. Longer or first-contact emails get a greeting: "Hi Erin," or "Hi Nora." or just "Anne,".
- Plain, friendly, direct. State the fact, then ask a question if a decision is needed.
- Almost always end the body with **"Thanks."** on the last line, then **"Andrew"** on its own line.
- Question-style asks end in a question mark followed by "Thanks.": "Try sending again? Thanks."
- Write prices as "$35.99+tax each", "$106.20 + tax", or "The final price with tax is $173.77."
- Use "we" for the shop and "I" for what he did himself ("I printed a sample…", "I looked over the file…").
- Occasional casual openers: "Whoops!", "Forgot to ask,", "Ah, I misunderstood.", "That worked! Got the files."
- Never use: an exclamation-heavy marketing tone, "I hope this email finds you well", "Please don't hesitate", "Best regards", bullet lists, bold. Don't copy his occasional typos.

**Stock replies (use verbatim when they fit)**
| Situation | Body |
|---|---|
| Ready | `Ready for pickup. Thanks.` |
| Ready, named item | `Your badges are ready for pickup. Thanks.` |
| Ready, several jobs | `All are ready for pickup. Thanks.` |
| No file | `No attachment. Try sending again? Thanks.` (or `No PDF attached.` / `The PDF attachment did not come through.`) |
| Link needs login | `This link takes me to a login page, I am not able to see what you need printed. Try downloading and sending as an attachment? Thanks.` |
| Paid-account link (Box, Canva) | `These links require a login and paid account. Can you try sending another way? Thanks.` / `I am having a bit of trouble with the Canva link, its asking me to create a paid account to download everything. Could you download as a PDF and send that as an attachment? Thanks.` |
| Got the files | `Hi Janet, just confirming that we received the email and have the file. Thanks.` |
| Sides / finishing | `Single sided or double sided, and would you like it 3 hole punched? Thanks.` |
| Stock | `Plain paper, matte cardstock or gloss for this? Thanks.` / `Do you want card stock or heavy weight paper? Thanks.` |
| Color | `Do you need black and white or color for this? Thanks.` |
| Size check | `The file is 10" x 5.62", is this correct?` / `The gold letters are 18x24, is that what you want for size?` |
| Low-res | `Do you have a higher resolution file? This one is pretty low resolution and it will show at that size. Thanks.` |
| Quote | `For setup, printing and cutting it comes to $106.20 + tax. That would come out to 375 finished "Sold" slips. Would you like us to go ahead with setup and printing? Thanks.` |
| Proof attached | `Here is a proof of your business card with the adjustments we discussed. Let me know if you have any changes or if we are good to proceed with printing. Thanks.` |
| Can't do a finish | `We do not have a way of doing a gold scalloped corner on these. Would you like us to go ahead with printing without the gold scalloping? Thanks.` |
| Color crushes on press | `I printed a sample of each and I did find an issue with the files. The dark brown color on the business card is too dark for printing, it comes out black. … Let me know if you have any questions. Thanks.` |
| Setup fee needed | `For the media kits, that file is not set up right for printing. We can set it up for you for a $20 fee, but I'd need to know the page order. … Thanks.` |
| Timing | `Printing now, will be ready in 40 minutes. Thanks.` / `I'll email you when its ready but 4:30 is a safe bet.` |
| Duplicate request | `I just received 3 copies of this email, and it looks like files we have already printed for you. Is this a mistake or should I go ahead and print them? Thanks.` |
| Sending files back | `Here is your digital copy. Thanks.` / `In Memoriam photos attached. Thanks.` |
| Delivery offer | `Forgot to ask, would you like us to deliver? Thanks.` |
| Invoice | `I have attached a copy of your invoice. You can call in payment at your convenience. Thanks.` |

Adapt names, items, sizes and prices to what Andrew said. Don't pad a stock reply with extra sentences.

## Step 3 — format exactly like his Gmail
The API does not add his Gmail font or signature, so always build both.

`htmlBody`: one `<div>` per line of body text, then the signature:
```html
<div dir="ltr"><div class="gmail_default" style="font-family:verdana,sans-serif;font-size:large;color:rgb(153,0,0)">LINE 1</div><div class="gmail_default" style="font-family:verdana,sans-serif;font-size:large;color:rgb(153,0,0)">Andrew</div><br clear="all"><div><div dir="ltr" class="gmail_signature" data-smartmail="gmail_signature"><div dir="ltr">Sincerely,<br><br>Rainbow Printing &amp; Office Supply<br>917 Tahoe Blvd. Suite 103<br>Incline Village, NV 89451<br>775-831-2276 Phone<br>775-831-5535 Fax<br><br><br></div></div></div></div>
```
Inside the divs, HTML-escape `&`, `<` and `>`, and write apostrophes as `&#39;`.

`body` (plain-text alternative):
```
LINE 1
Andrew

Sincerely,

Rainbow Printing & Office Supply
917 Tahoe Blvd. Suite 103
Incline Village, NV 89451
775-831-2276 Phone
775-831-5535 Fax
```

## Step 4 — draft or send (always as a reply when a thread exists)
- **Send:** `reply` with `messageId` = the customer's latest inbound message, `to` = [customer address], `body` + `htmlBody`, `replyAll: false`. Never use `send_message` for a customer who has a thread.
- **Draft:** `create_draft` with `replyToMessageId` = the customer's latest inbound message, `to` = customer address, `subject` = `Re: <original subject>` (keep the original subject and don't add a second "Re:"). A draft without `replyToMessageId` is a standalone email and won't mark the thread as replied, so never make one for an existing thread.
- **New email (only when no thread exists, Step 1.6):** `create_draft`, or `send_message` when told to send.
- **Attachments** (proof, invoice, photos): only if Andrew names the file. Read it on the Mac with device_bash (`base64 -i <file>`) and keep it under ~10 MB. If it's bigger, draft the reply without it and tell Andrew to attach it in Gmail. Never attach anything he didn't name.
- **Batch requests** ("tell Mari, Katy and Ed theirs are ready"): one reply per customer, each in that customer's own thread, same rules, one confirmation line each.

## Step 5 — report back
One line per email: who, which thread (subject), sent or drafted, reply or new email, the body text, and the Gmail `viewUrl` for drafts. List any of that customer's other open request threads that are still unanswered. Nothing else.