"""配置：模型端点、合规参数等。

demo 默认使用 mock LLM，设置环境变量可切换到 OpenAI 兼容的私有化部署接口：

    LLM_PROVIDER=openai_compatible
    LLM_BASE_URL=http://your-internal-endpoint
    LLM_API_KEY=...
    LLM_MODEL_ID=qwen2.5-14b-instruct

生产环境可进一步用 pydantic-settings 的 BaseSettings 直接绑定环境变量与 .env。
"""

from __future__ import annotations

import os

from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    provider: str = Field(default="mock", description="mock | openai_compatible")
    base_url: str = ""
    api_key: str = ""
    # 私有化部署：7B~14B 指令微调模型即可，关键是 prompt 里把候选文本给足
    model_id: str = "mock-llm-1"


class Config(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    loq: float = 1.0                    # 定量下限 (ng/mL)
    terminal_points: int = 3            # 终末相用于估算 kel 的点数
    top_k: int = 5                      # 检索候选数
    audit_store: str = ""               # 审计链持久化路径，空字符串 = 内存

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            llm=LLMConfig(
                provider=os.getenv("LLM_PROVIDER", "mock"),
                base_url=os.getenv("LLM_BASE_URL", ""),
                api_key=os.getenv("LLM_API_KEY", ""),
                model_id=os.getenv("LLM_MODEL_ID", "mock-llm-1"),
            ),
            loq=float(os.getenv("LOQ", "1.0")),
            terminal_points=int(os.getenv("TERMINAL_POINTS", "3")),
            top_k=int(os.getenv("TOP_K", "5")),
            audit_store=os.getenv("AUDIT_STORE", ""),
        )
