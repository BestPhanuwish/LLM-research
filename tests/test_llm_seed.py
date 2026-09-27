"""Tests for utils.utils.get_llm()'s optional best-effort reproducible seed."""

from unittest import TestCase
from unittest.mock import patch

from yacs.config import CfgNode

from utils import utils


def make_config(seed=None):
    config = CfgNode(new_allowed=True)
    config.max_token = 300
    config.temperature = 0.5
    config.max_retries = 1
    if seed is not None:
        config.seed = seed
    return config


class GetLlmSeedTests(TestCase):
    def test_no_seed_leaves_model_kwargs_empty(self):
        with patch("utils.utils.ChatOpenAI") as fake_chat_openai:
            utils.get_llm("gpt-4o-mini", make_config(), logger=None, api_key="key", api_base="https://api.openai.com/v1")

        self.assertEqual({}, fake_chat_openai.call_args.kwargs["model_kwargs"])

    def test_seed_is_forwarded_via_model_kwargs(self):
        with patch("utils.utils.ChatOpenAI") as fake_chat_openai:
            utils.get_llm(
                "gpt-4o-mini", make_config(seed=42), logger=None,
                api_key="key", api_base="https://api.openai.com/v1",
            )

        self.assertEqual({"seed": 42}, fake_chat_openai.call_args.kwargs["model_kwargs"])

    def test_null_seed_in_config_leaves_model_kwargs_empty(self):
        config = make_config()
        config.seed = None

        with patch("utils.utils.ChatOpenAI") as fake_chat_openai:
            utils.get_llm("gpt-4o-mini", config, logger=None, api_key="key", api_base="https://api.openai.com/v1")

        self.assertEqual({}, fake_chat_openai.call_args.kwargs["model_kwargs"])


if __name__ == "__main__":
    import unittest

    unittest.main()
