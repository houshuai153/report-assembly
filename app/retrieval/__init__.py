"""第二层：知识与检索。

叙述性文本不能凭空生成，必须有受控的模板和历史依据。
关键设计不是"生成"，而是"检索 + 选择"：系统召回已批准文本片段作为候选，
由模型/人类从中选择，而非直接输出一段完整叙述。
"""

from .corpus import build_corpus
from .hybrid_search import Retriever

__all__ = ["build_corpus", "Retriever"]
