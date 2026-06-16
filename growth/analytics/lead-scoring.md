# Qualified-Lead Scoring (ICP-fit band)

*Owner: analytics-lead · Status: LIVE (central Supabase) · Applies to: `leads` rows where `project='tsukumo'`*

The north star is **qualified reach → consulting leads**, not raw count. This scores each
consulting lead by ICP-fit at capture and stores a coarse band (`hot`/`warm`/`cold`) next to
it, so the dashboard reports **qualified** leads and the **suite → qualified** rate — and
experiments optimize for lead quality, not vanity volume.

Server-side, in the database. PII (email/message) is read only to **compute** the band; only
the band + score (non-PII coarse labels) are stored and surfaced. No profile is exported.

## How it runs (no app/route change)

A `BEFORE INSERT` trigger on `public.leads` fills `lead_score` (0–100) + `lead_band`. It's
**guarded to `project='tsukumo'`** (other projects' leads stay null) and **exception-safe**
(any error → band stays null, the insert is never blocked — a scoring bug can't lose a lead).
The capture route (`/api/contact`) is untouched. Scoring also lives as reusable immutable
functions (`lead_score_of`, `lead_band_of`) so backfills and dashboard reads use the same rules.

## The rubric (coarse, heuristic — a band, not a verdict)

| Signal | Points | Why |
|--------|------:|-----|
| Suite-sourced (`channel=oss_suite` or `how_heard ∈ {wraith,trovex,yoru}`) | +30 | the north-star source — came through the OSS |
| `how_heard=referral` | +12 | warm intro |
| `how_heard ∈ {ai_assistant, search}` | +5 | active discovery |
| Company present | +15 | a real organization |
| Work email (domain not a free provider) | +20 | B2B buyer signal |
| Message has team/scale cue (`team`, `engineers`, `roll out`, `cto`, `head of`, …) | +12 | ICP: a team, not a solo tinkerer |
| Message has prod-AI cue (`production`, `agentic`, `agents`, `claude code`, `cursor`, …) | +10 | real intent to run agents in prod |
| Substantial message (>120 chars) | +5 | wrote a real ask |

**Bands:** `hot ≥ 55` · `warm ≥ 30` · `cold < 30` (score capped at 100). **Qualified =
hot + warm.** Thresholds are deliberately legible and tunable as real leads arrive — these
are heuristics on the signals we actually capture, not a model.

Verified on synthetic inserts (then deleted): suite+work-email+company+team/prod message → 92
(hot); search+work-email+"agents for prod" → 35 (warm); gmail+no-company+"hi" → 0 (cold);
a non-tsukumo row → null (correctly unscored).

## Reporting

```sql
-- qualified leads by band (this week), suite-sourced split
select coalesce(lead_band,'unscored') as band,
       count(*) as leads,
       count(*) filter (where channel='oss_suite' or lower(how_heard) in ('wraith','trovex','yoru')) as suite
from public.leads
where project='tsukumo' and created_at >= now() - interval '7 days'
group by 1 order by array_position(array['hot','warm','cold','unscored'], coalesce(lead_band,'unscored'));
```

- **Qualified-lead count** = `hot + warm`. **Suite→qualified rate** = qualified suite leads ÷
  suite `tsukumo_visit` (Plausible). Feeds [`weekly-digest-template.md`](./weekly-digest-template.md)
  and the [dashboard](./suite-agency-funnel-dashboard.md) headline.
- Report bands aggregate only — never a per-lead profile.

## Privacy

- Email/message are read **inside the database** to compute the band; **only `lead_band` /
  `lead_score`** (coarse, non-PII) are stored and reported. No PII leaves Supabase, no email
  in analytics, no individual profiling.
- The band is a sales-prioritization label, not a judgement exported anywhere public.

## The migration (applied to central Supabase — recorded here, no repo migration tracking exists)

```sql
alter table public.leads add column if not exists lead_score smallint;
alter table public.leads add column if not exists lead_band  text;

create or replace function public.lead_score_of(
  p_channel text, p_how_heard text, p_company text, p_email text, p_message text
) returns int language sql immutable as $$
  select least(100,
      (case when p_channel='oss_suite' or lower(coalesce(p_how_heard,'')) in ('wraith','trovex','yoru') then 30
            when lower(coalesce(p_how_heard,''))='referral' then 12
            when lower(coalesce(p_how_heard,'')) in ('ai_assistant','search') then 5 else 0 end)
    + (case when coalesce(btrim(p_company),'')<>'' then 15 else 0 end)
    + (case when lower(split_part(coalesce(p_email,''),'@',2)) <> ''
              and lower(split_part(coalesce(p_email,''),'@',2)) <> all (array[
                'gmail.com','googlemail.com','outlook.com','hotmail.com','live.com','yahoo.com',
                'icloud.com','me.com','proton.me','protonmail.com','gmx.com','aol.com','mail.com','yandex.com'])
            then 20 else 0 end)
    + (case when lower(coalesce(p_message,'')) ~ '(team|engineers|devs|developers|roll ?out|onboard|at scale|head of|cto|vp eng|engineering manager)' then 12 else 0 end)
    + (case when lower(coalesce(p_message,'')) ~ '(production|prod|agentic|agents|ai coding|claude code|cursor|copilot|fleet)' then 10 else 0 end)
    + (case when length(lower(coalesce(p_message,''))) > 120 then 5 else 0 end));
$$;

create or replace function public.lead_band_of(p_score int) returns text language sql immutable as $$
  select case when p_score is null then null when p_score>=55 then 'hot' when p_score>=30 then 'warm' else 'cold' end;
$$;

create or replace function public.score_lead() returns trigger language plpgsql as $$
begin
  if coalesce(new.project,'') <> 'tsukumo' then return new; end if;
  new.lead_score := public.lead_score_of(new.channel,new.how_heard,new.company,new.email,new.message);
  new.lead_band  := public.lead_band_of(new.lead_score);
  return new;
exception when others then
  new.lead_score := null; new.lead_band := null; return new;
end; $$;

drop trigger if exists trg_score_lead on public.leads;
create trigger trg_score_lead before insert on public.leads
  for each row execute function public.score_lead();
```

> **For fullstack:** this is a direct additive migration on the shared central Supabase (no
> SQL-migration tracking exists in the repos today). If you start tracking DB migrations,
> reconcile this. It cannot break the lead-capture path (exception-safe, project-guarded).

## Acceptance

- [x] Server-side scoring of `assessment_request`/`leads` from captured signals → `hot`/`warm`/`cold`.
- [x] Stored next to the lead (`lead_band`/`lead_score`); only the band/aggregate surfaces, PII stays in Supabase.
- [x] Exception-safe + project-guarded — cannot block or corrupt the capture path; verified on synthetic inserts.
- [x] Dashboard/digest report qualified leads + suite→qualified rate.
- [ ] Tune thresholds once real leads accrue (heuristics, not a model).
