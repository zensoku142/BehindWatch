"""Fetch pinned public models and verify integrity before inference."""
from pathlib import Path
import hashlib
import urllib.request

ROOT = Path(__file__).resolve().parents[1] / 'models'
MODELS = {
    'person_yolox.onnx': ('https://media.githubusercontent.com/media/opencv/opencv_zoo/47534e27c9851bb1128ccc0102f1145e27f23f98/models/object_detection_yolox/object_detection_yolox_2022nov.onnx',
                         'c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063'),
    'face.task': ('https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task',
                  '64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff'),
    'sface.onnx': ('https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx',
                   '0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79'),
}


def valid(path, expected):
    if not path.is_file():
        return False
    # 分块校验避免启动时将整个模型复制到内存。
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest() == expected


def verify():
    for name, (_, digest) in MODELS.items():
        if not valid(ROOT/name, digest):
            raise RuntimeError(f'Model missing or damaged: {name}. Run launch.cmd to repair.')


def download():
    ROOT.mkdir(exist_ok=True)
    for name, (url, digest) in MODELS.items():
        target = ROOT/name
        if valid(target, digest):
            print(f'OK: {name}')
            continue
        temp = target.with_suffix(target.suffix+'.download')
        try:
            print(f'Downloading {name}...')
            with urllib.request.urlopen(url, timeout=60) as response, temp.open('wb') as output:
                while chunk := response.read(1024*1024):
                    output.write(chunk)
            if not valid(temp, digest):
                raise RuntimeError(f'Integrity check failed: {name}')
            temp.replace(target)
        finally:
            # An interrupted download must never be mistaken for a usable model.
            temp.unlink(missing_ok=True)
    verify()


if __name__ == '__main__':
    download()
