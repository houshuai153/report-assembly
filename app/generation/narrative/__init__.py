"""叙述生成：LLM 负责"组装和润色"，而非"生产事实"。

LLM 接收的输入：已填充的数值表格 + 检索到的候选文本片段 + 研究特异性变量。
它的任务是选择、拼接、调整措辞，使文本与数值一致、与模板结构对齐。
"""

from .orchestrator import SectionDraft, SectionOrchestrator

__all__ = ["SectionDraft", "SectionOrchestrator"]
