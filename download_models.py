"""Fetch pinned public models and verify integrity before inference."""
from pathlib import Path
import hashlib
import urllib.request

ROOT = Path(__file__).resolve().parent / 'models'
MODELS = {
    'person.tflite': ('https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite0/int8/1/efficientdet_lite0.tflite',
                      '0720bf247bd76e6594ea28fa9c6f7c5242be774818997dbbeffc4da460c723bb'),
    'face.task': ('https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task',
                  '64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff'),
}


def valid(path, expected):
    return path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == expected


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
            print(f'Downloading {name} from Google...')
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
