"""
Async Ollama Client Module (Python)
Matches src/services/ollama.js interface and specifications.
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = os.environ.get("OLLAMA_URL") or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("DEFAULT_OLLAMA_MODEL", "qwen3:14b")
DEFAULT_TIMEOUT_SECONDS = int(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "45"))

def get_available_models(base_url: str = DEFAULT_BASE_URL, timeout: int = 10) -> List[Dict[str, Any]]:
    endpoint = f"{base_url.rstrip('/')}/api/tags"
    req = urllib.request.Request(endpoint, headers={"Accept": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                return data.get("models", [])
    except Exception as e:
        logger.warning(f"Ollama tags endpoint unreachable ({endpoint}): {e}. Using fallback models.")
        return [
            {"name": "qwen3:14b", "status": "fallback"},
            {"name": "gemma4:12b", "status": "fallback"},
            {"name": "llama3.3:8b", "status": "fallback"},
        ]

def generate_completion(
    prompt: str,
    system_prompt: str = "You are an elite strength and conditioning coach analyzing progressive overload.",
    model: str = DEFAULT_MODEL,
    context_data: Optional[Dict[str, Any]] = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    raw_json_format: bool = True
) -> Dict[str, Any]:
    endpoint = f"{base_url.rstrip('/')}/api/generate"
    payload = {
        "model": model or DEFAULT_MODEL,
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "options": {"temperature": 0.2}
    }
    if raw_json_format:
        payload["format"] = "json"

    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data_bytes,
        headers={"Content-Type": "application/json", "Accept": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            res_json = json.loads(response.read().decode("utf-8"))
            raw_response = res_json.get("response", "")
            parsed = None
            if raw_json_format:
                try:
                    import re
                    clean_res = re.sub(r"^```(?:json)?|```$", "", raw_response.strip(), flags=re.MULTILINE).strip()
                    parsed = json.loads(clean_res)
                except json.JSONDecodeError:
                    print(f"Failed to decode JSON: {raw_response}")
                    parsed = None
            return {
                "content": raw_response,
                "parsed_json": parsed,
                "model": res_json.get("model", model),
                "is_fallback": False
            }
    except Exception as e:
        logger.warning(f"Ollama call failed ({e}). Returning heuristic fallback.")
        return _fallback_overload(context_data, model, str(e))

def _fallback_overload(context_data: Optional[Dict[str, Any]], model: str, err: str) -> Dict[str, Any]:
    weight = float(context_data.get("current_weight", 0.0) if context_data else 0.0)
    target_reps = context_data.get("target_rep_range", [8, 12]) if context_data else [8, 12]
    last_reps = int(context_data.get("last_reps", 0) if context_data else 0)
    last_rpe = float(context_data.get("last_rpe", 8.0) if context_data else 8.0)

    if last_reps >= target_reps[1] and last_rpe <= 8.5:
        inc = 2.5 if weight >= 50 else 1.25
        suggested_weight = round(weight + inc, 2)
        strategy = "weight_increase"
        rationale = f"Hit top target ({last_reps} reps) @ RPE {last_rpe}. Incremented by {inc}kg."
    else:
        suggested_weight = weight
        strategy = "rep_increase"
        rationale = f"Consolidating volume at {weight}kg."

    fallback_data = {
        "suggested_weight": suggested_weight,
        "target_reps": f"{target_reps[0]}-{target_reps[1]}",
        "suggested_sets": 3,
        "strategy": strategy,
        "rationale": rationale,
        "confidence_score": 0.8,
        "offline_fallback": True
    }
    return {
        "content": json.dumps(fallback_data),
        "parsed_json": fallback_data,
        "model": f"{model} (offline fallback: {err})",
        "is_fallback": True
    }

def stream_completion(
    prompt: str,
    system_prompt: str = "You are an elite strength and conditioning coach analyzing progressive overload.",
    model: str = DEFAULT_MODEL,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    temperature: float = 0.3
):
    """
    Generator yielding token strings as they arrive from Ollama streaming endpoint.
    """
    endpoint = f"{base_url.rstrip('/')}/api/generate"
    payload = {
        "model": model or DEFAULT_MODEL,
        "prompt": prompt,
        "system": system_prompt,
        "stream": True,
        "options": {
            "temperature": temperature,
            "num_ctx": 8192
        }
    }
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data_bytes,
        headers={"Content-Type": "application/json", "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        for line in response:
            if not line:
                continue
            try:
                line_str = line.decode("utf-8").strip()
                if not line_str:
                    continue
                chunk = json.loads(line_str)
                token = chunk.get("response", "")
                done = chunk.get("done", False)
                yield {"token": token, "done": done}
                if done:
                    break
            except Exception:
                continue
