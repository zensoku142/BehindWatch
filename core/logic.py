"""Tracking and alert rules, independent of the camera and UI."""
from dataclasses import dataclass, field
from math import hypot
from statistics import median
from core.face_identity import best_match, normalized, CONFIRM_FRAMES


def iou(a, b):
    x = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    y = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    intersection = x * y
    return intersection / max(1e-9, (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - intersection)


def appearance_similarity(a, b):
    return sum(min(x, y) for x, y in zip(a, b)) if a is not None and b is not None and len(a) == len(b) else 0


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
    motion: list = field(default_factory=list)
    moving: bool = False
    ignored: bool = False
    face_box: tuple | None = None
    face_seen: float = -1e9
    motion_source: str = ''


class Monitor:
    def __init__(self, presence=0.8, gaze=2.0, dwell=4.0, cooldown=10.0):
        self.tracks = {}
        self.next_id = 1
        self.owner = None
        self.ignored_ids = set()
        self.appearances = {}
        self.last_update = None
        self.features = {}
        self.selections = {}
        self.tracked_externally = False
        self.presence, self.gaze, self.dwell, self.cooldown = presence, gaze, dwell, cooldown

    def reset_tracking(self):
        # 摄像头关闭或长时间中断后不沿用位置；人工选择的会话特征保留，重新看清人脸后才恢复。
        self.tracks.clear()
        self.ignored_ids.clear()
        self.appearances.clear()
        self.features.clear()
        self.owner = None
        self.last_update = None
        for selection in self.selections.values():
            selection['count'] = 0

    def _remember_selection(self, key, identity):
        feature = self.features.get(identity)
        if feature is not None:
            self.selections[key] = {'feature': feature.copy(), 'id': identity, 'count': 0}

    def toggle_ignore(self, identity):
        if identity not in self.tracks or identity == self.owner:
            return False
        if identity in self.ignored_ids:
            self.ignored_ids.remove(identity)
            self.selections = {key: value for key, value in self.selections.items()
                               if key == 'owner' or value['id'] != identity}
        else:
            self.ignored_ids.add(identity)
            self._remember_selection(identity, identity)
        self.tracks[identity].ignored = identity in self.ignored_ids
        self.tracks[identity].motion.clear()
        self.tracks[identity].moving = False
        return True

    def calibrate(self, identity):
        if identity not in self.tracks:
            return False
        self.owner = identity
        self.selections = {key: value for key, value in self.selections.items()
                           if key != 'owner' and value['id'] != identity}
        self._remember_selection('owner', identity)
        self.ignored_ids.discard(identity)
        for track in self.tracks.values():
            track.sent.clear()
            track.facing_since = None
            track.first = track.seen
            track.motion.clear()
            track.moving = False
            track.ignored = track.id in self.ignored_ids
        return True

    def update(self, observations, now):
        # 单帧推理可能超过一秒，不能当成摄像头重启；长中断仍丢弃位置，避免把新来的人当成本人。
        if self.last_update is not None and now-self.last_update > 10.0:
            self.reset_tracking()
        self.last_update = now
        self.tracked_externally |= any('tracker_id' in obs for obs in observations)
        self.tracks = {k: t for k, t in self.tracks.items()
                       if now-t.seen < (3.0 if self.tracked_externally or k in self.ignored_ids or k == self.owner else 1.0)}
        self.ignored_ids.intersection_update(self.tracks)
        self.appearances = {k: value for k, value in self.appearances.items() if k in self.tracks}
        if self.owner not in self.tracks:
            self.owner = None
        matched, used = {}, set()
        if observations and all('tracker_id' in obs for obs in observations):
            # 生产检测链使用现成 ByteTrack 的编号，不再执行旧的框重叠/颜色贪心匹配。
            matched = {j: obs['tracker_id'] for j, obs in enumerate(observations)}
            for j, identity in matched.items():
                if identity not in self.tracks:
                    box = tuple(observations[j]['box'])
                    self.tracks[identity] = Track(identity, box, now, now, ((box[0]+box[2])/2, (box[1]+box[3])/2))
        else:
            # 保留不带跟踪编号的旧调用接口；摄像头路径统一由 ByteTrack 提供编号。
            # 人脸框与身体框交替出现时，先用最近的人脸位置关联；双向唯一才保留身份，避免交叉串人。
            face_pairs = [(k, j) for k, track in self.tracks.items()
                          for j, observation in enumerate(observations)
                          if track.face_box is not None and now-track.face_seen <= .4
                          and observation.get('face_box') is not None
                          and iou(track.face_box, observation['face_box']) >= .5
                          and (self.appearances.get(k) is None or observation.get('appearance') is None
                               or appearance_similarity(self.appearances[k], observation['appearance']) >= .55)]
            for identity, j in face_pairs:
                if sum(k == identity for k, _ in face_pairs) == 1 and sum(n == j for _, n in face_pairs) == 1:
                    matched[j] = identity
                    used.add(identity)
            # A temporary duplicate track can otherwise win IoU over the earlier ignored ID.
            for identity in self.ignored_ids | ({self.owner} if self.owner is not None else set()):
                if identity in used:
                    continue
                track = self.tracks[identity]
                old = self.appearances.get(identity)
                if old is None:
                    continue
                possible = []
                for j, observation in enumerate(observations):
                    if j in matched:
                        continue
                    current = observation.get('appearance')
                    if current is None:
                        continue
                    box = observation['box']
                    center = ((box[0]+box[2])/2, (box[1]+box[3])/2)
                    prior = ((track.box[0]+track.box[2])/2, (track.box[1]+track.box[3])/2)
                    width_ratio = (box[2]-box[0])/max(1e-9, track.box[2]-track.box[0])
                    similarity = appearance_similarity(old, current)
                    if hypot(center[0]-prior[0], center[1]-prior[1]) <= .08 and .6 <= width_ratio <= 1.7 and similarity >= .8:
                        possible.append((similarity + iou(track.box, box), j))
                possible.sort(reverse=True)
                if possible and (len(possible) == 1 or possible[0][0]-possible[1][0] >= .1):
                    j = possible[0][1]
                    if j not in matched:
                        matched[j] = identity
                        used.add(identity)
            candidates = []
            for k, track in self.tracks.items():
                for j, observation in enumerate(observations):
                    score = iou(track.box, observation['box'])
                    if score < .25:
                        continue
                    if k in self.ignored_ids or k == self.owner:
                        old, current = self.appearances.get(k), observation.get('appearance')
                        minimum = .7 if now-track.seen > .4 else .55
                        if old is not None and current is not None and appearance_similarity(old, current) < minimum:
                            continue
                        if now-track.seen > .4 and (old is None or current is None):
                            continue
                    candidates.append((score + (.2 if k in self.ignored_ids else 0), score, k, j))
            candidates.sort(reverse=True)
            for _, score, identity, j in candidates:
                if identity not in used and j not in matched:
                    # Ambiguous crossings invalidate owner calibration instead of silently swapping people.
                    rivals = [iou(t.box, observations[j]['box']) for k, t in self.tracks.items() if k != identity]
                    if identity == self.owner and rivals and max(rivals) > score-0.12:
                        self.owner = None
                    if identity in self.ignored_ids and rivals and max(rivals) > score-0.12:
                        # After a close crossing, this track might now be a different person.
                        self.ignored_ids.discard(identity)
                    matched[j] = identity
                    used.add(identity)
            # Rejoin a missed ignored track only when both its place and color signature agree.
            for j, observation in enumerate(observations):
                if j in matched or 'appearance' not in observation:
                    continue
                possible = []
                for identity in self.ignored_ids - used:
                    track = self.tracks[identity]
                    old = self.appearances.get(identity)
                    if old is None or now-track.seen > 3.0:
                        continue
                    box = observation['box']
                    center = ((box[0]+box[2])/2, (box[1]+box[3])/2)
                    prior = ((track.box[0]+track.box[2])/2, (track.box[1]+track.box[3])/2)
                    width_ratio = (box[2]-box[0])/max(1e-9, track.box[2]-track.box[0])
                    similarity = appearance_similarity(old, observation['appearance'])
                    if hypot(center[0]-prior[0], center[1]-prior[1]) <= .1 and .5 <= width_ratio <= 2 and similarity >= .7:
                        possible.append((similarity + iou(track.box, box), identity))
                possible.sort(reverse=True)
                if possible and (len(possible) == 1 or possible[0][0]-possible[1][0] >= .1):
                    identity = possible[0][1]
                    matched[j] = identity
                    used.add(identity)
        visible, events = [], []
        self.features = {}
        for j, obs in enumerate(observations):
            identity = matched.get(j)
            if identity is None:
                identity = self.next_id
                self.next_id += 1
                box = tuple(obs['box'])
                self.tracks[identity] = Track(identity, box, now, now, ((box[0]+box[2])/2, (box[1]+box[3])/2))
            track = self.tracks[identity]
            feature = normalized(obs['feature']) if 'feature' in obs else None
            if feature is not None:
                self.features[identity] = feature
            if now-track.seen > 1.5:
                track.first = now
                track.facing_since = None
                track.motion.clear()
            old_box = track.box
            track.box, track.seen = tuple(obs['box']), now
            if 'appearance' in obs:
                previous = self.appearances.get(identity)
                current = obs['appearance']
                self.appearances[identity] = (tuple(.8*a + .2*b for a, b in zip(previous, current))
                                              if previous is not None else tuple(current))
            track.facing = bool(obs.get('facing', False))
            track.facing_since = (track.facing_since if track.facing_since is not None else now) if track.facing else None
            face_box = obs.get('face_box')
            # ByteTrack 的身体轨迹不依赖正脸，避免路人转头时坐标来源反复切换、位移历史被清空。
            use_face = face_box is not None and ('tracker_id' not in obs or obs.get('face_only', False))
            source = 'face' if use_face else 'body'
            anchor = face_box if use_face else track.box
            if face_box is not None:
                track.face_box, track.face_seen = tuple(face_box), now
            # 人脸补充目标与身体目标的中心不同；坐标来源切换或框剧烈变形不能累计成走动。
            if source != track.motion_source:
                track.motion.clear()
            elif source == 'body':
                ratios = [(track.box[end]-track.box[start])/max(1e-9, old_box[end]-old_box[start])
                          for start, end in ((0, 2), (1, 3))]
                if any(not .5 <= ratio <= 2 for ratio in ratios):
                    track.motion.clear()
            track.motion_source = source
            # 身体框上半部会随坐姿、遮挡改变；底部位置及两侧边界更能区分整个人平移与框形变。
            point = ((anchor[0]+anchor[2])/2, (anchor[1]+anchor[3])/2 if use_face else anchor[3])
            track.motion = [(at, sample) for at, sample in track.motion if now-at <= 1.8]
            track.motion.append((now, (point, anchor)))
            track.moving = False
            if len(track.motion) >= 3 and now-track.motion[0][0] >= 1.0:
                # 三个时间段取中位数，要求两段同向移动；单次框跳变、探身后停住及来回摇晃不算经过。
                span = now-track.motion[0][0]
                groups = [[], [], []]
                for at, sample in track.motion:
                    groups[min(2, int(3*(at-track.motion[0][0])/span))].append(sample)
                if all(groups):
                    points = [(median(sample[0][0] for sample in group), median(sample[0][1] for sample in group))
                              for group in groups]
                    boxes = [tuple(median(sample[1][side] for sample in group) for side in range(4))
                             for group in groups]
                    steps = [(b[0]-a[0], b[1]-a[1]) for a, b in zip(points, points[1:])]
                    lengths = [hypot(*step) for step in steps]
                    # 按目标自身大小适应远近；固定的整幅画面 6% 门槛会吞掉远处通道中的真实走动。
                    threshold = max(.0125, (.9 if source == 'face' else .4)*(anchor[2]-anchor[0]))
                    edge_motion = True
                    if source == 'body':
                        dx = points[2][0]-points[0][0]
                        dy = points[2][1]-points[0][1]
                        # 一侧边界固定而另一侧漂移通常是坐姿或检测框形变，不应算作经过。
                        if abs(dx) >= threshold*.7:
                            edge_motion = min((boxes[2][side]-boxes[0][side])*dx for side in (0, 2)) >= .35*dx*dx
                        else:
                            edge_motion = (abs(dy) >= threshold and
                                           (boxes[2][1]-boxes[0][1])*dy >= .35*dy*dy and
                                           (boxes[2][3]-boxes[0][3])*dy >= .35*dy*dy)
                    track.moving = (hypot(points[2][0]-points[0][0], points[2][1]-points[0][1]) >= threshold
                                    and min(lengths) >= threshold*.25
                                    and sum(a*b for a, b in zip(*steps)) >= .8*lengths[0]*lengths[1]
                                    and edge_motion)
            track.ignored = identity in self.ignored_ids
            if track.ignored:
                track.moving = False
            visible.append(track)
        # 选择不再只依赖易失的轨迹编号；连续多帧、双向唯一的人脸匹配才恢复，不能仅凭同一座位恢复。
        matches = {key: best_match(value['feature'], self.features) for key, value in self.selections.items()}
        for key, selection in self.selections.items():
            identity = matches[key]
            if identity is not None and list(matches.values()).count(identity) != 1:
                identity = None
            old_id = selection['id']
            if old_id in self.features and best_match(selection['feature'], {old_id: self.features[old_id]}) is None:
                if key == 'owner' and self.owner == old_id:
                    self.owner = None
                elif key != 'owner':
                    self.ignored_ids.discard(old_id)
            # 检测编号本身可能每帧重建；连续确认应针对同一份选择特征，不能再依赖编号不变。
            selection['count'] = selection['count'] + 1 if identity is not None else 0
            if identity is None or selection['count'] < CONFIRM_FRAMES:
                continue
            if key == 'owner':
                self.owner = identity
            elif identity != self.owner:
                self.ignored_ids.discard(old_id)
                self.ignored_ids.add(identity)
            selection['id'] = identity
        for track in visible:
            identity = track.id
            track.ignored = identity in self.ignored_ids and identity != self.owner
            if track.ignored:
                track.moving = False
            if self.owner is None or identity == self.owner or track.ignored or not track.moving:
                continue
            if now-track.sent.get('walking', -1e9) >= self.cooldown:
                track.sent['walking'] = now
                events.append({'id': identity, 'message': '检测到人员走动'})
        for identity, track in self.tracks.items():
            if identity not in {t.id for t in visible}:
                track.facing_since = None
                # 短暂漏检只停止当前触发，保留历史供 ByteTrack 恢复后继续累计。
                track.moving = False
        return visible, events
