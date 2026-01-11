"""
老素材格式转换器

将老版本素材格式转换为新格式:
- epconfig.txt -> epconfig.json
- logo.argb -> logo.png
- loop.mp4 -> loop.mp4
"""
import os
import json
import shutil
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from PIL import Image

from config.epconfig import EPConfig, Overlay, OverlayType, ArknightsOverlayOptions

logger = logging.getLogger(__name__)


@dataclass
class ConversionResult:
    """转换结果"""
    success: bool
    src_path: str
    dst_path: str
    message: str = ""
    files_converted: List[str] = None

    def __post_init__(self):
        if self.files_converted is None:
            self.files_converted = []


class LegacyConverter:
    """老素材格式转换器"""

    # ARGB图像默认尺寸 (256KB = 256x256x4 bytes)
    DEFAULT_LOGO_SIZE = (256, 256)

    def __init__(self):
        self._results: List[ConversionResult] = []

    @property
    def results(self) -> List[ConversionResult]:
        """获取转换结果列表"""
        return self._results

    def clear_results(self):
        """清空结果"""
        self._results.clear()

    def detect_legacy_folder(self, folder_path: str) -> bool:
        """
        检测文件夹是否为老素材格式

        Args:
            folder_path: 文件夹路径

        Returns:
            是否为老素材格式
        """
        if not os.path.isdir(folder_path):
            return False

        # 检查必要文件
        required_files = ['epconfig.txt', 'loop.mp4']
        for f in required_files:
            if not os.path.exists(os.path.join(folder_path, f)):
                return False

        return True

    def parse_legacy_config(self, src_dir: str) -> Dict[str, Any]:
        """
        解析老配置文件

        Args:
            src_dir: 源目录

        Returns:
            解析后的配置字典
        """
        config_path = os.path.join(src_dir, 'epconfig.txt')
        config = {
            'color': '#000000',
            'version': 0
        }

        if not os.path.exists(config_path):
            logger.warning(f"配置文件不存在: {config_path}")
            return config

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()

            # 解析格式: "version color"
            # 例如: "0 ff000000"
            parts = content.split()
            if len(parts) >= 1:
                config['version'] = int(parts[0])
            if len(parts) >= 2:
                # 转换颜色格式: ff000000 -> #000000
                color_hex = parts[1]
                if len(color_hex) == 8:
                    # ARGB -> RGB (忽略alpha)
                    config['color'] = f"#{color_hex[2:]}"
                else:
                    config['color'] = f"#{color_hex}"

            logger.debug(f"解析老配置: {config}")

        except Exception as e:
            logger.error(f"解析配置文件失败: {e}")

        return config

    def convert_argb_to_png(
        self,
        argb_path: str,
        png_path: str,
        width: int = 256,
        height: int = 256
    ) -> bool:
        """
        将ARGB原始图像转换为PNG

        Args:
            argb_path: ARGB文件路径
            png_path: 输出PNG路径
            width: 图像宽度
            height: 图像高度

        Returns:
            是否成功
        """
        if not os.path.exists(argb_path):
            logger.warning(f"ARGB文件不存在: {argb_path}")
            return False

        try:
            with open(argb_path, 'rb') as f:
                data = f.read()

            expected_size = width * height * 4
            if len(data) != expected_size:
                logger.warning(
                    f"ARGB文件大小不匹配: {len(data)} != {expected_size}, "
                    f"尝试自动检测尺寸"
                )
                # 尝试自动检测尺寸
                detected = self._detect_image_size(len(data))
                if detected:
                    width, height = detected
                    logger.info(f"检测到图像尺寸: {width}x{height}")
                else:
                    logger.error("无法检测图像尺寸")
                    return False

            # ARGB -> RGBA
            pixels = bytearray(len(data))
            for i in range(0, len(data), 4):
                a, r, g, b = data[i], data[i+1], data[i+2], data[i+3]
                pixels[i] = r
                pixels[i+1] = g
                pixels[i+2] = b
                pixels[i+3] = a

            # 创建图像
            img = Image.frombytes('RGBA', (width, height), bytes(pixels))
            img.save(png_path, 'PNG')

            logger.info(f"已转换ARGB到PNG: {png_path}")
            return True

        except Exception as e:
            logger.error(f"转换ARGB失败: {e}")
            return False

    def _detect_image_size(self, data_size: int) -> Optional[Tuple[int, int]]:
        """
        根据数据大小检测图像尺寸

        Args:
            data_size: 数据字节数

        Returns:
            (宽度, 高度) 或 None
        """
        # 常见尺寸
        common_sizes = [
            (256, 256),   # 262144
            (512, 512),   # 1048576
            (128, 128),   # 65536
            (512, 128),   # 262144
            (256, 512),   # 524288
            (360, 640),   # 921600
            (480, 854),   # 1638720
            (720, 1280),  # 3686400
        ]

        pixel_count = data_size // 4
        for w, h in common_sizes:
            if w * h == pixel_count:
                return (w, h)

        # 尝试正方形
        import math
        sqrt = int(math.sqrt(pixel_count))
        if sqrt * sqrt == pixel_count:
            return (sqrt, sqrt)

        return None

    def copy_video_file(self, src_path: str, dst_path: str) -> bool:
        """
        复制视频文件

        Args:
            src_path: 源文件路径
            dst_path: 目标文件路径

        Returns:
            是否成功
        """
        if not os.path.exists(src_path):
            logger.warning(f"视频文件不存在: {src_path}")
            return False

        try:
            shutil.copy2(src_path, dst_path)
            logger.info(f"已复制视频: {dst_path}")
            return True
        except Exception as e:
            logger.error(f"复制视频失败: {e}")
            return False

    def generate_new_config(
        self,
        legacy_config: Dict[str, Any],
        folder_name: str,
        dst_dir: str
    ) -> bool:
        """
        生成新配置文件

        Args:
            legacy_config: 老配置数据
            folder_name: 文件夹名称（用作素材名称）
            dst_dir: 目标目录

        Returns:
            是否成功
        """
        try:
            # 创建新配置 (默认分辨率为 360x640)
            config = EPConfig()
            config.name = folder_name
            config.description = f"从老素材转换: {folder_name}"
            config.loop.file = "loop.mp4"

            # 设置叠加UI颜色
            color = legacy_config.get('color', '#000000')

            # 检查是否有logo
            has_logo = os.path.exists(os.path.join(dst_dir, 'logo.png'))

            config.overlay = Overlay(
                type=OverlayType.ARKNIGHTS,
                arknights_options=ArknightsOverlayOptions(
                    operator_name=folder_name,
                    color=color,
                    logo="logo.png" if has_logo else None
                )
            )

            if has_logo:
                config.icon = "logo.png"

            # 保存配置
            config_path = os.path.join(dst_dir, 'epconfig.json')
            config.save_to_file(config_path)

            logger.info(f"已生成配置: {config_path}")
            return True

        except Exception as e:
            logger.error(f"生成配置失败: {e}")
            return False

    def convert_folder(self, src_dir: str, dst_dir: str) -> ConversionResult:
        """
        转换单个素材文件夹

        Args:
            src_dir: 源目录
            dst_dir: 目标目录

        Returns:
            转换结果
        """
        folder_name = os.path.basename(src_dir)
        logger.info(f"开始转换: {folder_name}")

        result = ConversionResult(
            success=False,
            src_path=src_dir,
            dst_path=dst_dir
        )

        # 检查源目录
        if not self.detect_legacy_folder(src_dir):
            result.message = "不是有效的老素材格式"
            logger.warning(f"{folder_name}: {result.message}")
            self._results.append(result)
            return result

        # 创建目标目录
        os.makedirs(dst_dir, exist_ok=True)

        # 解析老配置
        legacy_config = self.parse_legacy_config(src_dir)

        # 转换logo.argb -> logo.png
        logo_src = os.path.join(src_dir, 'logo.argb')
        logo_dst = os.path.join(dst_dir, 'logo.png')
        if os.path.exists(logo_src):
            if self.convert_argb_to_png(logo_src, logo_dst):
                result.files_converted.append('logo.png')

        # 复制loop.mp4
        loop_src = os.path.join(src_dir, 'loop.mp4')
        loop_dst = os.path.join(dst_dir, 'loop.mp4')
        if self.copy_video_file(loop_src, loop_dst):
            result.files_converted.append('loop.mp4')

        # 生成新配置
        if self.generate_new_config(legacy_config, folder_name, dst_dir):
            result.files_converted.append('epconfig.json')

        result.success = len(result.files_converted) > 0
        result.message = f"已转换 {len(result.files_converted)} 个文件"

        logger.info(f"{folder_name}: {result.message}")
        self._results.append(result)
        return result

    def batch_convert(
        self,
        src_root: str,
        dst_root: str,
        progress_callback=None
    ) -> List[ConversionResult]:
        """
        批量转换多个素材文件夹

        Args:
            src_root: 源根目录
            dst_root: 目标根目录
            progress_callback: 进度回调函数 (current, total, name)

        Returns:
            转换结果列表
        """
        self.clear_results()

        if not os.path.isdir(src_root):
            logger.error(f"源目录不存在: {src_root}")
            return []

        # 收集要转换的文件夹
        folders = []
        for name in os.listdir(src_root):
            path = os.path.join(src_root, name)
            if os.path.isdir(path) and self.detect_legacy_folder(path):
                folders.append((name, path))

        if not folders:
            logger.warning(f"未找到老素材文件夹: {src_root}")
            return []

        logger.info(f"找到 {len(folders)} 个老素材文件夹")

        # 创建目标目录
        os.makedirs(dst_root, exist_ok=True)

        # 转换每个文件夹
        for i, (name, src_path) in enumerate(folders):
            if progress_callback:
                progress_callback(i + 1, len(folders), name)

            dst_path = os.path.join(dst_root, name)
            self.convert_folder(src_path, dst_path)

        return self._results

    def get_summary(self) -> str:
        """获取转换摘要"""
        if not self._results:
            return "没有转换结果"

        success_count = sum(1 for r in self._results if r.success)
        total_count = len(self._results)
        total_files = sum(len(r.files_converted) for r in self._results)

        return (
            f"转换完成: {success_count}/{total_count} 个文件夹成功, "
            f"共 {total_files} 个文件"
        )
