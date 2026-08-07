---
name: charline-calendar
description: Use when Charline handles calendars or scheduling.
version: 2.0.0
author: Charline Project
license: MIT
metadata:
  hermes:
    tags: [charline, calendar, scheduling, safety]
    related_skills: [google-workspace, charline-workspace, charline-orchestration]
---

# Charline Calendar

## Overview

This skill governs agenda reads, free-slot planning and safe Google Calendar transactions. Google Calendar remains the source of truth; deterministic code handles time arithmetic and conflict checks.

## When to Use

Use for agenda questions, availability, event drafts, creation, updates, deletion, recurrence and agenda briefings. Do not interpret casual discussion as authorization to change a calendar.

## Time Contract

Resolve timezone-aware start and end values, calendar, title, attendees, location, recurrence scope and notifications. Use the confirmed profile timezone (`Europe/Moscow` for the current user) unless the user explicitly supplies another timezone. Clarify genuinely ambiguous dates or durations.

For current-day availability, begin no earlier than the actual current time in calendar timezone. Past days have no free slots. Apply configured work windows and buffers, merge busy intervals, and offer at most three ranked options unless more are requested.

## Read Operations

Agenda and availability reads require no confirmation. Load `google-workspace`, read source events, ignore cancelled/transparent events where appropriate, expand recurrence through the API, and show local times. Do not invent missing events.

## Transaction Flow

1. Read relevant events and constraints.
2. Build one exact draft.
3. Check conflicts and buffers.
4. Preview title, date, time, timezone, calendar, attendees, location, recurrence and notifications.
5. Obtain explicit confirmation for that latest draft.
6. Recheck conflicts immediately before writing.
7. Execute one idempotent write.
8. Read the event back by returned ID and compare critical fields.
9. Report verified result and link.

A changed or superseded draft requires a new preview and confirmation. For recurring updates/deletes, explicitly resolve one occurrence, this-and-following, or the entire series. Deletes require strengthened confirmation and absence/deleted-state verification.

## Briefings

A calendar briefing is read-only. Schedule it with `charline-briefing` only after confirming delivery time, timezone, calendars and destination.

## Failure Handling

Unknown write outcome requires narrow read-by-ID/search before retry. Conflict after confirmation stops the write and produces alternatives. Authentication, timezone or recurrence ambiguity blocks the transaction rather than triggering a guess.

## Verification Checklist

- [ ] Intent and timezone resolved
- [ ] Source calendar data read
- [ ] Conflicts and buffers checked
- [ ] Latest exact draft confirmed for writes
- [ ] Conflict rechecked immediately before write
- [ ] One idempotent call executed
- [ ] Event read back and critical fields compared
