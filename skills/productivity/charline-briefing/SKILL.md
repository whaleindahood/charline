---
name: charline-briefing
description: Use when Charline creates recurring personal briefings.
version: 1.0.0
author: Charline Project
license: MIT
metadata:
  hermes:
    tags: [charline, briefing, cron, automation]
    related_skills: [charline-workspace, charline-calendar, charline-research]
---

# Charline Briefing

## Overview

This skill defines reliable read-only briefings delivered through Hermes cron. It keeps each scheduled run self-contained, observable and safe to repeat.

## When to Use

Use for morning/evening summaries, weekly planning, inbox/calendar reviews and recurring information digests. Do not create or change a cron job until schedule, timezone, sources and delivery target are confirmed.

## Brief Definition

Resolve:

- purpose and sections;
- schedule and `Europe/Moscow` timezone unless explicitly changed;
- included calendars/mail queries/documents/sources;
- delivery destination;
- handling of empty data and partial source failures;
- whether the briefing should be continuable in the main session.

Show this definition and obtain confirmation before creating the job.

## Cron Contract

The future run has no current-chat context. Its prompt must include user-facing language, timezone, exact date-window rules, source queries, required skills, read-only boundary, output format and failure behavior. Attach only required toolsets and skills.

A briefing must not recursively schedule jobs, send email, change calendar data or mutate documents. It may deliver its final report to the confirmed target. Use deterministic scripts only for data collection or change detection; keep reasoning in the agent when synthesis is needed.

## Reliability

- Make repeated runs safe and avoid duplicate notifications where possible.
- Report source failures by section; do not label the whole system unavailable when one source fails.
- Keep output quiet when no notification is useful only if that behavior was explicitly selected.
- Verify the created cron job by listing/read-back of its schedule, skills and destination.
- For conversational daily briefs, use session attachment where supported.

## Suggested V1 Brief

A morning brief may include today's Calendar agenda, urgent unread Gmail, user-confirmed reminders and weather only when a current weather source is available. It is read-only and should finish with concise priorities plus detected conflicts.

## Verification Checklist

- [ ] Purpose, schedule, timezone and destination confirmed
- [ ] Sources and empty/error behavior defined
- [ ] Prompt is self-contained and read-only
- [ ] Minimal skills/toolsets attached
- [ ] Job created only after confirmation
- [ ] Job listed/read back and delivery target verified
- [ ] Repeated execution cannot create external duplicates
