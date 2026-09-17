"""Local owner face template and conservative similarity checks."""
import json
import os
from pathlib import Path
import tempfile
import ctypes
from ctypes import wintypes

import numpy as np

TEMPLATE_VERSION = 1
MIN_SCORE = 0.45
MIN_MARGIN = 0.08
CONFIRM_FRAMES = 3


def template_path():
    return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'BehindWatch' / 'owner_face.bin'


class _Blob(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]


def _user_protect(data, decrypt=False):
    # DPAPI binds the saved descriptor to the current Windows user without an app-managed key.
    if os.name != 'nt':
        raise OSError('Face registration requires Windows')
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    source = ctypes.create_string_buffer(data)
    input_blob = _Blob(len(data), ctypes.cast(source, ctypes.POINTER(ctypes.c_ubyte)))
    output_blob = _Blob()
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.POINTER(_Blob),
                         ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_Blob)]
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(input_blob), None, None, None, None, 0x1, ctypes.byref(output_blob)):
        raise OSError(ctypes.get_last_error(), 'Windows face template protection failed')
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    try:
        return ctypes.string_at(output_blob.data, output_blob.size)
    finally:
        kernel.LocalFree(ctypes.cast(output_blob.data, ctypes.c_void_p))


def normalized(values):
    vector = np.asarray(values, dtype=np.float32).reshape(-1)
    if vector.size != 128 or not np.isfinite(vector).all():
        return None
    length = float(np.linalg.norm(vector))
    return vector / length if length > 1e-6 else None


def load_template(path=None):
    try:
        data = json.loads(_user_protect((path or template_path()).read_bytes(), decrypt=True))
        return normalized(data['feature']) if data['version'] == TEMPLATE_VERSION else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def save_template(features, path=None):
    path = path or template_path()
    feature = normalized(np.mean(features, axis=0))
    if feature is None:
        raise ValueError('Invalid face feature')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        # A partial write must not become an enrolled identity after a crash.
        with tempfile.NamedTemporaryFile(mode='wb', dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            payload = json.dumps({'version': TEMPLATE_VERSION, 'feature': feature.tolist()}).encode('utf-8')
            stream.write(_user_protect(payload))
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return feature


def delete_template(path=None):
    (path or template_path()).unlink(missing_ok=True)


def best_match(template, features):
    scores = []
    for identity, feature in features.items():
        candidate = normalized(feature)
        if candidate is not None:
            scores.append((float(np.dot(template, candidate)), identity))
    scores.sort(reverse=True)
    # Require one clear match so two similar visible faces cannot silently swap owner.
    if not scores or scores[0][0] < MIN_SCORE or (len(scores) > 1 and scores[0][0] - scores[1][0] < MIN_MARGIN):
        return None
    return scores[0][1]


class FaceAlerts:
    def __init__(self, confirmation_frames=2, cooldown=10.0):
        self.confirmation_frames = confirmation_frames
        self.cooldown = cooldown
        self.mode = None
        self.target = None
        self.frames = 0
        self.last_frame = None
        self.last_sent = float('-inf')

    def update(self, registered, face_ids, owner_id, now):
        face_ids = set(face_ids)
        others = face_ids - {owner_id} if registered else face_ids
        trigger = bool(others) if registered else len(face_ids) >= 2
        target = min(others) if trigger else None
        if self.mode != registered:
            self.mode = registered
            self.frames = 0
            self.last_sent = float('-inf')
        # A missed face or capture gap must restart confirmation, not preserve a stale alert.
        if not trigger or target != self.target or (self.last_frame is not None and now - self.last_frame > .5):
            self.frames = 0
        self.target = target
        self.last_frame = now
        if not trigger:
            return None
        self.frames += 1
        if self.frames < self.confirmation_frames or now - self.last_sent < self.cooldown:
            return None
        self.last_sent = now
        return {'id': target, 'message': '检测到未注册人脸' if registered else '检测到两张及以上人脸'}
