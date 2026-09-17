"""YOLO26s ONNX and Supervision ByteTrack adapters."""
import cv2
import numpy as np
import onnxruntime as ort
import supervision as sv


class PersonDetector:
    def __init__(self, model):
        # OpenCV DNN 会错误执行 YOLO26s 端到端输出的 TopK，真实画面产生重复框甚至直接报错。
        self.model = ort.InferenceSession(str(model), providers=['CPUExecutionProvider'])
        self.input_name = self.model.get_inputs()[0].name

    def detect(self, frame):
        h, w = frame.shape[:2]
        scale = min(640/w, 640/h)
        # 与官方 demo 相同的右下补边和 RGB 输入；还原坐标后才能与原画面的人脸、点击位置对齐。
        padded = np.full((640, 640, 3), 114, dtype=np.uint8)
        resized = cv2.resize(frame, (round(w*scale), round(h*scale)))
        padded[:resized.shape[0], :resized.shape[1]] = resized
        blob = cv2.dnn.blobFromImage(padded, scalefactor=1/255,
                                     size=(640, 640), swapRB=True)
        # 官方 NMS-free ONNX 输出为 xyxy、置信度、类别；保留低分人框供 ByteTrack 延续轨迹。
        results = self.model.run(None, {self.input_name: blob})[0].reshape(-1, 6)
        observations = []
        for x1, y1, x2, y2, score, category in results:
            if int(category) != 0 or score < .1:
                continue
            box = (max(0., x1/scale/w), max(0., y1/scale/h),
                   min(1., x2/scale/w), min(1., y2/scale/h))
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
