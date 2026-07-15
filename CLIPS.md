# Detection Clips (Issue 10, Task 2)

## How clips are triggered and stored

When a detection is logged (currently via the `/detections/demo` route, the only
place detections get created today), `app/routes.py` looks up the camera's
`stream_url` by matching `camera_name` against the `cameras` table, then calls
`capture_detection_clip()` in `app/clips.py`. That function reuses the same
`cv2.VideoCapture` pattern as the existing live-view (`gen_frames` /
`is_camera_online` in `app/routes.py`), opens the stream, and writes frames to
an `.mp4` file via `cv2.VideoWriter` at `app/static/clips/detection_<id>_<utc
timestamp>.mp4`. The path (relative to `static/`, e.g. `clips/detection_5_...mp4`)
is saved to the new `detections.clip_path` column and linked from the
dashboard's detection log ("View clip").

**Limitation — no true pre-roll yet.** There's no continuously-running frame
buffer anywhere in the app today (frames are only pulled on demand, e.g. when a
browser is actively viewing `/video_feed/<id>`). So `capture_detection_clip()`
can only capture frames from the moment it's called *onward* — it records
`CLIP_PRE_SECONDS + CLIP_POST_SECONDS` (default 3 + 3 = 6s total) starting at
the trigger, not frames from before the trigger. Getting real pre-roll would
require a background thread per camera continuously feeding a ring buffer —
that's future work, and holding a second persistent connection to the same
RTSP stream also risks conflicting with the live-view feature, which is why
it wasn't done here.

If a detection's `camera_name` doesn't match a registered camera, or the
stream can't be opened, clip capture is skipped silently (`clip_path` stays
empty) — same fail-safe pattern as the Issue 9 email alert: wrapped in
try/except so a broken camera or missing OpenCV codec never blocks detection
logging.

## Configuration (env vars, same `.env` as notifications)

| Var | Default | Meaning |
|---|---|---|
| `CLIP_PRE_SECONDS` | `3` | Seconds of "before" footage (see limitation above — currently counted from trigger, not truly before it) |
| `CLIP_POST_SECONDS` | `3` | Seconds of "after" footage |
| `CLIP_FALLBACK_FPS` | `15` | Used if the camera doesn't report a usable FPS |
| `CLIP_RETENTION_DAYS` | `30` | Default retention period for cleanup |

## Retention / cleanup

Run `flask --app run cleanup-clips` to delete clip files older than the
retention period (default 30 days, override with `--days N`) and clear
`clip_path` on any detection rows whose file is gone. Run this on a schedule
(cron, launchd, etc.) in a real deployment — nothing currently runs it
automatically.

## Privacy considerations

- Clips are identifiable footage of real people — treat them as sensitive
  personal data, same tier as the enrollment face images already in
  `instance/uploads`.
- `app/static/clips/` is gitignored (`app/static/clips/` in `.gitignore`) —
  **never commit real clips to the repo**, including in screenshots or test
  fixtures attached to issues/PRs.
- Retention exists specifically to limit how long identifiable footage sits
  on disk; don't raise `CLIP_RETENTION_DAYS` without a reason, and don't
  disable cleanup in a real deployment.
- As with the email alerts (see `NOTIFICATIONS.md`), consider whether the
  *detected* person needs notice or consent that a clip of them is being
  recorded and retained, separate from whoever receives the alert.
