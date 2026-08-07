---
name: charline-reminders
description: Use when Charline creates, changes, lists, or disables reminders.
version: 1.0.0
author: Charline Project
license: MIT
metadata:
  hermes:
    tags: [charline, reminders, cron, safety]
    related_skills: [charline-orchestration, charline-command-center]
---

# Charline Reminders

## Overview

This skill uses Hermes cron for durable reminders. It does not implement another scheduler or reminder database.

## When to Use

Use for one-time and recurring reminders, listing reminder jobs, and confirmed changes/disables. Casual statements are not scheduling authorization.

## Reminder Contract

Resolve text, next run, timezone, recurrence, delivery target, quiet/empty behavior and duplicate-delivery key. Future cron prompts are self-contained and receive only required skills/tools.

Build the draft with `python scripts/plan_reminder.py` using JSON on stdin. This helper validates future one-time timestamps, five-field cron expressions and IANA timezones; it only returns a draft and never creates a job.

## Write Policy

Cron create/change/disable/delete requires exact preview and explicit confirmation. Execute one Hermes cron mutation and read the job back, comparing schedule, timezone, prompt hash and destination. Unknown outcome requires listing/searching jobs before retry.

## Verification Checklist

- [ ] Text, schedule, timezone and destination resolved
- [ ] Latest exact preview explicitly confirmed
- [ ] Self-contained bounded prompt used
- [ ] Duplicate-delivery key defined
- [ ] Job listed/read back after mutation
- [ ] No second scheduler or local reminder store created
