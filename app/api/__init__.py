"""可选：FastAPI 审核工作台接口。

核心 demo（demo_run.py）不依赖 FastAPI，零外部依赖即可运行。
本模块提供审核工作台的最小接口示例，用于把人工审核节点接到前端。
"""

from .app import create_app

__all__ = ["create_app"]
