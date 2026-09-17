"""Exercise frozen multiprocessing and local inference without a camera."""
import multiprocessing as mp
import sys


def check_models(result):
    try:
        # 冻结子进程应在界面导入前分流，否则每个采集进程会重复占用 Qt 内存。
        if getattr(sys, 'frozen', False) and 'PySide6.QtWidgets' in sys.modules:
            raise RuntimeError('Capture subprocess imported the GUI')
        import numpy as np
        from core.vision import Detector
        from core.person_detection import PersonTracker
        detector = Detector()
        try:
            PersonTracker().update(detector.detect(np.zeros((480, 640, 3), dtype=np.uint8)))
        finally:
            detector.close()
        result.send(None)
    except Exception as exc:
        result.send(str(exc))
    finally:
        result.close()


def verify_runtime():
    receiver, sender = mp.Pipe(duplex=False)
    process = mp.Process(target=check_models, args=(sender,))
    try:
        process.start()
        sender.close()
        if not receiver.poll(45):
            raise RuntimeError('Inference subprocess timed out')
        error = receiver.recv()
        process.join(timeout=5)
        if error is not None or process.exitcode != 0:
            raise RuntimeError(error or 'Inference subprocess did not exit cleanly')
    finally:
        # 超时或初始化失败也必须回收自检进程，不能残留模型或 Pipe 句柄。
        if process.pid is not None:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
            process.close()
        sender.close()
        receiver.close()
