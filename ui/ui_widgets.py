"""Qt controls adapted from TokenMeter; see LICENSE-TokenMeter.txt."""
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QCheckBox, QComboBox, QSizePolicy, QStyle, QTabBar, QWidget
from ui.qt_theme import current_theme, fluent_icon
from ui.i18n import bind_text, tr

class SettingsComboBox(QComboBox):
    opening = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(34)
        self.setMinimumWidth(0)
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        # 下拉提示由 paintEvent 统一绘制；Windows 原生样式仍会绘制箭头，必须显式隐藏以免重叠。
        self.setStyleSheet('QComboBox::drop-down { border: 0; width: 24px; } '
                          'QComboBox::down-arrow { image: none; width: 0; height: 0; }')

    def showPopup(self):
        self.opening.emit()
        super().showPopup()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        # 去掉原生箭头按钮的直角底板后，复用项目的 Fluent 箭头保留清晰的下拉提示。
        icon = fluent_icon("chevron-down", 14)
        if icon.isNull():
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown)
        painter = QPainter(self)
        if not self.isEnabled():
            painter.setOpacity(0.45)
        icon.paint(painter, self.width() - 24, (self.height() - 14) // 2, 14, 14)


class SettingsTabBar(QTabBar):
    HEIGHT = 42
    INSET = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDrawBase(False)
        self.setExpanding(True)
        self.setFixedHeight(self.HEIGHT)

    def tabSizeHint(self, index: int) -> QSize:
        return QSize(self.fontMetrics().horizontalAdvance(self.tabText(index)) + 24, self.HEIGHT)

    def paintEvent(self, event) -> None:
        # 参考 NutriTime 的完整轨道和内缩胶囊；统一绘制可避免原生页签残留直角底板。
        tokens = current_theme()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        border = QColor(tokens.border)
        border.setAlpha(45)
        painter.setPen(QPen(border, 1))
        painter.setBrush(QColor(tokens.surface))
        track = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.drawRoundedRect(track, track.height() / 2, track.height() / 2)
        for index in range(self.count()):
            rect = QRectF(self.tabRect(index)).adjusted(self.INSET, self.INSET, -self.INSET, -self.INSET)
            selected = index == self.currentIndex()
            if selected:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(tokens.accent_soft))
                painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
                if self.hasFocus():
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.setPen(QPen(QColor(tokens.accent), 1))
                    painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
            painter.setPen(QColor(tokens.accent_text if selected else tokens.subtext))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, tr(self.tabText(index)))


class SettingsSwitch(QCheckBox):
    def __init__(self, text: str):
        super().__init__(text)
        # 保留复选框的键盘和无障碍语义，仅把重复的二态控件绘制成开关。
        bind_text(self, text, method='setAccessibleName')
        self.setFixedSize(50, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def hitButton(self, pos) -> bool:
        return self.rect().contains(pos)

    def paintEvent(self, event) -> None:
        tokens = current_theme()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            painter.setOpacity(0.45)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(tokens.accent if self.isChecked() else tokens.disabled))
        painter.drawRoundedRect(QRectF(2, 3, 46, 22), 11, 11)
        # on_accent 是文字对比色，浅色主色会变成黑色；开关圆钮保持白色才能维持一致外观。
        painter.setBrush(QColor("#FFFFFF"))
        thumb_border = QColor(tokens.border)
        thumb_border.setAlpha(45)
        painter.setPen(QPen(thumb_border, 0.5))
        painter.drawEllipse(QRectF(28 if self.isChecked() else 4, 5, 18, 18))
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(tokens.accent), 1))
            painter.drawRoundedRect(QRectF(0.5, 0.5, 49, 27), 13, 13)


def app_icon(size=64):
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 64, size / 64)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(current_theme().accent))
    painter.drawRoundedRect(QRectF(2, 2, 60, 60), 16, 16)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor('#ffffff'), 3))
    painter.drawRoundedRect(QRectF(14, 22, 36, 26), 5, 5)
    painter.drawEllipse(QPointF(32, 35), 7, 7)
    painter.drawLine(QPointF(24, 17), QPointF(40, 17))
    painter.end()
    return QIcon(pixmap)


class Preview(QWidget):
    selected = Signal(int)
    ignore_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.frame = None
        self.picture = QPixmap()
        self.frame_size = QSize(4, 3)
        self.image_rect = QRectF()
        self.selection_mode = None
        self.preview_hidden = False
        policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.setMinimumSize(100, 160)
        self.setAccessibleName(tr('实时预览'))

    def heightForWidth(self, width):
        size = self.frame_size
        return round(width * size.height() / size.width())

    def sizeHint(self):
        return QSize(480, self.heightForWidth(480))

    def set_frame(self, frame):
        previous_size = self.frame_size
        self.frame = frame
        self.picture = QPixmap()
        if frame:
            self.picture.loadFromData(frame['jpeg'], 'JPEG')
        # 后台会释放解码图像；保留尺寸即可稳定遮挡态布局，无需保留像素。
        if not self.picture.isNull():
            self.frame_size = self.picture.size()
        if previous_size != self.frame_size:
            self.updateGeometry()
        self.update()

    def paintEvent(self, event):
        tokens = current_theme()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        # 边框贴合实际视频比例，剩余空间属于布局，不伪装成可点击画面。
        source_size = self.frame_size
        size = source_size.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        w, h = size.width(), size.height()
        ox, oy = (self.width() - w) / 2, (self.height() - h) / 2
        outer = QRectF(ox, oy, w, h).adjusted(.5, .5, -.5, -.5)
        border = QColor(tokens.border)
        border.setAlpha(82)
        painter.setPen(QPen(border, 1))
        painter.setBrush(QColor(tokens.window))
        painter.drawRoundedRect(outer, 9, 9)
        if self.preview_hidden:
            self.image_rect = QRectF()
            painter.setPen(QColor(tokens.text))
            painter.drawText(outer, Qt.AlignmentFlag.AlignCenter, tr('画面已隐藏'))
            painter.setPen(QColor(tokens.subtext))
            painter.drawText(outer.adjusted(16, 48, -16, 0), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                             tr('隐藏画面不影响监测'))
            return
        if not self.frame or self.picture.isNull():
            self.image_rect = QRectF()
            app_icon(40).paint(painter, self.width() // 2 - 20, self.height() // 2 - 65, 40, 40)
            painter.setPen(QColor(tokens.text))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, tr('摄像头尚未开启'))
            painter.setPen(QColor(tokens.subtext))
            painter.drawText(self.rect().adjusted(16, 45, -16, 0), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                             tr('点击「开始监测」；人脸注册可在设置中操作'))
            return
        self.image_rect = QRectF(ox, oy, w, h)
        # 完整帧等比缩放，绘制与点击共用同一坐标，避免圆角或留白影响本人校准。
        clip = QPainterPath()
        clip.addRoundedRect(self.image_rect, 9, 9)
        painter.setClipPath(clip)
        painter.drawPixmap(self.image_rect.toRect(), self.picture)
        for track in self.frame['tracks']:
            x1, y1, x2, y2 = track['box']
            owner = track['id'] == self.frame['owner']
            color = '#18c77a' if owner else '#8e99a8' if track.get('ignored') else '#ffd18a'
            painter.setPen(QPen(QColor(color), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            rect = QRectF(ox + x1*w, oy + y1*h, (x2-x1)*w, (y2-y1)*h)
            painter.drawRect(rect)
            label = tr('本人') if owner else tr('人员 #{id}', id=track['id'])
            if not owner:
                label += ' · ' + tr('已忽略' if track.get('ignored') else '走动中' if track.get('moving') else '静止')
            # 标签独立于小检测框宽度，贴边时向内收；底色保证复杂背景下可读。
            metrics = painter.fontMetrics()
            label = metrics.elidedText(label, Qt.TextElideMode.ElideRight, max(1, int(w - 16)))
            label_w, label_h = metrics.horizontalAdvance(label) + 12, metrics.height() + 6
            label_x = max(ox + 4, min(rect.left(), ox + w - label_w - 4))
            label_y = max(oy + 4, min(rect.top(), oy + h - label_h - 4))
            label_rect = QRectF(label_x, label_y, label_w, label_h)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor('#D921252B'))
            painter.drawRoundedRect(label_rect, 3, 3)
            painter.setPen(QColor(color))
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, label)

    def mousePressEvent(self, event):
        if self.preview_hidden or not self.frame or self.image_rect.isEmpty() or not self.image_rect.contains(event.position()):
            return
        x = (event.position().x() - self.image_rect.x()) / self.image_rect.width()
        y = (event.position().y() - self.image_rect.y()) / self.image_rect.height()
        matches = [t for t in self.frame['tracks'] if t['box'][0] <= x <= t['box'][2] and t['box'][1] <= y <= t['box'][3]]
        if matches:
            target = min(matches, key=lambda t: (t['box'][2]-t['box'][0])*(t['box'][3]-t['box'][1]))
            (self.selected if self.selection_mode == 'owner' else self.ignore_selected).emit(target['id'])
