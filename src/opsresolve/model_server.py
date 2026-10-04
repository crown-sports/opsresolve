"""Optional loopback model server implementing the native local chat boundary."""

from __future__ import annotations

import importlib
import threading
import time
from pathlib import Path
from typing import Any


def create_model_app(path: Path, device: str = "cuda") -> Any:
    """Load an operator-selected local model without network downloads or remote model code."""
    from fastapi import FastAPI, HTTPException

    torch = importlib.import_module("torch")
    transformers = importlib.import_module("transformers")
    tokenizer = transformers.AutoTokenizer.from_pretrained(str(path), local_files_only=True, trust_remote_code=False)
    model = (
        transformers.AutoModelForCausalLM.from_pretrained(
            str(path),
            local_files_only=True,
            trust_remote_code=False,
            torch_dtype=torch.bfloat16 if device == "cuda" else torch.float32,
            attn_implementation="sdpa",
        )
        .to(device)
        .eval()
    )
    lock = threading.Lock()
    app = FastAPI(title="OpsResolve local model", docs_url=None, redoc_url=None)

    @app.get("/health")
    def health() -> dict[str, Any]:
        """Expose runtime identity without revealing the host model-cache path."""
        return {"ready": True, "model": path.name, "device": device}

    @app.post("/api/chat")
    def chat(value: dict[str, Any]) -> dict[str, Any]:
        """Generate one bounded report under a process-local inference lock."""
        messages = value.get("messages")
        if not isinstance(messages, list) or not 1 <= len(messages) <= 3:
            raise HTTPException(400, "Expected one to three chat messages")
        for message in messages:
            if (
                not isinstance(message, dict)
                or message.get("role") not in {"system", "user", "assistant"}
                or not isinstance(message.get("content"), str)
            ):
                raise HTTPException(400, "Invalid chat message")
        if sum(len(message["content"]) for message in messages) > 48000:
            raise HTTPException(413, "Prompt exceeds the local report limit")
        with lock:
            prompt = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True, enable_thinking=False
            )
            inputs = tokenizer(prompt, return_tensors="pt").to(device)
            if inputs.input_ids.shape[-1] > 12000:
                raise HTTPException(413, "Prompt exceeds 12,000 tokens")
            started = time.perf_counter()
            with torch.inference_mode():
                output = model.generate(
                    **inputs,
                    max_new_tokens=900,
                    do_sample=False,
                    pad_token_id=tokenizer.eos_token_id,
                )
            generated = output[0, inputs.input_ids.shape[-1] :]
            answer = tokenizer.decode(generated, skip_special_tokens=True)
            return {
                "model": path.name,
                "message": {"role": "assistant", "content": answer},
                "done": True,
                "prompt_eval_count": inputs.input_ids.shape[-1],
                "eval_count": len(generated),
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            }

    return app
