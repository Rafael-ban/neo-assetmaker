# 导出服务模块

import cv2
import struct
import numpy as np
import os
import shutil
import subprocess
import logging
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from PyQt6.QtCore import QThread, pyqtSignal, QObject

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    LOGO_WIDTH, LOGO_HEIGHT,
    VIDEO_WIDTH, VIDEO_HEIGHT,
    DISPLAY_WIDTH, DISPLAY_HEIGHT
)

logger = logging.getLogger(__name__)


def _get_exe_dir() -> str:
    """获取 EXE 所在目录"""
    return os.path.dirname(os.path.abspath(sys.argv[0]))


def _get_internal_resource_dir() -> str:
    """获取内部资源目录（Nuitka打包模式下的临时解压目录）"""
    try:
        return __compiled__.containing_dir
    except NameError:
        return os.path.dirname(os.path.abspath(__file__))


class ExportType(Enum):
    """导出类型枚举"""
    LOGO = "logo"
    OVERLAY = "overlay"
    DISPLAY = "display"
    LOOP_VIDEO = "loop"
    INTRO_VIDEO = "intro"


@dataclass
class ExportTask:
    """导出任务数据类"""
    export_type: ExportType
    output_path: str
    data: Any  # 图像矩阵或视频参数


@dataclass
class VideoExportParams:
    """视频导出参数"""
    video_path: str
    cropbox: Tuple[int, int, int, int]  # (x, y, w, h)
    start_frame: int
    end_frame: int
    fps: float


class ExportWorker(QThread):
    """导出工作线程，在后台执行导出任务"""

    progress_updated = pyqtSignal(int, str)
    export_completed = pyqtSignal(str)
    export_failed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tasks: list[ExportTask] = []
        self._output_dir: str = ""
        self._ffmpeg_path: str = ""
        self._cancelled: bool = False
        self._epconfig_data: Dict[str, Any] = {}

    def setup(self,
              tasks: list[ExportTask],
              output_dir: str,
              ffmpeg_path: str = "",
              epconfig_data: Dict[str, Any] = None):
        """设置导出任务"""
        self._tasks = tasks
        self._output_dir = output_dir
        self._ffmpeg_path = ffmpeg_path or self._find_ffmpeg()
        self._epconfig_data = epconfig_data or {}
        self._cancelled = False

    def cancel(self):
        self._cancelled = True
        logger.info("导出任务已请求取消")

    def is_cancelled(self) -> bool:
        return self._cancelled

    def _find_ffmpeg(self) -> str:
        """查找 ffmpeg.exe"""
        internal_ffmpeg = os.path.join(_get_internal_resource_dir(), "ffmpeg.exe")
        if os.path.isfile(internal_ffmpeg):
            logger.info(f"找到内部 ffmpeg: {internal_ffmpeg}")
            return internal_ffmpeg

        exe_dir_ffmpeg = os.path.join(_get_exe_dir(), "ffmpeg.exe")
        if os.path.isfile(exe_dir_ffmpeg):
            logger.info(f"找到 EXE 目录 ffmpeg: {exe_dir_ffmpeg}")
            return exe_dir_ffmpeg

        cwd_ffmpeg = os.path.join(os.getcwd(), "ffmpeg.exe")
        if os.path.isfile(cwd_ffmpeg):
            logger.info(f"找到工作目录 ffmpeg: {cwd_ffmpeg}")
            return cwd_ffmpeg

        try:
            result = subprocess.run(
                ["where", "ffmpeg"] if os.name == 'nt' else ["which", "ffmpeg"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                ffmpeg_path = result.stdout.strip().split('\n')[0]
                logger.info(f"找到系统 ffmpeg: {ffmpeg_path}")
                return ffmpeg_path
        except Exception as e:
            logger.warning(f"查找系统ffmpeg失败: {e}")

        logger.warning("未找到 ffmpeg")
        return ""

    def run(self):
        try:
            total_tasks = len(self._tasks)
            if total_tasks == 0:
                self.export_completed.emit("没有需要导出的任务")
                return

            os.makedirs(self._output_dir, exist_ok=True)

            completed = 0
            for i, task in enumerate(self._tasks):
                if self._cancelled:
                    self.export_failed.emit("导出已取消")
                    return

                base_progress = int((i / total_tasks) * 100)

                try:
                    self._execute_task(task, base_progress, total_tasks)
                    completed += 1
                except Exception as e:
                    logger.exception(f"执行任务 {task.export_type.value} 失败")
                    self.export_failed.emit(f"导出 {task.export_type.value} 失败: {str(e)}")
                    return

            if self._epconfig_data:
                self._generate_epconfig()

            self.progress_updated.emit(100, "导出完成")
            self.export_completed.emit(f"成功导出 {completed} 个文件到 {self._output_dir}")

        except Exception as e:
            logger.exception("导出过程发生错误")
            self.export_failed.emit(f"导出失败: {str(e)}")

    def _execute_task(self, task: ExportTask, base_progress: int, total_tasks: int):
        output_path = os.path.join(self._output_dir, task.output_path)

        if task.export_type == ExportType.LOGO:
            self.progress_updated.emit(base_progress, f"正在导出 {task.output_path}...")
            self._generate_logo(output_path, task.data)

        elif task.export_type == ExportType.OVERLAY:
            self.progress_updated.emit(base_progress, f"正在导出 {task.output_path}...")
            self._generate_overlay_display(output_path, task.data)

        elif task.export_type == ExportType.DISPLAY:
            self.progress_updated.emit(base_progress, f"正在导出 {task.output_path}...")
            self._generate_overlay_display(output_path, task.data)

        elif task.export_type in (ExportType.LOOP_VIDEO, ExportType.INTRO_VIDEO):
            self.progress_updated.emit(base_progress, f"正在导出 {task.output_path}...")
            self._generate_video(output_path, task.data, base_progress, total_tasks)

    def _generate_logo(self, result_path: str, mat: np.ndarray):
        """生成logo的ARGB文件"""
        mat = cv2.rotate(mat, cv2.ROTATE_180)
        mat = mat[::-1, :, :]
        mat = mat.astype(np.uint8)
        h, w, c = mat.shape
        logger.debug(f"Logo shape: {h} x {w} x {c}")

        with open(result_path, "wb") as f:
            for y in range(h):
                if self._cancelled:
                    raise InterruptedError("导出已取消")
                for x in range(w):
                    b, g, r = mat[y, x][:3]
                    f.write(struct.pack("BBBB", b, g, r, 255))

    def _generate_overlay_display(self, result_path: str, mat: np.ndarray):
        """生成overlay/display的ARGB文件"""
        mat = cv2.rotate(mat, cv2.ROTATE_180)
        mat = mat.astype(np.uint8)
        h, w, c = mat.shape
        logger.debug(f"Overlay/Display shape: {h} x {w} x {c}")

        with open(result_path, "wb") as f:
            for y in range(h):
                if self._cancelled:
                    raise InterruptedError("导出已取消")
                for x in range(w):
                    if c == 4:
                        b, g, r, a = mat[y, x]
                    else:
                        b, g, r = mat[y, x][:3]
                        a = 255
                    f.write(struct.pack("BBBB", b, g, r, a))

    def _generate_video(self, result_path: str, params: VideoExportParams,
                        base_progress: int, total_tasks: int):
        """生成视频文件"""
        if not self._ffmpeg_path:
            raise RuntimeError("未找到 ffmpeg，无法导出视频")

        temp_dir = os.path.join(self._output_dir, "temp_frames")
        os.makedirs(temp_dir, exist_ok=True)

        try:
            cap = cv2.VideoCapture(params.video_path)
            if not cap.isOpened():
                raise RuntimeError(f"无法打开视频文件: {params.video_path}")

            cap.set(cv2.CAP_PROP_POS_FRAMES, params.start_frame)
            total_frames = params.end_frame - params.start_frame

            for frame_index in range(total_frames):
                if self._cancelled:
                    raise InterruptedError("导出已取消")

                ret, frame = cap.read()
                if not ret:
                    logger.warning(f"在帧 {frame_index} 处读取失败")
                    break

                x, y, w, h = params.cropbox
                frame = frame[y:y+h, x:x+w]
                frame = cv2.rotate(frame, cv2.ROTATE_180)
                frame = cv2.resize(frame, (SCREEN_WIDTH, SCREEN_HEIGHT))

                padding_width = VIDEO_WIDTH - frame.shape[1]
                if padding_width > 0:
                    padding = np.zeros((SCREEN_HEIGHT, padding_width, 3), dtype=np.uint8)
                    frame = np.hstack([padding, frame])

                frame_path = os.path.join(temp_dir, f"frame_{str(frame_index).zfill(6)}.png")
                cv2.imwrite(frame_path, frame)

                if frame_index % 10 == 0:
                    frame_progress = int((frame_index / total_frames) * (100 / total_tasks))
                    current_progress = base_progress + frame_progress
                    self.progress_updated.emit(
                        current_progress,
                        f"正在处理帧 {frame_index}/{total_frames}..."
                    )

            cap.release()

            self.progress_updated.emit(base_progress + int(80 / total_tasks), "正在编码视频...")

            ffmpeg_cmd = [
                self._ffmpeg_path,
                "-framerate", str(params.fps),
                "-i", os.path.join(temp_dir, "frame_%06d.png"),
                "-vf", "format=nv12",
                "-c:v", "libx264",
                "-b:v", "600k",
                "-an",
                "-y",
                result_path
            ]

            logger.info(f"执行 ffmpeg 命令: {' '.join(ffmpeg_cmd)}")

            process = subprocess.run(
                ffmpeg_cmd,
                capture_output=True,
                text=True
            )

            if process.returncode != 0:
                logger.error(f"ffmpeg 错误: {process.stderr}")
                raise RuntimeError(f"ffmpeg 编码失败: {process.stderr[:200]}")

        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    def _generate_epconfig(self):
        epconfig_path = os.path.join(self._output_dir, "epconfig.txt")

        try:
            with open(epconfig_path, "w", encoding="utf-8") as f:
                for key, value in self._epconfig_data.items():
                    f.write(f"{key}={value}\n")
            logger.info(f"已生成配置文件: {epconfig_path}")
        except Exception as e:
            logger.warning(f"生成 epconfig.txt 失败: {e}")


class ExportService(QObject):
    """导出服务类，提供高级接口用于GUI调用"""

    progress_updated = pyqtSignal(int, str)
    export_completed = pyqtSignal(str)
    export_failed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: Optional[ExportWorker] = None
        self._ffmpeg_path: str = ""

    @property
    def is_exporting(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    @property
    def ffmpeg_available(self) -> bool:
        if not self._ffmpeg_path:
            self._ffmpeg_path = self._find_ffmpeg()
        return bool(self._ffmpeg_path)

    @property
    def ffmpeg_path(self) -> str:
        if not self._ffmpeg_path:
            self._ffmpeg_path = self._find_ffmpeg()
        return self._ffmpeg_path

    def set_ffmpeg_path(self, path: str):
        if os.path.isfile(path):
            self._ffmpeg_path = path
            logger.info(f"手动设置 ffmpeg 路径: {path}")
        else:
            raise FileNotFoundError(f"ffmpeg 文件不存在: {path}")

    def _find_ffmpeg(self) -> str:
        """查找 ffmpeg"""
        internal_ffmpeg = os.path.join(_get_internal_resource_dir(), "ffmpeg.exe")
        if os.path.isfile(internal_ffmpeg):
            return internal_ffmpeg

        exe_dir_ffmpeg = os.path.join(_get_exe_dir(), "ffmpeg.exe")
        if os.path.isfile(exe_dir_ffmpeg):
            return exe_dir_ffmpeg

        cwd_ffmpeg = os.path.join(os.getcwd(), "ffmpeg.exe")
        if os.path.isfile(cwd_ffmpeg):
            return cwd_ffmpeg

        try:
            result = subprocess.run(
                ["where", "ffmpeg"] if os.name == 'nt' else ["which", "ffmpeg"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]
        except Exception:
            pass

        return ""

    def export_all(self,
                   output_dir: str,
                   logo_mat: Optional[np.ndarray] = None,
                   overlay_mat: Optional[np.ndarray] = None,
                   display_mat: Optional[np.ndarray] = None,
                   loop_video_params: Optional[VideoExportParams] = None,
                   intro_video_params: Optional[VideoExportParams] = None,
                   epconfig_data: Optional[Dict[str, Any]] = None):
        """导出所有资源"""
        if self.is_exporting:
            self.export_failed.emit("已有导出任务正在进行")
            return

        tasks = []

        if logo_mat is not None:
            tasks.append(ExportTask(
                export_type=ExportType.LOGO,
                output_path="logo.argb",
                data=logo_mat
            ))

        if overlay_mat is not None:
            tasks.append(ExportTask(
                export_type=ExportType.OVERLAY,
                output_path="overlay.argb",
                data=overlay_mat
            ))

        if display_mat is not None:
            tasks.append(ExportTask(
                export_type=ExportType.DISPLAY,
                output_path="display.argb",
                data=display_mat
            ))

        if loop_video_params is not None:
            if not self.ffmpeg_available:
                self.export_failed.emit("未找到 ffmpeg，无法导出视频")
                return
            tasks.append(ExportTask(
                export_type=ExportType.LOOP_VIDEO,
                output_path="loop.mp4",
                data=loop_video_params
            ))

        if intro_video_params is not None:
            if not self.ffmpeg_available:
                self.export_failed.emit("未找到 ffmpeg，无法导出视频")
                return
            tasks.append(ExportTask(
                export_type=ExportType.INTRO_VIDEO,
                output_path="intro.mp4",
                data=intro_video_params
            ))

        if not tasks:
            self.export_failed.emit("没有需要导出的内容")
            return

        self._worker = ExportWorker(self)
        self._worker.setup(tasks, output_dir, self._ffmpeg_path, epconfig_data)

        self._worker.progress_updated.connect(self.progress_updated.emit)
        self._worker.export_completed.connect(self._on_export_completed)
        self._worker.export_failed.connect(self._on_export_failed)

        self._worker.start()
        logger.info(f"开始导出 {len(tasks)} 个任务到 {output_dir}")

    def export_logo(self, output_dir: str, mat: np.ndarray,
                    epconfig_data: Optional[Dict[str, Any]] = None):
        self.export_all(output_dir, logo_mat=mat, epconfig_data=epconfig_data)

    def export_overlay(self, output_dir: str, mat: np.ndarray,
                       epconfig_data: Optional[Dict[str, Any]] = None):
        self.export_all(output_dir, overlay_mat=mat, epconfig_data=epconfig_data)

    def export_display(self, output_dir: str, mat: np.ndarray,
                       epconfig_data: Optional[Dict[str, Any]] = None):
        self.export_all(output_dir, display_mat=mat, epconfig_data=epconfig_data)

    def export_video(self, output_dir: str, video_type: str,
                     params: VideoExportParams,
                     epconfig_data: Optional[Dict[str, Any]] = None):
        """导出视频，video_type为"loop"或"intro" """
        if video_type == "loop":
            self.export_all(output_dir, loop_video_params=params, epconfig_data=epconfig_data)
        elif video_type == "intro":
            self.export_all(output_dir, intro_video_params=params, epconfig_data=epconfig_data)
        else:
            self.export_failed.emit(f"未知的视频类型: {video_type}")

    def cancel(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            logger.info("已发送取消请求")
        else:
            logger.warning("没有正在进行的导出任务")

    def _on_export_completed(self, message: str):
        self.export_completed.emit(message)
        self._cleanup_worker()

    def _on_export_failed(self, message: str):
        self.export_failed.emit(message)
        self._cleanup_worker()

    def _cleanup_worker(self):
        if self._worker:
            self._worker.wait()
            self._worker.deleteLater()
            self._worker = None
