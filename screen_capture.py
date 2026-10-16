"""Convert Qt logical selection coordinates to physical screenshot pixels."""
from PIL import Image
from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication
import mss


def capture_rect(rect):
    screens = QGuiApplication.screens()
    parts = [(screen, rect.intersected(screen.geometry())) for screen in screens]
    parts = [(screen, part) for screen, part in parts if not part.isEmpty()]
    if not parts:
        raise RuntimeError('选区不在当前屏幕内，请重新框选。')
    output_scale = max(screen.devicePixelRatio() for screen, _ in parts)
    output = Image.new('RGB', (round(rect.width() * output_scale), round(rect.height() * output_scale)), 'black')
    with mss.MSS() as capture:
        monitors = capture.monitors[1:]
        for screen, part in parts:
            geometry = screen.geometry()
            scale = screen.devicePixelRatio()
            matches = [monitor for monitor in monitors
                       if monitor['left'] == geometry.x() and monitor['top'] == geometry.y()
                       and abs(monitor['width'] - geometry.width() * scale) <= 2
                       and abs(monitor['height'] - geometry.height() * scale) <= 2]
            if len(monitors) == 1 and len(screens) == 1:
                monitor = monitors[0]
            elif len(matches) == 1:
                monitor = matches[0]
            else:
                raise RuntimeError('无法准确对应当前显示器的缩放，请将选区放到主屏幕后重试。')
            region = physical_region(part, geometry, scale, monitor)
            shot = capture.grab(region)
            image = Image.frombytes('RGB', shot.size, shot.rgb)
            target_size = (round(part.width() * output_scale), round(part.height() * output_scale))
            if image.size != target_size:
                image = image.resize(target_size, Image.Resampling.LANCZOS)
            output.paste(image, (round((part.x() - rect.x()) * output_scale), round((part.y() - rect.y()) * output_scale)))
    return output


def physical_region(part, geometry, scale, monitor):
    left = monitor['left'] + round((part.x() - geometry.x()) * scale)
    top = monitor['top'] + round((part.y() - geometry.y()) * scale)
    right = min(monitor['left'] + monitor['width'], monitor['left'] + round((part.x() + part.width() - geometry.x()) * scale))
    bottom = min(monitor['top'] + monitor['height'], monitor['top'] + round((part.y() + part.height() - geometry.y()) * scale))
    return {'left': left, 'top': top, 'width': right - left, 'height': bottom - top}
