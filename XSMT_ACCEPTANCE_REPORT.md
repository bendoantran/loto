# XSMT acceptance report

Recorded UTC: 2026-10-22T15:04:03+00:00. Target: Ubuntu 26.04.1 LTS with KDE/Wayland, Python 3.12.9, kernel 7.0.0-38-generic.

## Outcome and boundary

Production XSMT support is implemented locally and passed its live pilot, live year-boundary grader, 36 offline tests, and separate child-process recovery checks. The original XSMN archive passed the full audit again after the changes. The independently checkpointed full XSMT history is **running, not finished**.

Repository visibility was rechecked as **private** through the connected GitHub account. Base commit: `a64c1b718dba16d084de1e571b9693b2a3e8e94c`. Changes are uncommitted; exact tested Python-file SHA-256 hashes are in `xsmt-acceptance.json`. No prediction code, model training, public hosting, or repository upload was performed.

## Project inspection

Read all repository instructions, both scraping handoffs, the XSMT challenge, prediction handoff/plan, source modules, controls, restore/verifier/monitor/service tools, shell and PowerShell wrappers, CI configuration and regression tests. Inspected structured manifests and reference schemas. The frozen-file check and full baseline verifier read every original HTML response and compare the saved database and all yearly numeric exports; this is programmatic archive inspection, not a claim of manually reading 600 MB of HTML line by line. See `PROJECT_REVIEW.md` for the detailed map.

## Preserved XSMN baseline

- Fixed range: 2007-08-18–2026-10-21; 7,005 dates, 21,592 province/date draws, 388,656 number appearances.
- 6,775 saved; 95 flagged; 133 explicit no-draw; 2 review; 0 unavailable.
- The two original review gaps (2008-09-02 and 2011-02-03) remain preserved.
- All frozen assets and original HTML hashes passed verification. Existing checkpoint preserved on repeat restore.
- Completed start reported “nothing needs downloading”; the migrated completion monitor stayed quiet.
- XSMT commands reject the legacy XSMN checkpoint and the reverse mismatch before database writes or downloads.

## Live source evidence

The exact requested [XSMT regional page](https://xosodaiphat.com/xsmt-xo-so-mien-trung.html) was fetched at 2026-10-22T14:56:02+00:00, raw SHA-256 `35573e22f082726fb9abd52ad4d90c05834802c232998b6756d4a868bc5b00af`. Its actual response was saved before parsing in `source.html`; extraction is in `results.json` and `prizes.csv`: **7 dates, 17 draws, 306 number appearances**. All dates were clean.

The separate real daily-page pilot checked 2026-10-16–2026-10-22: **7 dates, 17 draws, 306 values**, exact independent grader passed. The separate real year-boundary run checked 2025-12-31 and 2026-01-01: **2 dates, 5 draws, 90 values**, exact grader passed and actual yearly folders were verified. All nine dates required exactly one successful request. Live HTML bytes may differ from frozen reference bytes; the graders compare published number/loto strings and independently validate each live raw hash.

| Date | Status | Draws | Numbers | Attempts | Fetched UTC | Raw SHA-256 |
|---|---|---:|---:|---:|---|---|
| 2026-10-16 | saved | 2 | 36 | 1 | 2026-10-22T14:57:15+00:00 | `9c0a467cd8cc98439280f7e7134d8488ce640080621b086878488ce4401613ff` |
| 2026-10-17 | saved | 3 | 54 | 1 | 2026-10-22T14:57:17+00:00 | `8b5f3b15b5cf2d02ccd11a3b3e03b7a0862f16ccd0659fe11bad76e2f061932b` |
| 2026-10-18 | saved | 3 | 54 | 1 | 2026-10-22T14:57:19+00:00 | `74396b21ec83b163dd15d5670d657d3f1587b7a73de5991fe4df792929bad013` |
| 2026-10-19 | saved | 2 | 36 | 1 | 2026-10-22T14:57:21+00:00 | `f4371d718def1caee9bdde6c5c30740dab2380de5da68302fcaa91f25acbb7d0` |
| 2026-10-20 | saved | 2 | 36 | 1 | 2026-10-22T14:57:24+00:00 | `03ac637747079ea534454a30f92bdf8ce1c416c3d5d3b0cbd1aeb14331544b39` |
| 2026-10-21 | saved | 2 | 36 | 1 | 2026-10-22T14:57:26+00:00 | `ce6dd9b3d9a8b2a16c71a64905c2cbbec111ce443ff7c8913cf89a45bf32f581` |
| 2026-10-22 | saved | 3 | 54 | 1 | 2026-10-22T14:57:28+00:00 | `b6225ecabef06a969d4b5e92fff192d5ad926dba51be1d446cd9ef05637635b0` |
| 2025-12-31 | saved | 2 | 36 | 1 | 2026-10-22T14:57:48+00:00 | `53eeacb3089ca281a15e55ea7f31d025b8f17189e74aef30c79f9ef0fc5283e7` |
| 2026-01-01 | saved | 3 | 54 | 1 | 2026-10-22T14:57:51+00:00 | `51dafb21ee04463d51444a7c541902d78c45c90efbb09e68a4d13759400267f8` |

Source number strings, province order, leading zeros and repetitions are retained. Specific reference checks include Khánh Hòa G.ĐB `044743`, Khánh Hòa G.8 `09`, Bình Định G.6 `0144` and `0774`, and two occurrences of `04` in the specified Khánh Hòa loto table.

## Recovery and negative cases

`tools/prove_xsmt_recovery.py` used frozen HTML with an injected transport, not live requests. Separate child processes actually exited with codes 71 (after raw save) and 72 (after commit, before export). Evidence is in `recovery.json` and the retained scratch roots.

- Stop after two committed dates, restart twice: total requests remained exactly one per date; earlier raw hashes unchanged.
- Crash after raw save: pending checkpoint survived; restart reused the raw cache; total requests = 1.
- Crash after the final 2025 commit: 2025 export was reconstructed before the first 2026 request; no duplicate download.
- Two injected connection failures then success: attempts = 3, simulated waits 5 then 10 seconds, no fabricated completed progress.
- Further offline tests verify 5/10/20/40/60 backoff and a 60-second minimum for HTTP 429.
- A second real Linux process was refused while the first held flock.
- STOP survived a separate process restart; the monitor made zero restart calls and issued no requests.
- Wrong region both ways, wrong date, captcha/partial/empty content, missing/duplicate prize tiers, altered widths, province order, sidebar loto, synthetic XSMT cancellation/not-archived notices, wrong checkpoint range and wrong export region are tested.

No physical reboot, real power failure or Wi-Fi disconnection was performed. Tests mocked the retry clock for deterministic execution; production remains one request at a time, timeout 20 seconds, 1.5-second pacing, WAL/FULL commits per date and raw save before parsing.

## Independent historical discovery

Coarse XSMT probes: 2000-01-01, 2005-01-01, 2007-01-01 and 2007-08-01 were explicitly not archived; 2007-09-01 contained validated results. Refinement found 2007-08-09/13/15/16/17 explicitly not archived, and 2007-08-18/19/20 valid. Therefore **2007-08-18 is the earliest independently verified available XSMT date in this investigation**. This agrees with the XSMN start only after checking the XSMT source; it was not inherited as a fact.

Earlier dates were sampled, not exhaustively searched; isolated older available results cannot be ruled out. All discovery responses, timestamps and hashes are retained. The frozen full XSMT range is **2007-08-18–2026-10-22**, 7,006 days. Thirteen already-live daily responses were reused as raw cache inputs with their hashes/mtimes intact.

At this report snapshot: **105/7,006 dates**, latest date **2007-11-30**, state `running`. A consistent read-only partial audit checked 60 committed raw hashes and checkpoint integrity. This does not replace the required final full audit once collection finishes.

## Services, display and controls

The separate XSMT root is `/home/ldoan4/Documents/Codex/2026-10-22/git/work/xsmt`. Its `PROGRESS.md`/`progress.json` retain the canonical table, state names and UTC timestamps. Captured tables accompany the evidence ZIP. XSMN display files were not replaced.

Installed and enabled under `/home/ldoan4/.config/systemd/user/`: `loto-xsmt-history.service`, `loto-xsmt-monitor.service`, `loto-xsmt-monitor.timer`. Actual `systemd-analyze --user verify` passed (exit 0). It emitted one unrelated existing `spice-vdagent.service` warning. The real validator exposed an inherited quoted WorkingDirectory bug; the generator was corrected and the resulting units successfully started.

Collector state is active/running. Timer state is active/waiting, checking every 30 minutes. The first real monitor run completed quietly; the pilot monitor reported completion once, then stayed quiet. See `XSMT_RUNBOOK.md` for status, view, durable stop, explicit resume, export and verification commands.

`Linger=no`: user-session login resume is enabled, but pre-login and after-logout operation was not enabled. Keep the machine awake. Desktop popup delivery was not verified; journal/event-file reporting is available. No chat automation was created.

```
Id=loto-xsmt-history.service
ActiveState=active
SubState=running
MainPID=32767

Id=loto-xsmt-monitor.timer
ActiveState=active
SubState=waiting
NEXT                         LEFT LAST                              PASSED UNIT                    ACTIVATES
Thu 2026-10-22 11:30:16 EDT 26min Thu 2026-10-22 11:00:16 EDT 3min 46s ago loto-xsmt-monitor.timer loto-xsmt-monitor.service

1 timers listed.
Linger=no
```

## Provisional evidence score

| Area | Evidence-backed self-score |
|---|---:|
| Region isolation/source handling | 20/20 |
| Numeric/loto accuracy | 25/25 |
| Interruption/recovery | 25/25 |
| Year organization | 10/10 |
| Existing display/quiet monitor | 10/10 |
| Target reproducibility | 8/10 |
| Total | **98/100 provisional** |

This is a self-assessment, not an independent grade. Two reproducibility points are withheld because physical reboot and desktop popup delivery were not tested. Full-history completion is separately unfinished and is not claimed by this implementation score.
