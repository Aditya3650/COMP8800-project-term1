# src/llm_infer.py
import os
import torch
from typing import Dict, Any
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel, PeftConfig

import os

import re

TRIAGE_TEMPLATE = """You are a Windows security log triage assistant.

Your audience is a junior IT support technician with limited security knowledge.
Explain things clearly and in simple, non-technical language.

When you see the event details, produce a short triage note with:
- A plain-English explanation of what happened.
- Whether this looks routine/normal or potentially suspicious.
- One simple recommendation for what, if anything, the technician should do.

Output format (exactly three sentences):

Explanation: <what this event means in plain English, no EventID/provider names or long IDs>
Assessment: <say if this looks routine/normal, or potentially suspicious/high risk, and why>
Recommended Action: <one short action, or "None – informational only.">

Do NOT repeat long numeric IDs like S-1-5-21-... or hex values.
Do NOT dump key=value fields such as Id=..., ProviderName=..., LevelDisplayName=..., __Channel=..., or Message_clean=...
Do NOT echo usernames + passwords literally — mask sensitive fields if needed.

Event details:
Log name: {log_type}
EventID: {event_id}
Source: {source}
Time: {time}
Message: {message}
"""



_sid_pattern = re.compile(r"S-\d(-\d+)+")
_hex_pattern = re.compile(r"0x[0-9a-fA-F]+")

def _clean_message(msg: str) -> str:
    # Collapse whitespace
    msg = re.sub(r"\s+", " ", msg).strip()
    # Mask SIDs and hex values so the model doesn't parrot them
    msg = _sid_pattern.sub("[SID]", msg)
    msg = _hex_pattern.sub("[HEX]", msg)
    # (optional) mask things that look like "password = ..."
    msg = re.sub(r"password\s*[:=]\s*\S+", "password=[MASKED]", msg, flags=re.IGNORECASE)
    return msg


os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

import torch
try:
    torch.set_num_threads(2)
except Exception:
    pass

# project paths
REPO_ROOT     = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ADAPTER_DIR   = os.environ.get("LLM_ADAPTER_DIR", os.path.join(REPO_ROOT, "logtriage-phi-mini"))
LOCAL_BASE_DIR = os.path.join(REPO_ROOT, "models", "phi-3.5-mini-instruct")  # put base model here
BASE_FALLBACK  = "microsoft/phi-3.5-mini-instruct"                            # fallback if local missing

# keep CPU reasonable on Windows
try:
    torch.set_num_threads(4)
except Exception:
    pass

_tok = None
_model = None

def _pick_base_path(saved_base: str | None) -> str:
    """
    Prefer local folder with model files. If it doesn't exist, use saved_base or fallback HF id.
    """
    if os.path.isdir(LOCAL_BASE_DIR):
        return LOCAL_BASE_DIR
    return saved_base or BASE_FALLBACK

def _load_once():
    global _tok, _model
    if _model is not None:
        return

    print("[llm] Adapter dir:", ADAPTER_DIR, "exists:", os.path.isdir(ADAPTER_DIR))
    peft_cfg = PeftConfig.from_pretrained(ADAPTER_DIR)
    base_path = _pick_base_path(peft_cfg.base_model_name_or_path)
    print("[llm] base path:", base_path)

    use_cuda  = torch.cuda.is_available()
    dtype     = torch.float16 if use_cuda else torch.float32
    device_map = "auto" if use_cuda else None
    print("[llm] cuda:", use_cuda, "dtype:", dtype, "device_map:", device_map)

    # load tokenizer + base strictly from local if we have a local dir
    local_only = os.path.isdir(base_path)
    _tok = AutoTokenizer.from_pretrained(base_path, use_fast=True, local_files_only=local_only)
    base = AutoModelForCausalLM.from_pretrained(
        base_path,
        torch_dtype=dtype,
        device_map=device_map,
        trust_remote_code=True,
        local_files_only=local_only
    )
    try:
        base.config.attn_implementation = "eager"
    except Exception:
        pass

    _model = PeftModel.from_pretrained(base, ADAPTER_DIR)
    print("[llm] model+adapter loaded.")

def build_input_from_row(row: dict) -> str:
    log_type = row.get("log_type") or row.get("log") or "Unknown"
    event_id = row.get("event_id", "Unknown")
    source = row.get("source", "Unknown")
    time_str = row.get("time", "Unknown")

    msg = row.get("message") or []
    if isinstance(msg, list):
        msg = " | ".join(m for m in msg if m)
    msg = msg or "(no message)"
    msg = _clean_message(msg)

    # MAX_MSG_CHARS = 600
    # if len(msg) > MAX_MSG_CHARS:
    #     msg = msg[:MAX_MSG_CHARS] + " [message truncated]"

    return TRIAGE_TEMPLATE.format(
        log_type=log_type,
        event_id=event_id,
        source=source,
        time=time_str,
        message=msg,
    )


def generate_triage(input_str: str, temperature: float = 0.0, max_new_tokens: int = 80) -> str:
    _load_once()
    prompt = input_str  # TRIAGE_TEMPLATE already includes instructions

    device = next(_model.parameters()).device
    with torch.inference_mode():
        ids = _tok(prompt, return_tensors="pt").to(device)
        out = _model.generate(
            **ids,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            temperature=temperature,
            eos_token_id=_tok.eos_token_id,
        )

    text = _tok.decode(out[0], skip_special_tokens=True)

    # Strip the prompt if it’s echoed
    if text.startswith(prompt):
        text = text[len(prompt):].strip()

    # Remove obvious noisy key=value junk if it sneaks in
    noisy_patterns = [
        r"Id=\d+\b",
        r"ProviderName=[^\s]+",
        r"LevelDisplayName=[^\s]+",
        r"TimeCreated=[^\n]+",
        r"__Channel=[^\s]+",
        r"Message_clean=[^\n]+",
    ]
    for pat in noisy_patterns:
        text = re.sub(pat, "", text)

    return text.strip()


# self-test runner (optional)
if __name__ == "__main__":
    print("[llm] self-test starting…")
    try:
        _load_once()
        print("[llm] model+adapter loaded OK")
        sample = ("Id=4625 ProviderName=Microsoft-Windows-Security-Auditing "
                  "LevelDisplayName=Failure TimeCreated=2025-10-31T06:35:44Z "
                  "__Channel=Security Message_clean=Unknown user name or bad password")
        out = generate_triage(sample)
        print("[llm] sample output:\n", out[:400], "…")
    except Exception as e:
        import traceback
        print("[llm] ERROR:", e)
        print(traceback.format_exc())
