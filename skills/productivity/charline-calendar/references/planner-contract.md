# Availability planner contract

Hermes reads Calendar through the official `google-workspace` skill, expands recurrence, removes cancelled/transparent events where appropriate, then sends normalized JSON to `scripts/plan_availability.py` through stdin.

```json
{
  "window_start": "2026-08-07T09:00:00+03:00",
  "window_end": "2026-08-07T18:00:00+03:00",
  "current_time": "2026-08-07T10:15:00+03:00",
  "duration_minutes": 60,
  "buffer_minutes": 15,
  "limit": 3,
  "busy": [
    {
      "start": "2026-08-07T12:00:00+03:00",
      "end": "2026-08-07T13:00:00+03:00"
    }
  ]
}
```

All timestamps must contain UTC offsets. `current_time` prevents past-slot suggestions. Script performs no API calls and writes no state. Returned slots use the timezone object/offset from `window_start`.
