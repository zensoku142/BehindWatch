"""Local MediaPipe inference. No image upload or recording."""
from pathlib import Path
import math
import time
import queue
from dataclasses import asdict
from logic import Monitor

ROOT = Path(__file__).resolve().parent


class Detector:
    def __init__(self):
        from download_models import verify
        verify()
        import mediapipe as mp
        self.mp = mp
        base, vision = mp.tasks.BaseOptions, mp.tasks.vision
        self.people = vision.ObjectDetector.create_from_options(vision.ObjectDetectorOptions(
            base_options=base(model_asset_path=str(ROOT/'models/person.tflite')),
            running_mode=vision.RunningMode.VIDEO, score_threshold=0.4,
            category_allowlist=['person'], max_results=8))
        self.faces = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
            base_options=base(model_asset_path=str(ROOT/'models/face.task')),
            running_mode=vision.RunningMode.VIDEO, num_faces=6,
            min_face_detection_confidence=0.45, output_facial_transformation_matrixes=True))
        self.timestamp = 0

    def detect(self, frame):
        import cv2
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb)
        self.timestamp = max(self.timestamp+1, int(time.monotonic()*1000))
        result = self.people.detect_for_video(image, self.timestamp)
        observations = []
        for d in result.detections:
            b = d.bounding_box
            observations.append({'box': (max(0,b.origin_x/w), max(0,b.origin_y/h), min(1,(b.origin_x+b.width)/w), min(1,(b.origin_y+b.height)/h)), 'facing': False})
        faces = self.faces.detect_for_video(image, self.timestamp)
        for landmarks, matrix in zip(faces.face_landmarks, faces.facial_transformation_matrixes):
            xs, ys = [p.x for p in landmarks], [p.y for p in landmarks]
            box = (max(0,min(xs)), max(0,min(ys)), min(1,max(xs)), min(1,max(ys)))
            cx, cy = (box[0]+box[2])/2, (box[1]+box[3])/2
            # This estimates head orientation only; it cannot prove eye fixation or reading.
            yaw = math.degrees(math.atan2(float(matrix[0,2]), float(matrix[2,2])))
            pitch = math.degrees(math.atan2(-float(matrix[1,2]), math.hypot(float(matrix[0,2]),float(matrix[2,2]))))
            facing = abs(yaw) < 23 and abs(pitch) < 22 and (box[2]-box[0])*w >= 40
            matches = [o for o in observations if o['box'][0] <= cx <= o['box'][2] and o['box'][1] <= cy <= o['box'][3]]
            if matches:
                target = min(matches, key=lambda o: (o['box'][2]-o['box'][0])*(o['box'][3]-o['box'][1]))
                target['facing'] |= facing
            else:
                # A visible head can still warn when a body is occluded by the seated user.
                observations.append({'box': box, 'facing': facing})
        return observations

    def close(self):
        self.people.close()
        self.faces.close()


def worker(camera, commands, frames, events):
    import cv2
    from camera import Camera
    detector = capture = None
    try:
        events.put(('status', '正在载入本地模型…'))
        detector = Detector()
        events.put(('status', '正在打开摄像头…'))
        capture = Camera(int(camera), 640, 480)
        capture.open()
        monitor = Monitor()
        while True:
            started = time.monotonic()
            while True:
                try:
                    name, value = commands.get_nowait()
                except queue.Empty:
                    break
                if name == 'stop':
                    return
                if name == 'owner':
                    events.put(('calibration', monitor.calibrate(value)))
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError('摄像头画面中断。监测已停止，请重新启动。')
            # Mirror before detection so clicks and displayed boxes share identical coordinates.
            frame = cv2.flip(frame, 1)
            observations = detector.detect(frame)
            tracks, alerts = monitor.update(observations, time.monotonic())
            for alert in alerts:
                events.put(('alert', alert))
            ok, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            payload = {'jpeg': jpeg.tobytes(), 'tracks': [asdict(t) for t in tracks],
                       'owner': monitor.owner, 'at': time.monotonic(),
                       'fps': round(1/max(0.125, time.monotonic()-started), 1)}
            # Only retain the newest frame, so slow UI rendering cannot build a video backlog.
            try:
                frames.get_nowait()
            except queue.Empty:
                pass
            try:
                frames.put_nowait(payload)
            except queue.Full:
                pass
            time.sleep(max(0, 0.125-(time.monotonic()-started)))
    except Exception as exc:
        events.put(('error', str(exc)))
    finally:
        if capture is not None:
            capture.release()
        if detector is not None:
            detector.close()
        events.put(('stopped', None))
