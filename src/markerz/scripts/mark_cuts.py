#!/usr/bin/env python3
"""Add a marker at every cut point on the current DaVinci Resolve timeline."""

import sys

resolve = bmd.scriptapp("Resolve")  # noqa: F821 - injected by Resolve
if not resolve:
    print("Could not connect to DaVinci Resolve.")
    sys.exit(1)

project = resolve.GetProjectManager().GetCurrentProject()
timeline = project.GetCurrentTimeline()

if not timeline:
    print("No timeline is currently open.")
    sys.exit(1)

track_count = timeline.GetTrackCount("video")
cut_frames = set()

for track in range(1, track_count + 1):
    clips = timeline.GetItemListInTrack("video", track)
    if not clips:
        continue
    for clip in clips:
        start = clip.GetStart()
        end = clip.GetEnd()
        cut_frames.add(start)
        cut_frames.add(end)

# Remove the very first and very last frame of the timeline (not real cuts)
tl_start = timeline.GetStartFrame()
tl_end = timeline.GetEndFrame()
cut_frames.discard(tl_start)
cut_frames.discard(tl_end)

existing = timeline.GetMarkers()  # dict keyed by frame offset from tl_start

added = 0
for frame in sorted(cut_frames):
    offset = frame - tl_start
    if offset in existing:
        continue
    timeline.AddMarker(offset, "Blue", "Cut", "", 1)
    added += 1

print(f"Done - added {added} markers across {track_count} video track(s).")
