"""Local YOLO26s detection, ByteTrack tracking and MediaPipe face landmarks."""
from pathlib import Path
import math
import time
import queue
from dataclasses import asdict
from core.logic import Monitor
from core.face_identity import CONFIRM_FRAMES, best_match, delete_template, load_template, save_template

ROOT = Path(__file__).resolve().parents[1]


class Detector:
    def __init__(self):
        from scripts.download_models import verify
        verify()
        import mediapipe as mp
        self.mp = mp
        base, vision = mp.tasks.BaseOptions, mp.tasks.vision
        from core.person_detection import PersonDetector
        self.people = PersonDetector(ROOT/'models/yolo26s.onnx')
        self.faces = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
            base_options=base(model_asset_path=str(ROOT/'models/face.task')),
            running_mode=vision.RunningMode.VIDEO, num_faces=6,
            min_face_detection_confidence=0.45, output_facial_transformation_matrixes=True))
        import cv2
        self.recognizer = cv2.FaceRecognizerSF_create(str(ROOT/'models/sface.onnx'), '')
        self.identify = False
        self.timestamp = 0

    def detect(self, frame):
        import cv2
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb)
        self.timestamp = max(self.timestamp+1, int(time.monotonic()*1000))
        observations = self.people.detect(frame)
        for observation in observations:
            x1, y1, x2, y2 = [int(value*size) for value, size in zip(observation['box'], (w, h, w, h))]
            crop = frame[y1:y2, x1:x2]
            if crop.shape[0] >= 20 and crop.shape[1] >= 20:
                # A coarse torso-color signature helps a manually ignored coworker survive brief tracking gaps.
                torso = crop[crop.shape[0]//4:3*crop.shape[0]//4, crop.shape[1]//5:4*crop.shape[1]//5]
                hsv = cv2.cvtColor(torso, cv2.COLOR_BGR2HSV)
                hist = cv2.calcHist([hsv], [0, 1], None, [12, 6], [0, 180, 0, 256])
                observation['appearance'] = (hist / max(float(hist.sum()), 1)).reshape(-1).tolist()
        faces = self.faces.detect_for_video(image, self.timestamp)
        body_count = len(observations)
        assigned_bodies = set()
        for landmarks, matrix in zip(faces.face_landmarks, faces.facial_transformation_matrixes):
            xs, ys = [p.x for p in landmarks], [p.y for p in landmarks]
            box = (max(0,min(xs)), max(0,min(ys)), min(1,max(xs)), min(1,max(ys)))
            cx, cy = (box[0]+box[2])/2, (box[1]+box[3])/2
            # This estimates head orientation only; it cannot prove eye fixation or reading.
            yaw = math.degrees(math.atan2(float(matrix[0,2]), float(matrix[2,2])))
            pitch = math.degrees(math.atan2(-float(matrix[1,2]), math.hypot(float(matrix[0,2]),float(matrix[2,2]))))
            facing = abs(yaw) < 23 and abs(pitch) < 22 and (box[2]-box[0])*w >= 40
            feature = None
            if self.identify and abs(yaw) < 25 and abs(pitch) < 25 and (box[2]-box[0])*w >= 80:
                import numpy as np
                eyes = sorted((landmarks[33], landmarks[263]), key=lambda point: point.x)
                mouth = sorted((landmarks[61], landmarks[291]), key=lambda point: point.x)
                points = [eyes[0], eyes[1], landmarks[1], mouth[0], mouth[1]]
                row = np.array([[box[0]*w, box[1]*h, (box[2]-box[0])*w, (box[3]-box[1])*h,
                                 *(coordinate for point in points for coordinate in (point.x*w, point.y*h)), 1]], dtype=np.float32)
                try:
                    aligned = self.recognizer.alignCrop(frame, row)
                    feature = self.recognizer.feature(aligned).reshape(-1)
                except cv2.error:
                    # A partial or malformed face must not stop person monitoring.
                    feature = None
            matches = [(i, observations[i]) for i in range(body_count) if i not in assigned_bodies
                       and observations[i]['box'][0] <= cx <= observations[i]['box'][2]
                       and observations[i]['box'][1] <= cy <= observations[i]['box'][3]]
            if matches:
                index, target = min(matches, key=lambda entry: (entry[1]['box'][2]-entry[1]['box'][0])*(entry[1]['box'][3]-entry[1]['box'][1]))
                # One body box cannot represent two faces; preserve the second as its own target.
                assigned_bodies.add(index)
                target['facing'] |= facing
                target['face'] = True
                target['face_box'] = box
                if feature is not None:
                    target['feature'] = feature
            else:
                # A visible head can still warn when a body is occluded by the seated user.
                observation = {'box': box, 'facing': facing, 'face': True, 'face_box': box, 'face_only': True}
                if feature is not None:
                    observation['feature'] = feature
                observations.append(observation)
        return observations

    def close(self):
        self.faces.close()


def worker(camera, commands, frames, events, idle_camera=False):
    import cv2
    from core.camera import Camera
    detector = capture = None
    try:
        events.put(('status', '正在载入本地模型…'))
        detector = Detector()
        capture = Camera(int(camera), 640, 480)
        if not idle_camera:
            events.put(('status', '正在打开摄像头…'))
            capture.open()
        active = not idle_camera
        monitor = Monitor()
        from core.person_detection import PersonTracker
        tracker = PersonTracker()
        template = load_template()
        # 点击本人或忽略时复用当前清晰人脸的特征，仅在内存保留本次选择，避免编号重建就丢失标记。
        detector.identify = True
        events.put(('identity', template is not None))
        enrolling = None
        candidate, confirmations = None, 0
        owner_streak = 0
        previous_owner_face = None
        while True:
            started = time.monotonic()
            while True:
                try:
                    name, value = commands.get_nowait()
                except queue.Empty:
                    break
                if name == 'stop':
                    return
                if name == 'camera':
                    if value and not active:
                        capture.open()
                        active = True
                        events.put(('camera', True))
                    elif not value and active:
                        capture.release()
                        monitor.reset_tracking()
                        tracker = PersonTracker()
                        active = False
                        owner_streak = 0
                        previous_owner_face = None
                        events.put(('camera', False))
                    continue
                if name == 'owner':
                    events.put(('calibration', monitor.calibrate(value)))
                elif name == 'toggle_ignore':
                    events.put(('ignore', monitor.toggle_ignore(value)))
                elif name == 'register':
                    if monitor.owner is None:
                        events.put(('registration', '请先在预览中选择本人。'))
                    else:
                        enrolling = {'owner': monitor.owner, 'features': [], 'started': time.monotonic()}
                        detector.identify = True
                elif name == 'delete_identity':
                    delete_template()
                    template = None
                    enrolling = None
                    detector.identify = True
                    candidate, confirmations = None, 0
                    events.put(('identity', False))
            if not active:
                time.sleep(0.1)
                continue
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError('摄像头画面中断。监测已停止，请重新启动。')
            # Mirror before detection so clicks and displayed boxes share identical coordinates.
            frame = cv2.flip(frame, 1)
            observations = tracker.update(detector.detect(frame))
            tracks, movement_alerts = monitor.update(observations, time.monotonic())
            features = {track.id: obs['feature'] for track, obs in zip(tracks, observations) if 'feature' in obs}
            face_ids = {track.id for track, obs in zip(tracks, observations) if obs.get('face')}
            if enrolling is not None:
                if len(face_ids) > 1:
                    # Enrollment with two faces could save the bystander's descriptor as the owner.
                    enrolling = None
                    detector.identify = True
                    events.put(('registration', '注册失败：请确保画面中只有本人。'))
                else:
                    feature = features.get(enrolling['owner']) if monitor.owner == enrolling['owner'] else None
                    if feature is not None:
                        enrolling['features'].append(feature)
            if enrolling is not None:
                if len(enrolling['features']) >= 5:
                    saved = False
                    try:
                        template = save_template(enrolling['features'])
                        saved = True
                    except (OSError, ValueError) as exc:
                        events.put(('registration', f'注册保存失败：{exc}'))
                    enrolling = None
                    detector.identify = True
                    if saved:
                        events.put(('identity', True))
                        events.put(('registration', '本人面容已注册，后续启动将自动识别。'))
                elif time.monotonic() - enrolling['started'] > 10 or monitor.owner != enrolling['owner']:
                    enrolling = None
                    detector.identify = True
                    events.put(('registration', '注册失败：请正对摄像头并保持脸部清晰，再重试。'))
            if template is not None and monitor.owner is None:
                match = best_match(template, features)
                candidate, confirmations = (match, confirmations + 1) if match is not None and match == candidate else (match, 1)
                if match is not None and confirmations >= CONFIRM_FRAMES:
                    monitor.calibrate(match)
                    candidate, confirmations = None, 0
            else:
                candidate, confirmations = None, 0
            owner_face = best_match(template, features) if template is not None else None
            # Two consecutive matches to the same tracked face prevent a one-frame stranger match from confirming presence.
            owner_streak = owner_streak + 1 if owner_face is not None and owner_face == previous_owner_face else (1 if owner_face is not None else 0)
            previous_owner_face = owner_face
            for alert in movement_alerts:
                events.put(('alert', alert))
            ok, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            payload = {'jpeg': jpeg.tobytes(), 'tracks': [asdict(t) for t in tracks],
                       'owner': monitor.owner, 'at': time.monotonic(),
                       'face_count': len(face_ids), 'other_face_count': len(face_ids - {owner_face}) if template is not None else 0,
                       'moving_count': sum(track.moving for track in tracks if track.id != monitor.owner),
                       'owner_present': owner_streak >= 2,
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
