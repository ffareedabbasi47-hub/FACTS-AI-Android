# FACTS AI — Safe Upload Reconciliation & Manual Recovery Guide

This document outlines the upload lifecycle, state machine, interruption handling, and operator procedures for recovering ambiguous or failed YouTube upload operations in FACTS AI.

---

## 1. Upload Operation Lifecycle & State Machine

Every upload operation follows a deterministic four-state model persisted in `used_topics.txt`:

```
[PENDING] (Initiated before network call)
    │
    ├── Upload Succeeded ──────────► [CONFIRMED] (Video live with Video ID)
    │
    └── Network Error / Interruption ─┐
                                      ▼
                        Automated Reconciliation on Next Run
                                      │
              ┌───────────────────────┴───────────────────────┐
              ▼                                               ▼
      Found on Channel                                Not Found on Channel
              │                                               │
              ▼                                               ▼
        [CONFIRMED]                                  [REVIEW_REQUIRED]
                                                              │
                                      ┌───────────────────────┴───────────────────────┐
                                      ▼                                               ▼
                              Operator Confirms                               Operator Confirms
                              Video Exists on YouTube                         Upload Did Not Happen
                                      │                                               │
                                      ▼                                               ▼
                                 [CONFIRMED]                                       [FAILED]
```

### State Definitions

| State | Format in `used_topics.txt` | Meaning & Behavior |
|---|---|---|
| **`[PENDING]`** | `[PENDING] op_id=... \| topic=... \| title=... \| <timestamp>` | An upload operation has been persisted prior to issuing the YouTube API upload request. If the pipeline crashes, this record blocks any new video creation until reconciled. |
| **`[CONFIRMED]`** | `[CONFIRMED] topic=... \| https://youtu.be/<vid> \| op_id=...` (or legacy `topic \| url \| op_id`) | Video was successfully confirmed on the authenticated channel. The topic is marked completed and deduplicated against future runs. |
| **`[REVIEW_REQUIRED]`** | `[REVIEW_REQUIRED] op_id=... \| topic=... \| reason=... \| <timestamp>` | An ambiguous upload could not be verified on the YouTube channel during automated reconciliation. Pipeline halts safely and refuses to generate duplicate videos until human review. |
| **`[FAILED]`** | `[FAILED] op_id=... \| reason=... \| <timestamp>` | An operation was verified by an operator to have permanently failed without publishing a video. The pipeline lock is released. |

---

## 2. Upload Interruption Audit

| Failure Point | System State | What Actually Happened | Recovery Procedure |
|---|---|---|---|
| **Crash before upload initiation** (e.g. video rendering fails, auth failure) | No `[PENDING]` record | No bytes sent to YouTube. | Automatic retry on next run. |
| **Crash before Chunk 0 completes** | `[PENDING]` record exists | Resumable upload session was not finalized; YouTube does not have the video. | On next run, reconciliation searches channel, finds nothing, and flags `[REVIEW_REQUIRED]`. Operator verifies YouTube Studio and marks `[FAILED]`. |
| **Crash during intermediate chunks** (e.g. chunk 3 of 10) | `[PENDING]` record exists | Incomplete video session on YouTube servers; not published or indexed. | Automatic reconciliation checks channel's uploads playlist and search. Video will not be found; transitions to `[REVIEW_REQUIRED]`. Operator verifies and marks `[FAILED]`. |
| **Crash after final chunk, before response received** | `[PENDING]` record exists | Video IS uploaded and processed on YouTube, but client dropped before getting Video ID. | On next run, automated reconciliation queries `playlistItems().list` on the channel's uploads playlist, matches `[Operation ID: <op_id>]` in the description, retrieves the Video ID, and marks `[CONFIRMED]`. |
| **Search Indexing Delay** | `[PENDING]` record exists | Video exists but YouTube Search API has not indexed it yet. | `playlistItems().list` queries the uploads playlist directly, which is immune to search indexing latency. |

---

## 3. Safe Manual Recovery Procedures

When the pipeline halts with `AMBIGUOUS UPLOAD BLOCKED` or an operation is in `[REVIEW_REQUIRED]`:

### Step 1: Inspect Unresolved Operations
Check `used_topics.txt` for `[PENDING]` or `[REVIEW_REQUIRED]` lines:
```bash
grep -E "\[PENDING\]|\[REVIEW_REQUIRED\]" used_topics.txt
```

### Step 2: Run Manual Reconciliation
To re-query YouTube with channel authentication across the uploads playlist and search:
```bash
python main.py --reconcile-pending
```
If the video is found on YouTube, the system automatically marks it `[CONFIRMED]`, prints the Video ID, and resolves the lock.

### Step 3: If Video Does NOT Exist on YouTube
If you have verified in [YouTube Studio](https://studio.youtube.com/) that no video with the operation marker exists:
```bash
python main.py --mark-failed <OP_ID>
```
*Example:*
```bash
python main.py --mark-failed FACTS-AI-OP-20261113-pl1234
```
This updates the status to `[FAILED]`, releasing the pipeline lock so automated scheduled runs can resume safely.

### Step 4: If Video WAS Uploaded but Missed by Automated Queries
If you locate the video manually in YouTube Studio:
```bash
python main.py --mark-confirmed <OP_ID> <VIDEO_ID>
```
*Example:*
```bash
python main.py --mark-confirmed FACTS-AI-OP-20261113-pl1234 dQw4w9WgXcQ
```
This updates the status to `[CONFIRMED]`, associates the Video URL, and records deduplication.

---

## 4. Duplicate Prevention Guarantees

1. **No Silent Duplicate Videos**: As long as an unresolved `[PENDING]` or `[REVIEW_REQUIRED]` record exists in `used_topics.txt`, `AutomationPipeline.run_pipeline()` will refuse to proceed to topic selection or video rendering.
2. **Channel Identity Gate**: Reconciliation requires matching the authenticated channel ID (`channels().list(mine=True)`). A rogue or foreign video sharing an operation marker cannot hijack confirmation.
3. **No Title-Only Confirmation**: Legacy title matching is disabled. Confirmation requires the exact `[Operation ID: <uuid>]` marker in the description.
