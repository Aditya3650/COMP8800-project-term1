# src/llm_infer.py
import os
import torch
from typing import Dict, Any
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel, PeftConfig


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ADAPTER_DIR = os.environ.get("LLM_ADAPTER_DIR", os.path.join(REPO_ROOT, "logtriage-phi-mini"))
BASE_FALLBACK = "microsoft/phi-3-mini-4k-instruct"  # lighter fallback if base name not saved in adapter

_tok = None
_model = None

def _load_once():
    global _tok, _model
    if _model is not None:
        return
    peft_cfg = PeftConfig.from_pretrained(ADAPTER_DIR)
    base_name = peft_cfg.base_model_name_or_path or BASE_FALLBACK

    _tok = AutoTokenizer.from_pretrained(base_name, use_fast=True)
    dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    device_map = "auto" if torch.cuda.is_available() else None

    base = AutoModelForCausalLM.from_pretrained(
        base_name,
        torch_dtype=dtype,
        device_map=device_map,
        trust_remote_code=True,
    )
    try:
        base.config.attn_implementation = "eager"
    except Exception:
        pass

    _model = PeftModel.from_pretrained(base, ADAPTER_DIR)

def build_input_from_row(r: Dict[str, Any]) -> str:
    """
    Convert your DB row dict → the 'input' string your fine-tuned model expects.
    (Matches how we trained: key=value ... Message_clean=...)
    """
    msg = " | ".join(r.get("message", []) or [])
    parts = [
        f"Id={r.get('event_id','')}",
        f"ProviderName={r.get('source','')}",
        "LevelDisplayName=Information",
        f"TimeCreated={r.get('time','')}",
        f"__Channel={r.get('log_type','')}",
        f"Message_clean={msg[:800]}",
    ]
    return " ".join(parts)

def generate_triage(input_str: str, temperature: float = 0.15, max_new_tokens: int = 220) -> str:
    _load_once()
    prompt = f"""### Instruction:
Rewrite the event for an on-call runbook with severity and actions.

### Input:
{input_str}

### Response:
"""
    ids = _tok(prompt, return_tensors="pt").to(next(_model.parameters()).device)
    out = _model.generate(
        **ids,
        max_new_tokens=max_new_tokens,
        do_sample=True,
        temperature=temperature,
        top_p=0.9,
    )
    text = _tok.decode(out[0], skip_special_tokens=True)
    return text.split("### Response:")[-1].strip()
