"""
SparkyFitness Client Module (Python)
Matches src/services/sparky.js interface and specifications.
"""

import os
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime, date
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = os.environ.get("SPARKY_URL") or os.environ.get("SPARKY_BASE_URL", "http://localhost:8080")
DEFAULT_API_TOKEN = os.environ.get("SPARKY_API_TOKEN", "")
DEFAULT_TIMEOUT_SECONDS = int(os.environ.get("SPARKY_TIMEOUT_SECONDS", "15"))

def format_date_key(d: Any) -> str:
    if isinstance(d, (datetime, date)):
        return d.strftime("%Y-%m-%d")
    return str(d).split("T")[0] if d else datetime.utcnow().strftime("%Y-%m-%d")

def get_daily_summary(
    target_date: Any,
    base_url: str = DEFAULT_BASE_URL,
    api_token: str = DEFAULT_API_TOKEN,
    timeout: int = DEFAULT_TIMEOUT_SECONDS
) -> Dict[str, Any]:
    date_str = format_date_key(target_date)
    endpoint = f"{base_url.rstrip('/')}/api/v1/nutrition/summary?date={date_str}"

    headers = {"Accept": "application/json"}
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"

    req = urllib.request.Request(endpoint, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                payload = json.loads(response.read().decode("utf-8"))
                data = payload.get("data", payload.get("summary", payload))
                return {
                    "date": date_str,
                    "calories": float(data.get("calories", data.get("total_calories", 0.0))),
                    "protein_grams": float(data.get("protein", data.get("protein_grams", 0.0))),
                    "carbs_grams": float(data.get("carbs", data.get("total_carbs", 0.0))),
                    "fat_grams": float(data.get("fat", data.get("total_fat", 0.0))),
                    "water_ml": float(data.get("water", data.get("water_ml", 0.0))),
                    "raw": payload,
                    "is_fallback": False
                }
    except Exception as e:
        logger.warning(f"SparkyFitness API unreachable ({endpoint}): {e}. Returning safe mock fallback.")

    return {
        "date": date_str,
        "calories": 0.0,
        "protein_grams": 0.0,
        "carbs_grams": 0.0,
        "fat_grams": 0.0,
        "water_ml": 0.0,
        "raw": {"error": str(e) if 'e' in locals() else "Timeout", "notice": "Offline fallback"},
        "is_fallback": True
    }
