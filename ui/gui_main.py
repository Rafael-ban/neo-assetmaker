"""明日方舟通行证 资源转换器 - GUI入口"""

import sys
import os
import logging
from PyQt6.QtWidgets import (
    QApplication, QStackedWidget, QMessageBox, QFileDialog, QProgressDialog
)
from PyQt6.QtCore import QObject, pyqtSignal, Qt

from .main_window import MainWindow
from .video_preview_widget import VideoPreviewWidget
from .image_preview_widget import ImagePreviewWidget
from .side_panel import OperatorPanel, DisplayPanel
from .timeline_widget import TimelineWidget


def get_exe_dir() -> str:
    """获取 EXE 所在目录（用于输出目录，兼容 Nuitka onefile）"""
    return os.path.dirname(os.path.abspath(sys.argv[0]))


def get_internal_resource_dir() -> str:
    """获取内部资源目录（打包在 EXE 内的图标等文件）"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(current_dir)


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from asset_maker import AssetMaker
    from config import SCREEN_WIDTH, SCREEN_HEIGHT, LOGO_WIDTH, LOGO_HEIGHT
except ImportError:
    AssetMaker = None
    SCREEN_WIDTH, SCREEN_HEIGHT = 360, 640
    LOGO_WIDTH, LOGO_HEIGHT = 256, 256

try:
    from core.export_service import ExportService, VideoExportParams
    EXPORT_SERVICE_AVAILABLE = True
except ImportError:
    ExportService = None
    VideoExportParams = None
    EXPORT_SERVICE_AVAILABLE = False

try:
    from core.logger_setup import setup_gui_logger
    LOGGER_AVAILABLE = True
except ImportError:
    setup_gui_logger = None
    LOGGER_AVAILABLE = False

try:
    from .log_dialog import LogDialog
    LOG_DIALOG_AVAILABLE = True
except ImportError:
    LogDialog = None
    LOG_DIALOG_AVAILABLE = False

logger = logging.getLogger(__name__)


class ApplicationController(QObject):
    """应用程序控制器 - 协调各组件之间的信号和数据流"""

    status_message = pyqtSignal(str)

    def __init__(self):
        super().__init__()

        if LOGGER_AVAILABLE and setup_gui_logger:
            setup_gui_logger()
            logger.info("GUI日志系统已初始化")

        self.main_window = MainWindow()

        self.video_preview = VideoPreviewWidget()
        self.image_preview = ImagePreviewWidget()
        self.timeline = TimelineWidget()
        self.operator_panel = OperatorPanel()
        self.display_panel = DisplayPanel()

        # 预览区堆叠组件，用于切换视频/图片预览
        self.preview_stack = QStackedWidget()
        self.preview_stack.addWidget(self.video_preview)
        self.preview_stack.addWidget(self.image_preview)

        self.main_window.set_operator_panel(self.operator_panel)
        self.main_window.set_display_panel(self.display_panel)
        self.main_window.set_preview_widget(self._create_preview_container())

        self._current_mode = 0  # 0: 运营员素材, 1: 待机屏图
        self._crop_rect = (0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)

        self._export_service = None
        self._progress_dialog = None
        if EXPORT_SERVICE_AVAILABLE and ExportService:
            self._export_service = ExportService()
            self._connect_export_signals()
            logger.info("导出服务已初始化")
        else:
            logger.warning("导出服务不可用，导出功能将被禁用")

        self._log_dialog = None
        self._log_handler = None
        if LOG_DIALOG_AVAILABLE and LogDialog:
            self._log_dialog = LogDialog(self.main_window)
            self._log_handler = self._log_dialog.create_handler()
            logging.getLogger().addHandler(self._log_handler)
            logger.info("日志对话框已初始化")

        self._connect_signals()

    def _create_preview_container(self):
        """创建预览容器，包含预览堆栈和时间轴"""
        from PyQt6.QtWidgets import QWidget, QVBoxLayout

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self.preview_stack, 1)
        layout.addWidget(self.timeline)

        return container

    def _connect_signals(self):
        """连接所有组件信号"""
        self.main_window.video_opened.connect(self._on_video_opened)
        self.main_window.image_opened.connect(self._on_image_opened)
        self.main_window.mode_changed.connect(self._on_mode_changed)
        self.main_window.export_requested.connect(self._on_export_requested)

        self.operator_panel.loop_video_selected.connect(self._on_loop_video_selected)
        self.operator_panel.intro_video_selected.connect(self._on_intro_video_selected)
        self.operator_panel.logo_image_selected.connect(self._on_logo_image_selected)
        self.operator_panel.overlay_image_selected.connect(self._on_overlay_image_selected)
        self.operator_panel.background_color_changed.connect(self._on_background_color_changed)
        self.operator_panel.export_requested.connect(self._on_export_requested)
        self.operator_panel.view_log_requested.connect(self._on_view_log_requested)

        self.display_panel.image_selected.connect(self._on_display_image_selected)
        self.display_panel.export_requested.connect(self._on_export_display)

        self.video_preview.cropbox_changed.connect(self._on_cropbox_changed)
        self.video_preview.frame_changed.connect(self._on_frame_changed)
        self.video_preview.playback_state_changed.connect(self._on_playback_state_changed)
        self.video_preview.video_loaded.connect(self._on_video_loaded)

        self.image_preview.image_loaded.connect(self._on_image_loaded)

        self.timeline.play_pause_clicked.connect(self._on_play_pause)
        self.timeline.seek_requested.connect(self._on_seek)
        self.timeline.prev_frame_clicked.connect(self._on_prev_frame)
        self.timeline.next_frame_clicked.connect(self._on_next_frame)
        self.timeline.goto_start_clicked.connect(self._on_goto_start)
        self.timeline.goto_end_clicked.connect(self._on_goto_end)
        self.timeline.set_in_point_clicked.connect(self._on_set_in_point)
        self.timeline.set_out_point_clicked.connect(self._on_set_out_point)

    def _connect_export_signals(self):
        """连接导出服务的信号"""
        if self._export_service:
            self._export_service.progress_updated.connect(self._on_export_progress)
            self._export_service.export_completed.connect(self._on_export_completed)
            self._export_service.export_failed.connect(self._on_export_failed)

    def _on_video_opened(self, path: str):
        if self.video_preview.load_video(path):
            self.preview_stack.setCurrentWidget(self.video_preview)
            self.timeline.show()
            self._update_status(f"已加载视频: {os.path.basename(path)}")
        else:
            QMessageBox.warning(self.main_window, "错误", f"无法加载视频文件:\n{path}")

    def _on_image_opened(self, path: str):
        if self._current_mode == 0:
            self._on_logo_image_selected(path)
        else:
            self._on_display_image_selected(path)

    def _on_mode_changed(self, index: int):
        self._current_mode = index
        if index == 0:
            self.preview_stack.setCurrentWidget(self.video_preview)
            self.timeline.show()
        else:
            self.preview_stack.setCurrentWidget(self.image_preview)
            self.image_preview.set_preview_mode('display')
            self.timeline.hide()

    def _on_export_requested(self):
        if self._current_mode == 0:
            self._export_operator_assets()
        else:
            self._on_export_display()

    def _on_loop_video_selected(self, path: str):
        if self.video_preview.load_video(path):
            self.preview_stack.setCurrentWidget(self.video_preview)
            self.timeline.show()

    def _on_intro_video_selected(self, path: str):
        self._update_status(f"已选择入场视频: {os.path.basename(path)}")

    def _on_logo_image_selected(self, path: str):
        self.image_preview.set_preview_mode('logo')
        if self.image_preview.load_image(path):
            self.preview_stack.setCurrentWidget(self.image_preview)
            self.timeline.hide()

    def _on_overlay_image_selected(self, path: str):
        self.image_preview.set_preview_mode('overlay')
        if self.image_preview.load_image(path):
            self.preview_stack.setCurrentWidget(self.image_preview)
            self.timeline.hide()

    def _on_background_color_changed(self, argb: int):
        self.image_preview.set_background_color(argb)

    def _on_display_image_selected(self, path: str):
        self.image_preview.set_preview_mode('display')
        if self.image_preview.load_image(path):
            self.preview_stack.setCurrentWidget(self.image_preview)
            self.timeline.hide()

    def _on_export_display(self):
        logger.info("开始导出待机屏图")

        display_name = self.display_panel.get_display_name()
        if not display_name:
            QMessageBox.warning(self.main_window, "错误", "请输入待机屏名称")
            return

        image = self.image_preview.get_processed_image()
        if image is None:
            QMessageBox.warning(self.main_window, "错误", "请先加载图片")
            return

        output_dir = os.path.join(get_exe_dir(), "asset", display_name)
        os.makedirs(output_dir, exist_ok=True)

        try:
            if self._export_service:
                self._show_progress_dialog("正在导出待机屏图...")
                self._export_service.export_display(output_dir, image)
            else:
                save_path = os.path.join(output_dir, "display.argb")
                self._save_argb_image(image, save_path)
                logger.info(f"待机屏图已导出: {save_path}")
                self._update_status(f"已导出: {save_path}")
                QMessageBox.information(self.main_window, "成功", f"待机屏图已导出:\n{output_dir}")
        except Exception as e:
            logger.error(f"待机屏图导出失败: {str(e)}")
            self._hide_progress_dialog()
            QMessageBox.critical(self.main_window, "错误", f"导出失败:\n{str(e)}")

    def _on_cropbox_changed(self, x: int, y: int, w: int, h: int):
        self._crop_rect = (x, y, w, h)
        self.operator_panel.update_crop_info(x, y, w, h)

    def _on_frame_changed(self, frame: int):
        self.timeline.set_current_frame(frame)

    def _on_playback_state_changed(self, is_playing: bool):
        self.timeline.set_playing(is_playing)

    def _on_video_loaded(self, frame_count: int, fps: float):
        self.timeline.set_total_frames(frame_count)
        self.timeline.set_fps(fps)
        self.timeline.set_in_point(0)
        self.timeline.set_out_point(frame_count - 1)
        self.operator_panel.update_time_range(0, frame_count - 1)

    def _on_image_loaded(self, width: int, height: int, has_alpha: bool):
        if self._current_mode == 1:
            self.display_panel.update_image_info(width, height, has_alpha)

    def _on_play_pause(self):
        self.video_preview.toggle_playback()

    def _on_seek(self, frame: int):
        self.video_preview.seek_to_frame(frame)

    def _on_prev_frame(self):
        self.video_preview.step_frame(-1)

    def _on_next_frame(self):
        self.video_preview.step_frame(1)

    def _on_goto_start(self):
        in_point = self.timeline.get_in_point()
        self.video_preview.seek_to_frame(in_point)

    def _on_goto_end(self):
        out_point = self.timeline.get_out_point()
        self.video_preview.seek_to_frame(out_point)

    def _on_set_in_point(self):
        current = self.video_preview.get_current_frame()
        self.timeline.set_in_point(current)
        self.operator_panel.update_time_range(current, self.timeline.get_out_point())

    def _on_set_out_point(self):
        current = self.video_preview.get_current_frame()
        self.timeline.set_out_point(current)
        self.operator_panel.update_time_range(self.timeline.get_in_point(), current)

    def _export_operator_assets(self):
        """导出运营员素材（视频、Logo、Overlay、配置）"""
        logger.info("开始导出运营员素材")

        operator_name = self.operator_panel.get_operator_name()
        if not operator_name:
            QMessageBox.warning(self.main_window, "错误", "请输入运营员名称")
            return

        loop_video_path = self.operator_panel.get_loop_video_path()
        if not loop_video_path:
            QMessageBox.warning(self.main_window, "错误", "请选择循环待机视频")
            return

        output_dir = os.path.join(get_exe_dir(), "asset", operator_name)
        os.makedirs(output_dir, exist_ok=True)

        if not self._export_service:
            self._export_operator_assets_legacy(operator_name, output_dir)
            return

        try:
            in_point = self.timeline.get_in_point()
            out_point = self.timeline.get_out_point()
            bg_color = self.operator_panel.get_background_color()
            video_fps = self.video_preview.get_fps() if hasattr(self.video_preview, 'get_fps') else 30.0

            loop_crop_args = (
                loop_video_path,
                self._crop_rect,
                in_point,
                out_point,
                video_fps
            )

            intro_crop_args = None
            intro_video_path = self.operator_panel.get_intro_video_path()
            if intro_video_path:
                intro_crop_args = (
                    intro_video_path,
                    self._crop_rect,
                    in_point,
                    out_point,
                    video_fps
                )

            logo_image = None
            logo_path = self.operator_panel.get_logo_image_path()
            if logo_path:
                logo_image = self.image_preview.get_processed_image()

            overlay_image = None
            overlay_path = self.operator_panel.get_overlay_image_path()
            if overlay_path:
                overlay_image = self.image_preview.get_processed_image()

            self._show_progress_dialog("正在导出运营员素材...")

            logger.info(f"导出参数: 运营员={operator_name}, 输出目录={output_dir}")
            logger.info(f"循环视频: {loop_video_path}, 帧范围={in_point}-{out_point}")

            loop_video_params = VideoExportParams(
                video_path=loop_video_path,
                cropbox=self._crop_rect,
                start_frame=in_point,
                end_frame=out_point,
                fps=video_fps
            )

            intro_video_params = None
            if intro_video_path:
                intro_video_params = VideoExportParams(
                    video_path=intro_video_path,
                    cropbox=self._crop_rect,
                    start_frame=in_point,
                    end_frame=out_point,
                    fps=video_fps
                )

            epconfig_data = {
                "operator": operator_name,
                "background_color": hex(bg_color)
            }

            self._export_service.export_all(
                output_dir=output_dir,
                logo_mat=logo_image,
                overlay_mat=overlay_image,
                loop_video_params=loop_video_params,
                intro_video_params=intro_video_params,
                epconfig_data=epconfig_data
            )

        except Exception as e:
            logger.error(f"导出失败: {str(e)}")
            self._hide_progress_dialog()
            QMessageBox.critical(self.main_window, "错误", f"导出失败:\n{str(e)}")

    def _export_operator_assets_legacy(self, operator_name: str, output_dir: str):
        """回退导出方法（当ExportService不可用时）"""
        try:
            in_point = self.timeline.get_in_point()
            out_point = self.timeline.get_out_point()
            bg_color = self.operator_panel.get_background_color()

            self._update_status("正在导出素材...")

            if AssetMaker:
                maker = AssetMaker(output_dir, operator_name)
                pass

            self._update_status("素材导出完成")
            QMessageBox.information(
                self.main_window, "成功",
                f"运营员素材已导出到:\n{output_dir}"
            )
        except Exception as e:
            logger.error(f"Legacy导出失败: {str(e)}")
            QMessageBox.critical(self.main_window, "错误", f"导出失败:\n{str(e)}")

    def _save_argb_image(self, image, path: str):
        """保存ARGB格式图片（BGRA转ARGB）"""
        import numpy as np

        h, w = image.shape[:2]
        argb_data = np.zeros((h, w, 4), dtype=np.uint8)
        argb_data[..., 0] = image[..., 3]
        argb_data[..., 1] = image[..., 2]
        argb_data[..., 2] = image[..., 1]
        argb_data[..., 3] = image[..., 0]

        with open(path, 'wb') as f:
            f.write(argb_data.tobytes())

    def _update_status(self, message: str):
        self.main_window.status_label.setText(message)
        self.status_message.emit(message)

    def _show_progress_dialog(self, title: str):
        self._progress_dialog = QProgressDialog(title, "取消", 0, 100, self.main_window)
        self._progress_dialog.setWindowTitle("导出进度")
        self._progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress_dialog.setMinimumDuration(0)
        self._progress_dialog.setValue(0)
        self._progress_dialog.canceled.connect(self._on_export_canceled)
        self._progress_dialog.show()

    def _hide_progress_dialog(self):
        if self._progress_dialog:
            try:
                self._progress_dialog.canceled.disconnect(self._on_export_canceled)
            except (TypeError, RuntimeError):
                pass
            self._progress_dialog.close()
            self._progress_dialog = None

    def _on_export_progress(self, progress: int, message: str):
        dialog = self._progress_dialog
        if dialog is not None:
            try:
                dialog.setValue(progress)
                dialog.setLabelText(message)
            except (RuntimeError, AttributeError):
                pass
        self._update_status(message)

    def _on_export_completed(self, output_path: str):
        logger.info(f"导出完成: {output_path}")
        self._hide_progress_dialog()
        self._update_status("导出完成")
        QMessageBox.information(
            self.main_window, "成功",
            f"素材导出完成:\n{output_path}"
        )

    def _on_export_failed(self, error_message: str):
        logger.error(f"导出失败: {error_message}")
        self._hide_progress_dialog()
        self._update_status("导出失败")
        QMessageBox.critical(
            self.main_window, "错误",
            f"导出失败:\n{error_message}"
        )

    def _on_export_status(self, message: str):
        logger.info(message)
        self._update_status(message)

    def _on_export_canceled(self):
        if self._export_service:
            self._export_service.cancel()
        logger.info("用户取消导出")
        self._update_status("导出已取消")

    def _on_view_log_requested(self):
        if self._log_dialog:
            self._log_dialog.show()
            self._log_dialog.raise_()
            self._log_dialog.activateWindow()
        else:
            QMessageBox.information(
                self.main_window, "提示",
                "日志对话框不可用。\n请确保已安装 log_dialog 模块。"
            )

    def show(self):
        self.main_window.show()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 设置窗口图标（需要多个尺寸以适配Windows标题栏）
    from PyQt6.QtGui import QIcon, QPixmap
    from PyQt6.QtCore import QSize
    icon_path = os.path.join(get_internal_resource_dir(), "favicon.ico")
    if os.path.exists(icon_path):
        icon = QIcon()
        pixmap = QPixmap(icon_path)
        if not pixmap.isNull():
            for size in [16, 32, 48, 256]:
                scaled = pixmap.scaled(
                    QSize(size, size),
                    aspectRatioMode=Qt.AspectRatioMode.KeepAspectRatio,
                    transformMode=Qt.TransformationMode.SmoothTransformation
                )
                icon.addPixmap(scaled)
            app.setWindowIcon(icon)

    # 深色主题样式
    app.setStyleSheet("""
        QWidget {
            background-color: #2d2d2d;
            color: #ddd;
        }
        QGroupBox {
            border: 1px solid #555;
            border-radius: 4px;
            margin-top: 10px;
            padding-top: 10px;
            font-weight: bold;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }
        QLineEdit {
            background-color: #3d3d3d;
            border: 1px solid #555;
            border-radius: 3px;
            padding: 5px;
            color: #fff;
        }
        QLineEdit:focus {
            border-color: #0078d4;
        }
        QLineEdit:read-only {
            background-color: #353535;
            color: #aaa;
        }
        QPushButton {
            background-color: #444;
            border: 1px solid #555;
            border-radius: 3px;
            padding: 6px 12px;
            color: #ddd;
        }
        QPushButton:hover {
            background-color: #555;
        }
        QPushButton:pressed {
            background-color: #333;
        }
        QCheckBox {
            spacing: 8px;
        }
        QCheckBox::indicator {
            width: 16px;
            height: 16px;
        }
        QScrollBar:vertical {
            background-color: #2d2d2d;
            width: 12px;
        }
        QScrollBar::handle:vertical {
            background-color: #555;
            border-radius: 4px;
            min-height: 20px;
        }
        QScrollBar::handle:vertical:hover {
            background-color: #666;
        }
        QSplitter::handle {
            background-color: #444;
        }
        QSplitter::handle:hover {
            background-color: #555;
        }
    """)

    controller = ApplicationController()
    controller.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
