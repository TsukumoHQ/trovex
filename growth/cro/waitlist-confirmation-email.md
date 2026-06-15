# Waitlist confirmation email — DRAFT

*Owner: cro-lead · copy-gate. DRAFT — not wired to send. Live sending needs an email
sender + operator sign-off (external send is gated; see autonomy-rules).*

## Status

The on-page confirmation state ("You're on the list…") ships live in the waitlist PR.
This **email** is a draft: trovex has no transactional sender configured, and sending
to a real inbox is an external action that needs the operator to wire it and approve.

## When/how it would send

Auto-sent from `web/api/waitlist.js` on a successful capture, only if a sender is
configured (e.g. `WAITLIST_RESEND_API_KEY` + a verified from-address). Until then,
the page confirmation is the whole experience and that's fine — no email beats a
broken/spammy one.

## Draft copy

> **Subject:** You're on the trovex beta list
>
> Thanks for the interest — you're on the list for the trovex private beta.
>
> What happens next: we let people in as spots open and you'll get an invite from this
> address when yours does. The beta is small on purpose, so we won't promise a date.
>
> trovex gives your coding agents one canonical doc per query instead of rereading the
> repo — about 60% fewer tokens on doc lookups, running locally on your machine.
>
> Nothing else will land in your inbox until your invite. Didn't sign up? Ignore this
> and you won't hear from us again.
>
> — the trovex team

## Rules (if/when it's wired)

- **Honest:** no fake "you're #142 in line", no countdown, no fabricated timeline.
- **One email.** No drip, no newsletter, no list-selling. The next email is the invite.
- **Deliverability:** verified from-domain (SPF/DKIM), a real reply-to, plain text or
  light HTML — no marketing-template bloat.
- **Double opt-in not required** for a single transactional confirmation, but include a
  clear "didn't sign up? ignore this" line (above).
- **No PII beyond the recipient's own address;** don't echo other signups.

## Coordinate
- analytics-lead: a `waitlist_confirmation_sent` event could close the loop, but only
  if it carries no PII (count/source only).
- Operator: choose the sender (Resend / SES / Postmark) and approve go-live.
