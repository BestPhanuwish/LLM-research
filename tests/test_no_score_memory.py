"""Tests for the no-op importance-scoring memory used in controlled trials."""

from unittest import TestCase
from unittest.mock import Mock

from agents.character import NoScoreGenerativeAgentMemory


class PoisonLLM:
    """Raises if invoked; proves no model call happens during scoring."""

    def get_num_tokens(self, prompt):
        raise AssertionError("LLM should not be called for a no-op importance score")

    def __getattr__(self, name):
        raise AssertionError(
            f"LLM.{name} should not be called for a no-op importance score"
        )


class NoScoreGenerativeAgentMemoryTests(TestCase):
    def test_score_memory_importance_returns_zero_without_a_model_call(self):
        memory = NoScoreGenerativeAgentMemory.construct(
            llm=PoisonLLM(),
            memory_retriever=Mock(),
        )

        score = memory._score_memory_importance("Neville Longbottom: Keep quiet.")

        self.assertEqual(0.0, score)

    def test_add_memory_never_triggers_reflection_regardless_of_call_count(self):
        retriever = Mock()
        retriever.add_documents.return_value = ["doc-id"]
        memory = NoScoreGenerativeAgentMemory.construct(
            llm=PoisonLLM(),
            memory_retriever=retriever,
            reflection_threshold=10,
            importance_weight=0.1,
        )

        for _ in range(50):
            memory.add_memory("Neville Longbottom: Keep quiet.")

        self.assertEqual(0.0, memory.aggregate_importance)
        self.assertEqual(50, retriever.add_documents.call_count)


if __name__ == "__main__":
    import unittest

    unittest.main()
