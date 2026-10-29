import os
import logging
from typing import Any, Iterator, Union
from transformers import PreTrainedTokenizerFast
from transformers.convert_slow_tokenizer import bytes_to_unicode

from .tool_declaration_ts import encode_tools_to_typescript_style

logger = logging.getLogger(__name__)


def deep_sort_dict(obj: Any) -> Any:
    """Deep sort dict keys recursively to ensure stable hashing and tokenization."""
    if isinstance(obj, dict):
        return {k: deep_sort_dict(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [deep_sort_dict(item) for item in obj]
    return obj


class CustomFastTokenizer(PreTrainedTokenizerFast):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Byte-to-unicode mapping for downstream tasks requiring single-byte decoding
        self.byte_encoder = bytes_to_unicode()
        self.byte_decoder = {v: k for k, v in self.byte_encoder.items()}

    @staticmethod
    def _split_whitespaces_or_nonwhitespaces(
        s: str, max_consecutive_slice_len: int
    ) -> Iterator[str]:
        current_slice_len = 0
        current_slice_is_space = s[0].isspace() if len(s) > 0 else False
        slice_start = 0

        for i in range(len(s)):
            is_now_space = s[i].isspace()
            if current_slice_is_space ^ is_now_space:
                current_slice_len = 1
                current_slice_is_space = is_now_space
            else:
                current_slice_len += 1
                if current_slice_len > max_consecutive_slice_len:
                    yield s[slice_start:i]
                    slice_start = i
                    current_slice_len = 1
        yield s[slice_start:]

    def encode(self, text: Union[str, Any], *args, **kwargs) -> list[int]:
        if not isinstance(text, str) or args or kwargs:
            return super().encode(text, *args, **kwargs)

        # Chunking thresholds to prevent OOM on very long texts
        MAX_ENCODE_CHARS = 400_000
        MAX_NO_WHITESPACES_CHARS = 25_000

        all_substrs = []
        for i in range(0, len(text), MAX_ENCODE_CHARS):
            chunk = text[i : i + MAX_ENCODE_CHARS]
            all_substrs.extend(
                self._split_whitespaces_or_nonwhitespaces(
                    chunk, MAX_NO_WHITESPACES_CHARS
                )
            )

        t = []
        for substr in all_substrs:
            t.extend(super().encode(substr, add_special_tokens=False))

        return t

    def apply_chat_template(self, conversation, tools=None, **kwargs):
        tools = deep_sort_dict(tools)

        if tools:
            try:
                tools_ts_str = encode_tools_to_typescript_style(tools)
                kwargs["tools_ts_str"] = tools_ts_str
            except Exception as e:
                logger.error(f"Failed to convert tools to TypeScript style: {e}")

        return super().apply_chat_template(
            conversation=conversation, tools=tools, **kwargs
        )
