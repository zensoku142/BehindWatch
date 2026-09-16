"""Tracking and alert rules, independent of the camera and UI."""
from dataclasses import dataclass, field
from math import hypot


def iou(a, b):
    x = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    y = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    intersection = x * y
    return intersection / max(1e-9, (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - intersection)


@dataclass
class Track:
    id: int
    box: tuple
    first: float
    seen: float
    origin: tuple
    facing_since: float | None = None
    facing: bool = False
    sent: dict = field(default_factory=dict)


class Monitor:
    def __init__(self, presence=0.8, gaze=2.0, dwell=4.0, cooldown=10.0):
        self.tracks = {}
        self.next_id = 1
        self.owner = None
        self.presence, self.gaze, self.dwell, self.cooldown = presence, gaze, dwell, cooldown

    def calibrate(self, identity):
        if identity not in self.tracks:
            return False
        self.owner = identity
        for track in self.tracks.values():
            track.sent.clear()
            track.facing_since = None
            track.first = track.seen
        return True

    def update(self, observations, now):
        # Never carry identities or attention duration across a long capture/sleep gap.
        self.tracks = {k: t for k, t in self.tracks.items() if now-t.seen < 1.0}
        if self.owner not in self.tracks:
            self.owner = None
        candidates = sorted(((iou(t.box, o['box']), k, j)
                             for k, t in self.tracks.items()
                             for j, o in enumerate(observations)), reverse=True)
        matched, used = {}, set()
        for score, identity, j in candidates:
            if score < 0.25:
                break
            if identity not in used and j not in matched:
                # Ambiguous crossings invalidate owner calibration instead of silently swapping people.
                rivals = [iou(t.box, observations[j]['box']) for k, t in self.tracks.items() if k != identity]
                if identity == self.owner and rivals and max(rivals) > score-0.12:
                    self.owner = None
                matched[j] = identity
                used.add(identity)
        visible, events = [], []
        for j, obs in enumerate(observations):
            identity = matched.get(j)
            if identity is None:
                identity = self.next_id
                self.next_id += 1
                box = tuple(obs['box'])
                self.tracks[identity] = Track(identity, box, now, now, ((box[0]+box[2])/2, (box[1]+box[3])/2))
            track = self.tracks[identity]
            if now-track.seen > 0.4:
                track.first = now
                track.facing_since = None
            track.box, track.seen = tuple(obs['box']), now
            track.facing = bool(obs.get('facing', False))
            track.facing_since = (track.facing_since if track.facing_since is not None else now) if track.facing else None
            visible.append(track)
            if self.owner is None or identity == self.owner:
                continue
            center = ((track.box[0]+track.box[2])/2, (track.box[1]+track.box[3])/2)
            moving = hypot(center[0]-track.origin[0], center[1]-track.origin[1]) > 0.06
            kind = None
            if track.facing_since is not None and now-track.facing_since >= self.gaze:
                kind = '有人可能看向屏幕'
            elif now-track.first >= self.dwell:
                kind = '身后有人停留'
            elif now-track.first >= self.presence:
                kind = '身后有人活动' if moving else '检测到其他人员'
            if kind and now-track.sent.get(kind, -1e9) >= self.cooldown:
                # Higher severity may alert immediately; lower severity must not flood after it.
                rank = {'检测到其他人员': 1, '身后有人活动': 1, '身后有人停留': 2, '有人可能看向屏幕': 3}
                recent = [v for k, v in track.sent.items() if rank[k] >= rank[kind]]
                if not recent or now-max(recent) >= self.cooldown:
                    track.sent[kind] = now
                    events.append({'id': identity, 'message': kind})
        for identity, track in self.tracks.items():
            if identity not in {t.id for t in visible}:
                track.facing_since = None
        return visible, events
