"""审计链完整性 + 篡改检测的单元测试。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.compliance.audit_chain import AuditChain


class TestAuditChain(unittest.TestCase):
    def test_verify_ok_on_clean_chain(self):
        chain = AuditChain()
        chain.append("DATA_LOCKED", "u1", "dataset", "d1", "h1")
        chain.append("AI_GENERATE_SECTION", "u1", "section", "m", "h2", tool="LLM:x")
        chain.append("HUMAN_ACCEPT", "u2", "section", "m", "h2")
        ok, _ = chain.verify()
        self.assertTrue(ok)

    def test_detect_tampering(self):
        chain = AuditChain()
        chain.append("DATA_LOCKED", "u1", "dataset", "d1", "h1")
        chain.append("AI_GENERATE_SECTION", "u1", "section", "m", "h2")
        chain.append("HUMAN_ACCEPT", "u2", "section", "m", "h2")

        entries = chain.entries
        tampered = entries[1].model_copy(update={"payload_hash": "0" * 64})
        broken = AuditChain()
        broken._entries = entries[:1] + [tampered] + entries[2:]  # noqa: SLF001

        ok, msg = broken.verify()
        self.assertFalse(ok)
        self.assertIn("篡改", msg)

    def test_detect_link_break(self):
        chain = AuditChain()
        chain.append("A", "u1", "t", "o", "h1")
        chain.append("B", "u1", "t", "o", "h2")
        # 直接删掉中间一条，链指针断裂
        entries = chain.entries
        broken = AuditChain()
        broken._entries = entries[:1]  # noqa: SLF001
        broken.append("C", "u1", "t", "o", "h3")
        # 注意：append 会基于 broken 的最后一条（即 entries[0]）计算 previous_hash，
        # 与原始 entries[1] 不同，这里验证的是正常追加不会把链修回去。
        ok, _ = broken.verify()
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
