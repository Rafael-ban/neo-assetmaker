"""
主窗口 - 三栏布局
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QMenuBar, QMenu, QStatusBar,
    QFileDialog, QMessageBox, QLabel
)
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QAction, QKeySequence, QIcon

from config.epconfig import EPConfig
from config.constants import APP_NAME, APP_VERSION, get_resolution_spec
from gui.widgets.config_panel import ConfigPanel
from gui.widgets.video_preview import VideoPreviewWidget
from gui.widgets.timeline import TimelineWidget
from gui.widgets.json_preview import JsonPreviewWidget


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self._config: Optional[EPConfig] = None
        self._project_path: str = ""
        self._base_dir: str = ""
        self._is_modified: bool = False

        self._setup_ui()
        self._setup_menu()
        self._setup_icon()
        self._connect_signals()
        self._load_settings()

        self._update_title()
        logger.info("主窗口初始化完成")

    def _setup_icon(self):
        """设置窗口图标"""
        icon_path = os.path.join(
            os.path.dirname(__file__), '..', 'resources', 'icons', 'favicon.ico'
        )
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            logger.debug(f"已加载窗口图标: {icon_path}")
        else:
            logger.warning(f"窗口图标文件不存在: {icon_path}")

    def _setup_ui(self):
        """设置UI"""
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(1200, 800)

        # 中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 三栏分割器
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.splitter)

        # === 左侧: 配置面板 ===
        self.config_panel = ConfigPanel()
        self.splitter.addWidget(self.config_panel)

        # === 中间: 视频预览 + 时间轴 ===
        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(5, 5, 5, 5)
        preview_layout.setSpacing(5)

        self.video_preview = VideoPreviewWidget()
        preview_layout.addWidget(self.video_preview, stretch=1)

        self.timeline = TimelineWidget()
        preview_layout.addWidget(self.timeline)

        self.splitter.addWidget(preview_container)

        # === 右侧: JSON预览 ===
        self.json_preview = JsonPreviewWidget()
        self.splitter.addWidget(self.json_preview)

        # 设置分割比例
        self.splitter.setSizes([350, 600, 350])
        self.splitter.setStretchFactor(0, 0)  # 左侧固定
        self.splitter.setStretchFactor(1, 1)  # 中间可伸缩
        self.splitter.setStretchFactor(2, 0)  # 右侧固定

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

    def _setup_menu(self):
        """设置菜单"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")

        self.action_new = QAction("新建项目(&N)", self)
        self.action_new.setShortcut(QKeySequence.StandardKey.New)
        file_menu.addAction(self.action_new)

        self.action_open = QAction("打开项目(&O)...", self)
        self.action_open.setShortcut(QKeySequence.StandardKey.Open)
        file_menu.addAction(self.action_open)

        self.action_save = QAction("保存(&S)", self)
        self.action_save.setShortcut(QKeySequence.StandardKey.Save)
        file_menu.addAction(self.action_save)

        self.action_save_as = QAction("另存为(&A)...", self)
        self.action_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        file_menu.addAction(self.action_save_as)

        file_menu.addSeparator()

        self.action_exit = QAction("退出(&X)", self)
        self.action_exit.setShortcut(QKeySequence.StandardKey.Quit)
        file_menu.addAction(self.action_exit)

        # 工具菜单
        tools_menu = menubar.addMenu("工具(&T)")

        self.action_validate = QAction("验证配置(&V)", self)
        self.action_validate.setShortcut(QKeySequence("Ctrl+T"))
        tools_menu.addAction(self.action_validate)

        self.action_export = QAction("导出素材(&E)...", self)
        self.action_export.setShortcut(QKeySequence("Ctrl+E"))
        tools_menu.addAction(self.action_export)

        tools_menu.addSeparator()

        self.action_batch_convert = QAction("批量转换老素材(&B)...", self)
        tools_menu.addAction(self.action_batch_convert)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")

        self.action_about = QAction("关于(&A)", self)
        help_menu.addAction(self.action_about)

    def _connect_signals(self):
        """连接信号"""
        # 菜单动作
        self.action_new.triggered.connect(self._on_new_project)
        self.action_open.triggered.connect(self._on_open_project)
        self.action_save.triggered.connect(self._on_save_project)
        self.action_save_as.triggered.connect(self._on_save_as)
        self.action_exit.triggered.connect(self.close)
        self.action_validate.triggered.connect(self._on_validate)
        self.action_export.triggered.connect(self._on_export)
        self.action_batch_convert.triggered.connect(self._on_batch_convert)
        self.action_about.triggered.connect(self._on_about)

        # 配置面板
        self.config_panel.config_changed.connect(self._on_config_changed)
        self.config_panel.video_file_selected.connect(self._on_video_file_selected)

        # 视频预览
        self.video_preview.video_loaded.connect(self._on_video_loaded)
        self.video_preview.frame_changed.connect(self._on_frame_changed)
        self.video_preview.playback_state_changed.connect(self._on_playback_changed)

        # 时间轴
        self.timeline.play_pause_clicked.connect(self.video_preview.toggle_play)
        self.timeline.seek_requested.connect(self.video_preview.seek_to_frame)
        self.timeline.prev_frame_clicked.connect(self.video_preview.prev_frame)
        self.timeline.next_frame_clicked.connect(self.video_preview.next_frame)
        self.timeline.goto_start_clicked.connect(lambda: self.video_preview.seek_to_frame(0))
        self.timeline.goto_end_clicked.connect(
            lambda: self.video_preview.seek_to_frame(self.video_preview.total_frames - 1)
        )
        self.timeline.set_in_point_clicked.connect(self.timeline.set_in_point_to_current)
        self.timeline.set_out_point_clicked.connect(self.timeline.set_out_point_to_current)

    def _load_settings(self):
        """加载设置"""
        settings = QSettings("ArknightsPassMaker", "MainWindow")
        geometry = settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
            logger.debug("已恢复窗口几何设置")

    def _save_settings(self):
        """保存设置"""
        settings = QSettings("ArknightsPassMaker", "MainWindow")
        settings.setValue("geometry", self.saveGeometry())
        logger.debug("已保存窗口几何设置")

    def _update_title(self):
        """更新窗口标题"""
        title = f"{APP_NAME} v{APP_VERSION}"
        if self._project_path:
            title = f"{os.path.basename(self._project_path)} - {title}"
        if self._is_modified:
            title = f"* {title}"
        self.setWindowTitle(title)

    def _on_new_project(self):
        """新建项目"""
        if not self._check_save():
            return

        # 选择目录
        dir_path = QFileDialog.getExistingDirectory(
            self, "选择项目目录", ""
        )
        if not dir_path:
            return

        # 创建新配置
        self._config = EPConfig()
        self._base_dir = dir_path
        self._project_path = os.path.join(dir_path, "epconfig.json")
        self._is_modified = True

        # 更新UI
        self.config_panel.set_config(self._config, self._base_dir)
        self.json_preview.set_config(self._config, self._base_dir)
        self._update_title()
        self.status_bar.showMessage(f"新建项目: {dir_path}")

    def _on_open_project(self):
        """打开项目"""
        if not self._check_save():
            return

        path, _ = QFileDialog.getOpenFileName(
            self, "打开配置文件", "",
            "JSON文件 (*.json);;所有文件 (*.*)"
        )
        if not path:
            return

        try:
            self._config = EPConfig.load_from_file(path)
            self._project_path = path
            self._base_dir = os.path.dirname(path)
            self._is_modified = False

            # 更新UI
            self.config_panel.set_config(self._config, self._base_dir)
            self.json_preview.set_config(self._config, self._base_dir)

            # 尝试加载循环视频
            if self._config.loop.file:
                video_path = self._config.loop.file
                # 如果是相对路径，转换为绝对路径
                if not os.path.isabs(video_path):
                    video_path = os.path.join(self._base_dir, video_path)
                logger.info(f"尝试加载循环视频: {video_path}")
                if os.path.exists(video_path):
                    self.video_preview.load_video(video_path)
                else:
                    logger.warning(f"循环视频文件不存在: {video_path}")

            self._update_title()
            self.status_bar.showMessage(f"已打开: {path}")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开文件失败:\n{e}")

    def _on_save_project(self):
        """保存项目"""
        if not self._config:
            return

        if not self._project_path:
            self._on_save_as()
            return

        try:
            self._config.save_to_file(self._project_path)
            self._is_modified = False
            self._update_title()
            self.status_bar.showMessage(f"已保存: {self._project_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败:\n{e}")

    def _on_save_as(self):
        """另存为"""
        if not self._config:
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "保存配置文件",
            self._project_path or "epconfig.json",
            "JSON文件 (*.json)"
        )
        if not path:
            return

        try:
            self._config.save_to_file(path)
            self._project_path = path
            self._base_dir = os.path.dirname(path)
            self._is_modified = False
            self._update_title()
            self.status_bar.showMessage(f"已保存: {path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败:\n{e}")

    def _on_validate(self):
        """验证配置"""
        if not self._config:
            QMessageBox.information(self, "提示", "请先创建或打开项目")
            return

        from core.validator import EPConfigValidator

        validator = EPConfigValidator(self._base_dir)
        results = validator.validate_config(self._config)

        if not validator.has_errors():
            QMessageBox.information(self, "验证通过", validator.get_summary())
        else:
            errors = validator.get_errors()
            warnings = validator.get_warnings()

            msg = f"{validator.get_summary()}\n\n"
            if errors:
                msg += "错误:\n"
                for r in errors[:5]:
                    msg += f"  - {r}\n"
            if warnings:
                msg += "\n警告:\n"
                for r in warnings[:5]:
                    msg += f"  - {r}\n"

            QMessageBox.warning(self, "验证结果", msg)

    def _on_export(self):
        """导出素材"""
        if not self._config:
            QMessageBox.information(self, "提示", "请先创建或打开项目")
            return

        # 选择导出目录
        dir_path = QFileDialog.getExistingDirectory(
            self, "选择导出目录", self._base_dir
        )
        if not dir_path:
            return

        QMessageBox.information(
            self, "导出",
            f"导出功能正在开发中...\n导出目录: {dir_path}"
        )

    def _on_batch_convert(self):
        """批量转换老素材"""
        from core.legacy_converter import LegacyConverter

        # 选择源目录
        src_dir = QFileDialog.getExistingDirectory(
            self, "选择老素材所在目录", ""
        )
        if not src_dir:
            return

        # 选择目标目录
        dst_dir = QFileDialog.getExistingDirectory(
            self, "选择转换后的保存目录", ""
        )
        if not dst_dir:
            return

        # 确认转换
        result = QMessageBox.question(
            self, "确认转换",
            f"将从以下目录转换老素材:\n\n"
            f"源目录: {src_dir}\n"
            f"目标目录: {dst_dir}\n\n"
            f"是否继续?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if result != QMessageBox.StandardButton.Yes:
            return

        # 执行转换
        logger.info(f"开始批量转换: {src_dir} -> {dst_dir}")
        self.status_bar.showMessage("正在转换老素材...")

        try:
            converter = LegacyConverter()
            results = converter.batch_convert(src_dir, dst_dir)

            summary = converter.get_summary()
            logger.info(summary)

            # 显示结果
            if results:
                success_count = sum(1 for r in results if r.success)
                fail_count = len(results) - success_count

                msg = f"{summary}\n\n"
                if fail_count > 0:
                    msg += "失败的转换:\n"
                    for r in results:
                        if not r.success:
                            msg += f"  - {os.path.basename(r.src_path)}: {r.message}\n"

                QMessageBox.information(self, "转换完成", msg)
            else:
                QMessageBox.warning(
                    self, "转换结果",
                    f"未找到可转换的老素材文件夹\n\n"
                    f"老素材格式应包含:\n"
                    f"  - epconfig.txt\n"
                    f"  - loop.mp4\n"
                    f"  - logo.argb (可选)\n"
                    f"  - overlay.argb (可选)"
                )

            self.status_bar.showMessage(summary)

        except Exception as e:
            logger.error(f"批量转换失败: {e}")
            QMessageBox.critical(self, "错误", f"转换失败:\n{e}")
            self.status_bar.showMessage("转换失败")

    def _on_about(self):
        """关于"""
        QMessageBox.about(
            self, f"关于 {APP_NAME}",
            f"<h3>{APP_NAME}</h3>"
            f"<p>版本: {APP_VERSION}</p>"
            f"<p>明日方舟通行证素材制作器</p>"
            f"<p>融合 ep_material_maker 和 decompiled 项目</p>"
        )

    def _on_config_changed(self):
        """配置变更"""
        self._is_modified = True
        self._update_title()

        # 更新JSON预览
        if self._config:
            self.json_preview.set_config(self._config, self._base_dir)

    def _on_video_file_selected(self, path: str):
        """视频文件被选择"""
        logger.info(f"视频文件被选择: {path}")
        if path and os.path.exists(path):
            self.video_preview.load_video(path)
        else:
            logger.warning(f"视频文件不存在: {path}")

    def _on_video_loaded(self, total_frames: int, fps: float):
        """视频加载完成"""
        self.timeline.set_total_frames(total_frames)
        self.timeline.set_fps(fps)
        self.timeline.set_in_point(0)
        self.timeline.set_out_point(total_frames - 1)
        self.status_bar.showMessage(f"视频已加载: {total_frames} 帧, {fps:.1f} FPS")

    def _on_frame_changed(self, frame: int):
        """帧变更"""
        self.timeline.set_current_frame(frame)

    def _on_playback_changed(self, is_playing: bool):
        """播放状态变更"""
        self.timeline.set_playing(is_playing)

    def _check_save(self) -> bool:
        """检查是否需要保存"""
        if not self._is_modified:
            return True

        result = QMessageBox.question(
            self, "保存更改",
            "当前项目有未保存的更改，是否保存?",
            QMessageBox.StandardButton.Save |
            QMessageBox.StandardButton.Discard |
            QMessageBox.StandardButton.Cancel
        )

        if result == QMessageBox.StandardButton.Save:
            self._on_save_project()
            return not self._is_modified
        elif result == QMessageBox.StandardButton.Discard:
            return True
        else:
            return False

    def closeEvent(self, event):
        """关闭事件"""
        if self._check_save():
            self._save_settings()
            event.accept()
        else:
            event.ignore()
