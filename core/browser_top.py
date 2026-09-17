import ctypes
import win32gui


def detect_browser_top(automation, uia, hwnd):
    if not win32gui.IsWindow(hwnd) or win32gui.IsIconic(hwnd):
        return None, None
    rect = win32gui.GetWindowRect(hwnd)
    if win32gui.GetClassName(hwnd) not in ("Chrome_WidgetWin_1", "MozillaWindowClass"):
        return rect, None
    window = automation.ElementFromHandle(hwnd)
    if win32gui.GetClassName(hwnd) == "Chrome_WidgetWin_1":
        browser = window.FindFirst(uia.TreeScope_Descendants,
                                  automation.CreatePropertyCondition(uia.UIA_ClassNamePropertyId, "BrowserRootView"))
        # Electron 应用也使用 Chrome 窗口类，必须确认存在浏览器框架才能裁剪。
        if not browser:
            return rect, None
        container = browser.FindFirst(uia.TreeScope_Descendants,
                                      automation.CreatePropertyCondition(uia.UIA_ClassNamePropertyId, "TopContainerView"))
        if container:
            bounds = container.CurrentBoundingRectangle
            # 直接读取 Chrome 顶部容器，包含地址栏和当前显示的书签栏。
            # 裁剪后容器可能被标记为屏幕外，仍需读取其布局边界以避免反复恢复和隐藏。
            if rect[1] <= bounds.top < bounds.bottom < rect[3]:
                return rect, bounds.bottom - rect[1]
    condition = automation.CreatePropertyCondition(uia.UIA_ControlTypePropertyId, uia.UIA_DocumentControlTypeId)
    documents = window.FindAll(uia.TreeScope_Descendants, condition)
    candidates = []
    for index in range(documents.Length):
        document = documents.GetElement(index)
        if document.CurrentIsOffscreen:
            continue
        bounds = document.CurrentBoundingRectangle
        left, top, right, bottom = rect
        # 排除后台标签和窗口外的文档；取最大文档，避免把网页 iframe 当成正文边界。
        if (left <= bounds.left < bounds.right <= right and
                top <= bounds.top < bounds.bottom <= bottom):
            area = (bounds.right - bounds.left) * (bounds.bottom - bounds.top)
            candidates.append((area, bounds.top - top))
    return rect, max(candidates)[1] if candidates else None


def browser_detection_worker(requests, results):
    import comtypes
    import comtypes.client

    comtypes.CoInitialize()
    try:
        # 与主界面使用相同的物理像素坐标，避免高 DPI 下裁剪高度偏移。
        ctypes.windll.user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
        uia = comtypes.client.GetModule("UIAutomationCore.dll")
        automation = comtypes.client.CreateObject(uia.CUIAutomation, interface=uia.IUIAutomation)
        while True:
            request = requests.get()
            if request is None:
                return
            token, hwnd = request
            try:
                rect, height = detect_browser_top(automation, uia, hwnd)
                results.put((token, rect, height))
            except Exception:
                # 浏览器导航、关闭或暂时不提供无障碍信息时，保留顶部而不猜测高度。
                results.put((token, None, None))
    except Exception as e:
        print("初始化浏览器顶部识别失败:", e)
        results.put((None, None, None))
    finally:
        comtypes.CoUninitialize()
