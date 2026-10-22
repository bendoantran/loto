# loto agent requirements

Read `KUBUNTU_AGENT_HANDOFF.md` before changing or installing this project. The owner requested the same scraping requirements, method, progress display, and resumability on Kubuntu as the original Windows run.

- Preserve the fixed range 2007-08-18 through 2026-10-21. Do not silently extend it or clear checkpoints.
- Migration means restore the bundled database and verify the completed archive; do not rescrape 19 years.
- Keep the GitHub repository private. Never publish credentials or enable public hosting.
- Keep the one-request-at-a-time collector, timeout, pacing, retries, date order, data schemas, quality states, leading zeros, repeated appearances, and raw-source preservation unchanged.
- `PROGRESS.md` and `progress.json` are the canonical existing display. Do not substitute a dashboard or redesign.
- Respect STOP and intentional stopped states. Never run two collectors against one data root. Do not repair an active SQLite database by deleting files.
- Preserve original HTML and published numbers; flag inconsistencies instead of guessing or silently correcting.
- Use Python standard library only. Run the offline tests after meaningful changes. Run the full verifier before claiming migration acceptance.
- If this Kubuntu environment lacks browser authentication, sudo permission, systemd user-session access, or a Linux facility, state that precise blocker; complete independent work first.
- Do not claim real Kubuntu acceptance until commands have actually run on the target computer.
- The original Windows source is `C:\Users\bendo\Documents\xoso`. Its existing workflow is historical context; use resolved Linux paths here.

Do not create subagents unless the owner asks for them.
