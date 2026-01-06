"""统一日志管理模块"""

import os
import sys
import logging
import traceback
from datetime import datetime
from typing import Optional, Callable

_current_log_path: Optional[str] = None

DEFAULT_LOG_DIR = "logs"
DEFAULT_LOG_PREFIX = "ep_assetmaker"


def _get_exe_dir() -> str:
    """获取 EXE 所在目录"""
    return os.path.dirname(os.path.abspath(sys.argv[0]))


def get_log_file_path() -> Optional[str]:
    """获取当前日志文件路径"""
    return _current_log_path


def _create_log_file(log_dir: str, log_prefix: str) -> str:
    """创建日志文件并返回路径"""
    global _current_log_path

    if not os.path.isabs(log_dir):
        log_dir = os.path.join(_get_exe_dir(), log_dir)

    os.makedirs(log_dir, exist_ok=True)
    log_filename = f"{log_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_path = os.path.join(log_dir, log_filename)
    _current_log_path = log_path

    return log_path


def _get_formatter() -> logging.Formatter:
    return logging.Formatter(
        "%(asctime)s [%(name)s] [%(threadName)s] [%(levelname)s] %(message)s"
    )


def _cli_excepthook(exc_type, exc_value, exc_traceback, old_hook=sys.excepthook):
    """CLI 模式的异常钩子"""
    logging.error("程序发生了错误，以下为详细信息：")
    logging.error("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
    logging.error("请按回车键继续....")
    input()
    sys.exit(0)


def _gui_excepthook(exc_type, exc_value, exc_traceback, old_hook=sys.excepthook):
    """GUI 模式的异常钩子"""
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    logging.error("程序发生了错误，以下为详细信息：")
    logging.error(error_msg)

    try:
        from PyQt5.QtWidgets import QMessageBox, QApplication

        # 确保 QApplication 实例存在
        app = QApplication.instance()
        if app is not None:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle("程序错误")
            msg_box.setText("程序发生了未处理的错误")
            msg_box.setDetailedText(error_msg)
            msg_box.exec_()
    except ImportError:
        print(f"程序发生了错误：\n{error_msg}", file=sys.stderr)
    except Exception as e:
        print(f"程序发生了错误：\n{error_msg}", file=sys.stderr)
        print(f"显示错误对话框时出错：{e}", file=sys.stderr)


def setup_cli_logger(
    log_dir: str = DEFAULT_LOG_DIR,
    log_prefix: str = DEFAULT_LOG_PREFIX,
    log_level: int = logging.DEBUG
) -> str:
    """为 CLI 模式设置日志记录器"""
    log_path = _create_log_file(log_dir, log_prefix)
    log_filename = os.path.basename(log_path)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()

    formatter = _get_formatter()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    sys.excepthook = _cli_excepthook

    return log_filename


def setup_gui_logger(
    log_dir: str = DEFAULT_LOG_DIR,
    log_prefix: str = DEFAULT_LOG_PREFIX,
    log_level: int = logging.DEBUG,
    enable_console: bool = True
) -> str:
    """为 GUI 模式设置日志记录器"""
    log_path = _create_log_file(log_dir, log_prefix)
    log_filename = os.path.basename(log_path)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()

    formatter = _get_formatter()

    if enable_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    sys.excepthook = _gui_excepthook

    return log_filename


def add_custom_handler(handler: logging.Handler, use_default_formatter: bool = True) -> None:
    """添加自定义日志处理器"""
    if use_default_formatter:
        handler.setFormatter(_get_formatter())

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)


def remove_handler(handler: logging.Handler) -> None:
    """移除指定的日志处理器"""
    root_logger = logging.getLogger()
    root_logger.removeHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的日志记录器"""
    return logging.getLogger(name)
