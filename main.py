
import sys
import json
import threading
from pathlib import Path

from account_backend import analyze_with_account, find_codex, close_connections
from screen_capture import capture_rect

from PySide6.QtCore import Qt, QRect, QPoint, Signal, QObject, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QGuiApplication, QCursor, QFont, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QTextEdit,
    QHBoxLayout, QVBoxLayout, QFrame, QMessageBox, QDialog
)

BASE_DIR = Path(__file__).resolve().parent

CONFIG_PATH = BASE_DIR / "config.json"
DEFAULT_CONFIG = {
    "backend": "chatgpt_account",
    "mode": "explain",
    "save_frames": False,
    "button_size": 54,
    "opacity": 0.96
}

try:
    CONFIG = DEFAULT_CONFIG | json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
except Exception:
    CONFIG = DEFAULT_CONFIG.copy()

MODES = {
    "explain": "看图并解释",
    "translate": "翻译",
    "extract": "提取文字",
    "summarize": "总结要点",
    "practice": "练习题解答",
}

PROMPTS = {
    "explain": (
        "请分析整张截图中的图像和文字，不要只提取文字。"
        "如果是题目，结合示意图、符号、箭头、连接关系、题干和选项回答，并简要说明依据。"
        "机械或齿轮图应先看清零件、啮合或同轴关系，再判断传动或方向；不要凭常识补出图中没有的连接。"
        "如果不是题目，用中文解释主要图形或内容。看不清或图没截全时请具体指出，不要猜。"
    ),
    "translate": (
        "请识别这块屏幕区域中的主要文字，并翻译成自然中文。"
        "如果原文已经是中文，则翻译成自然英文。"
        "保留关键术语，不要添加无关解释。"
    ),
    "extract": (
        "请尽可能准确提取这块屏幕区域中的可读文字。"
        "保持原有顺序和分段，不要改写，不要总结。"
    ),
    "summarize": (
        "请结合这块屏幕区域的图像、示意图和文字，总结核心信息，不要忽略非文字内容。"
        "先给一句总述，再给最多3条要点。"
        "如果信息不足，请明确说明。"
    ),
    "practice": (
        "请同时观察题目中的图片、示意图、箭头、连接关系、文字和选项。"
        "如果是练习题，结合图形信息给出答案和简短理由；先确认图示关系，再推导结果。"
        "齿轮题需要区分外啮合、内啮合、同轴、皮带或链条，以及已给定的转向。"
        "如果不是练习题，就说明它不是一道可回答的练习题。"
        "如果信息不足，请说信息不足，不要猜。"
    ),
}

class Bridge(QObject):
    ok = Signal(str)
    err = Signal(str)
    finished = Signal()

BRIDGE = Bridge()

def analyze_image(img, mode):
    return analyze_with_account(img, PROMPTS.get(mode, PROMPTS["explain"]), BASE_DIR)

class RegionSelector(QWidget):
    selected = Signal(QRect)

    def __init__(self):
        super().__init__()
        self.start_pos = QPoint()
        self.end_pos = QPoint()
        self.dragging = False

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setCursor(Qt.CrossCursor)

        screens = QGuiApplication.screens()
        left = min(s.geometry().left() for s in screens)
        top = min(s.geometry().top() for s in screens)
        right = max(s.geometry().right() for s in screens)
        bottom = max(s.geometry().bottom() for s in screens)
        self.virtual = QRect(left, top, right-left+1, bottom-top+1)
        self.setGeometry(self.virtual)

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0,0,0,1))

        if self.start_pos != self.end_pos:
            rect = QRect(self.start_pos, self.end_pos).normalized()
            p.setPen(QPen(QColor(52, 139, 255, 240), 2))
            p.drawRect(rect)

            p.setPen(QColor(255,255,255))
            p.setFont(QFont("Segoe UI", 10))
            label = f"{rect.width()} × {rect.height()}"
            p.drawText(rect.adjusted(8, 8, -8, -8), Qt.AlignTop | Qt.AlignLeft, label)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.dragging = True
            self.start_pos = e.position().toPoint()
            self.end_pos = self.start_pos
            self.update()

    def mouseMoveEvent(self, e):
        if self.dragging:
            self.end_pos = e.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.dragging:
            self.dragging = False
            self.end_pos = e.position().toPoint()
            local = QRect(self.start_pos, self.end_pos).normalized()

            if local.width() < 20 or local.height() < 20:
                self.close()
                return

            global_rect = QRect(
                local.left() + self.geometry().left(),
                local.top() + self.geometry().top(),
                local.width(),
                local.height()
            )
            self.hide()
            QTimer.singleShot(60, lambda: self.finish(global_rect))

    def finish(self, rect):
        self.selected.emit(rect)
        self.close()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()

class ResultWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.resize(440, 270)

        self.title = QLabel("AI 解释")
        self.close_btn = QPushButton("×")
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.clicked.connect(self.hide)

        top = QHBoxLayout()
        top.addWidget(self.title)
        top.addStretch()
        top.addWidget(self.close_btn)

        self.text = QTextEdit()
        self.text.setReadOnly(True)

        self.copy_btn = QPushButton("复制")
        self.copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(self.text.toPlainText()))

        bottom = QHBoxLayout()
        self.preview_btn = QPushButton("查看本次图片")
        self.preview_btn.setEnabled(False)
        self.preview_btn.clicked.connect(self.show_capture)
        self.capture_pixmap = None
        self.preview_dialog = None
        bottom.addWidget(self.preview_btn)
        bottom.addStretch()
        bottom.addWidget(self.copy_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.addLayout(top)
        layout.addWidget(self.text)
        layout.addLayout(bottom)

        self.setStyleSheet("""
            QWidget {
                background: rgba(24,24,27,245);
                color: #f4f4f5;
                border-radius: 14px;
                font-family: "Segoe UI";
            }
            QLabel {
                font-size: 14px;
                font-weight: 600;
            }
            QTextEdit {
                background: rgba(255,255,255,9);
                border: 1px solid rgba(255,255,255,18);
                border-radius: 10px;
                padding: 10px;
                font-size: 14px;
            }
            QPushButton {
                background: rgba(255,255,255,12);
                border: 1px solid rgba(255,255,255,22);
                border-radius: 8px;
                padding: 6px 10px;
            }
            QPushButton:hover {
                background: rgba(255,255,255,24);
            }
        """)

        self.drag_offset = None

    def set_capture(self, image):
        image = image.convert('RGB')
        raw = image.tobytes()
        qimage = QImage(raw, image.width, image.height, image.width * 3, QImage.Format_RGB888).copy()
        self.capture_pixmap = QPixmap.fromImage(qimage)
        self.preview_btn.setEnabled(True)
        if self.preview_dialog is not None:
            self.preview_dialog.close()

    def hide_capture(self):
        if self.preview_dialog is not None:
            self.preview_dialog.hide()

    def show_capture(self):
        if self.capture_pixmap is None:
            return
        self.preview_dialog = QDialog(self)
        self.preview_dialog.setWindowTitle("本次发送的图片（仅保留在内存）")
        self.preview_dialog.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        available = screen.availableGeometry()
        label = QLabel()
        label.setPixmap(self.capture_pixmap.scaled(available.width() - 120, available.height() - 160,
                                                   Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout = QVBoxLayout(self.preview_dialog)
        layout.addWidget(label)
        self.preview_dialog.show()

    def show_loading(self, mode_label):
        self.title.setText(mode_label)
        self.text.setPlainText("正在分析你选中的区域…")
        self.place()
        self.show()
        self.raise_()

    def show_text(self, s):
        self.text.setPlainText(s)
        self.place()
        self.show()
        self.raise_()

    def place(self):
        pos = QCursor.pos()
        screen = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        g = screen.availableGeometry()
        x = min(max(pos.x()+20, g.left()), g.right()-self.width())
        y = min(max(pos.y()+20, g.top()), g.bottom()-self.height())
        self.move(x, y)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.drag_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self.drag_offset is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self.drag_offset)

    def mouseReleaseEvent(self, e):
        self.drag_offset = None

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.hide()

class FloatingMenu(QWidget):
    select_requested = Signal()
    repeat_requested = Signal()
    mode_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setWindowOpacity(float(CONFIG.get("opacity", 0.96)))

        self.setStyleSheet("""
            QWidget {
                background: rgba(24,24,27,245);
                color: white;
                border-radius: 14px;
                font-family: "Segoe UI";
                font-size: 13px;
            }
            QPushButton {
                text-align: left;
                background: rgba(255,255,255,10);
                border: 1px solid rgba(255,255,255,18);
                border-radius: 9px;
                padding: 8px 12px;
            }
            QPushButton:hover {
                background: rgba(255,255,255,22);
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8,8,8,8)
        layout.setSpacing(6)

        account_label = QLabel("ChatGPT 账号\n使用账号的 Codex 额度")
        account_label.setStyleSheet("color: #a1a1aa; padding: 4px 6px; font-size: 11px;")
        layout.addWidget(account_label)
        self.mode_label = QLabel("当前：" + MODES.get(CONFIG.get("mode", "explain"), "看图并解释"))
        self.mode_label.setStyleSheet("color: #c4d6ff; padding: 3px 6px; font-size: 11px;")
        layout.addWidget(self.mode_label)

        b1 = QPushButton("框选区域")
        b1.clicked.connect(self.select_requested.emit)
        layout.addWidget(b1)

        b2 = QPushButton("再看一次")
        b2.clicked.connect(self.repeat_requested.emit)
        layout.addWidget(b2)

        for key, label in MODES.items():
            btn = QPushButton(label)
            btn.clicked.connect(lambda checked=False, k=key: self.mode_requested.emit(k))
            layout.addWidget(btn)

        close_btn = QPushButton("退出程序")
        close_btn.clicked.connect(QApplication.instance().quit)
        layout.addWidget(close_btn)

        self.adjustSize()

class FloatingBubble(QWidget):
    clicked = Signal()

    def __init__(self):
        super().__init__()
        size = int(CONFIG.get("button_size", 54))
        self.setFixedSize(size, size)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self.dragging = False
        self.drag_offset = QPoint()

        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(screen.right()-size-24, screen.top()+120)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(2,2,-2,-2)
        p.setBrush(QColor(35, 112, 245, 245))
        p.setPen(QPen(QColor(255,255,255,45), 1))
        p.drawEllipse(rect)

        p.setPen(QColor(255,255,255))
        p.setFont(QFont("Segoe UI", 12, QFont.Bold))
        p.drawText(rect, Qt.AlignCenter, "AI")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.dragging = False
            self.drag_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton:
            if (e.globalPosition().toPoint() - self.frameGeometry().topLeft() - self.drag_offset).manhattanLength() > 3:
                self.dragging = True
            self.move(e.globalPosition().toPoint() - self.drag_offset)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and not self.dragging:
            self.clicked.emit()

class Controller(QObject):
    def __init__(self):
        super().__init__()
        self.last_rect = None
        self.mode = CONFIG.get("mode", "explain")
        self.selector = None
        self.busy = False

        self.bubble = FloatingBubble()
        self.menu = FloatingMenu()
        self.result = ResultWindow()

        self.bubble.clicked.connect(self.toggle_menu)
        self.menu.select_requested.connect(self.select_region)
        self.menu.repeat_requested.connect(self.repeat_region)
        self.menu.mode_requested.connect(self.set_mode)

        BRIDGE.ok.connect(self.result.show_text)
        BRIDGE.err.connect(lambda s: self.result.show_text("发生错误：\n" + s))
        BRIDGE.finished.connect(self.finish_analysis)

        self.bubble.show()

    def toggle_menu(self):
        if self.menu.isVisible():
            self.menu.hide()
            return

        bubble_pos = self.bubble.geometry()
        screen = QGuiApplication.screenAt(self.bubble.geometry().center()) or QGuiApplication.primaryScreen()
        g = screen.availableGeometry()

        self.menu.adjustSize()
        x = bubble_pos.left() - self.menu.width() - 10
        y = bubble_pos.top()

        if x < g.left():
            x = bubble_pos.right() + 10
        if y + self.menu.height() > g.bottom():
            y = g.bottom() - self.menu.height()

        self.menu.move(x, y)
        self.menu.show()
        self.menu.raise_()

    def set_mode(self, mode):
        self.mode = mode
        self.menu.mode_label.setText("当前：" + MODES.get(mode, "看图并解释"))
        CONFIG["mode"] = mode
        try:
            CONFIG_PATH.write_text(json.dumps(CONFIG, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        self.menu.hide()

    def select_region(self):
        if self.busy:
            self.menu.hide()
            return
        self.menu.hide()
        self.result.hide()
        self.result.hide_capture()
        self.selector = RegionSelector()
        self.selector.selected.connect(self.region_selected)
        self.selector.show()
        self.selector.raise_()
        self.selector.activateWindow()

    def region_selected(self, rect):
        self.last_rect = rect
        self.analyze_rect(rect)

    def repeat_region(self):
        self.menu.hide()
        if self.last_rect is None:
            self.select_region()
            return
        self.analyze_rect(self.last_rect)

    def analyze_rect(self, rect):
        if self.busy:
            return
        self.busy = True
        mode = self.mode
        self.menu.hide()
        self.result.hide()
        self.result.hide_capture()
        self.bubble.hide()
        QTimer.singleShot(90, lambda: self.begin_analysis(rect, mode))

    def finish_analysis(self):
        self.busy = False

    def begin_analysis(self, rect, mode):
        try:
            img = capture_rect(rect)
        except Exception as error:
            self.busy = False
            self.bubble.show()
            self.result.show_text("无法读取框选区域：\n" + str(error))
            return
        self.bubble.show()
        self.result.set_capture(img)
        self.result.show_loading(MODES.get(mode, "AI 解释"))

        def worker():
            try:
                answer = analyze_image(img, mode)
                BRIDGE.ok.emit(answer)
            except Exception as e:
                BRIDGE.err.emit(str(e))
            finally:
                BRIDGE.finished.emit()

        threading.Thread(target=worker, daemon=True).start()

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.aboutToQuit.connect(close_connections)

    controller = Controller()

    try:
        find_codex()
    except RuntimeError as error:
        message = str(error)
        QTimer.singleShot(500, lambda: QMessageBox.information(
            None,
            "需要登录 ChatGPT 账号",
            message
        ))

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
