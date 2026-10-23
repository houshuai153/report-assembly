"""第三层：生成与编排。

分工：
  - 数值 / 表格 / 统计结果 → 确定性计算引擎，不经过 LLM；
  - 叙述性文本 → LLM 负责"组装和润色"，而非"生产事实"。
"""

from .deterministic import ComputedResults, compute

__all__ = ["ComputedResults", "compute"]
