"""OpenCV Zoo YOLOX and Supervision ByteTrack adapters."""
import cv2
import numpy as np
import supervision as sv

from core.vendor.yolox import YoloX


class PersonDetector:
    def __init__(self, model):
        self.model = YoloX(str(model), confThreshold=.1, nmsThreshold=.45)

    def detect(self, frame):
        h, w = frame.shape[:2]
        scale = min(640/w, 640/h)
        # 与官方 demo 相同的右下补边和 RGB 输入；还原坐标后才能与原画面的人脸、点击位置对齐。
        padded = np.full((640, 640, 3), 114, dtype=np.uint8)
        resized = cv2.resize(frame, (round(w*scale), round(h*scale)))
        padded[:resized.shape[0], :resized.shape[1]] = resized
        results = self.model.infer(cv2.cvtColor(padded, cv2.COLOR_BGR2RGB).astype(np.float32))
        observations = []
        for x, y, width, height, score, category in results:
            if int(category) != 0:
                continue
            box = (max(0., x/scale/w), max(0., y/scale/h),
                   min(1., (x+width)/scale/w), min(1., (y+height)/scale/h))
            if box[2] > box[0] and box[3] > box[1]:
                observations.append({'box': box, 'confidence': float(score), 'facing': False})
        return observations


class PersonTracker:
    def __init__(self):
        # 低分框用于延续遮挡中的目标，不能独立创建新目标；保持三秒左右的失配缓冲。
        self.tracker = sv.ByteTrack(track_activation_threshold=.25, lost_track_buffer=90,
                                    frame_rate=8, minimum_consecutive_frames=1)

    def update(self, observations):
        detections = sv.Detections(
            xyxy=np.asarray([o['box'] for o in observations], dtype=np.float32).reshape(-1, 4)*640,
            confidence=np.asarray([o.get('confidence', .5) for o in observations], dtype=np.float32),
            class_id=np.zeros(len(observations), dtype=int),
            data={'index': np.arange(len(observations))})
        tracked = self.tracker.update_with_detections(detections)
        if not len(tracked):
            return []
        return [{**observations[int(index)], 'tracker_id': int(identity)}
                for index, identity in zip(tracked.data['index'], tracked.tracker_id)]
