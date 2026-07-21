"""
siemens_api.py — Integração com a API Siemens Point of Sales (Inventário).
Envia batches de até 1000 registros via POST com retry e delay entre requisições.
"""
import time
import logging
import requests
import json
from config import SIEMENS_API_URL, SIEMENS_API_TOKEN, SIEMENS_DISTRIBUTOR_SENDER_ID, RETRY_MAX, RETRY_BACKOFF

logger = logging.getLogger(__name__)

# Delay seguro entre o envio de BATCHES (em segundos)
BATCH_DELAY = 2.0


def _build_headers() -> dict:
    """Monta os headers HTTP exigidos pela API de Inventário Siemens."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "x-api-key": SIEMENS_API_TOKEN,
        "distributor_sender_id": SIEMENS_DISTRIBUTOR_SENDER_ID
    }
    return headers


def send_batch(records: list, batch_index: int = 0, dry_run: bool = False) -> dict:
    """
    Envia um batch de registros de inventário para a API Siemens.

    Args:
        records:      Lista de dicionários (até 1000 registros).
        batch_index:  Índice do batch (para logging).
        dry_run:      Se True, simula o envio sem fazer requisição real.

    Returns:
        dict com keys: success (bool), status_code (int|None),
                        response_body (dict|str|None), error (str|None).
    """
    if not dry_run and batch_index > 1:
        time.sleep(BATCH_DELAY)

    payload = records
    headers = _build_headers()

    if dry_run:
        logger.info(f"[DRY-RUN] Batch {batch_index} ({len(records)} registros) — Pronto para envio.")
        if len(records) > 0:
            preview_count = min(2, len(records))
            preview = json.dumps(payload[:preview_count], indent=2, ensure_ascii=False, default=str)
            if len(records) > 2:
                preview = preview[:-1] + f"  ... (e mais {len(records)-2} registros JSON) ...\n]"
            logger.info(f"[DRY-RUN] Estrutura do Array JSON Payload de Inventário:\n{preview}")
        return {"success": True, "status_code": 201, "response_body": {"dry_run": True}, "error": None}

    last_error = None
    for attempt in range(1, RETRY_MAX + 1):
        try:
            logger.info(f"Enviando Batch {batch_index} com {len(records)} registros (tentativa {attempt}/{RETRY_MAX})…")

            if len(records) > 0:
                preview_count = min(2, len(records))
                preview = json.dumps(payload[:preview_count], indent=2, ensure_ascii=False, default=str)
                if len(records) > 2:
                    preview = preview[:-1] + f"  ... (e mais {len(records)-2} registros JSON) ...\n]"
                logger.info(f"Estrutura do Array JSON Payload:\n{preview}")

            resp = requests.post(
                SIEMENS_API_URL,
                json=payload,
                headers=headers,
                timeout=120,
            )

            if resp.status_code in (200, 201):
                logger.info(f"✅ Batch {batch_index} aceito (Status {resp.status_code}).")
                try:
                    body = resp.json()
                except Exception:
                    body = resp.text
                return {"success": True, "status_code": resp.status_code, "response_body": body, "error": None}

            logger.warning(f"⚠️ Batch {batch_index} retornou status {resp.status_code}: {resp.text[:500]}")
            last_error = f"HTTP {resp.status_code}: {resp.text[:300]}"

        except Exception as exc:
            last_error = str(exc)
            logger.warning(f"❌ Erro no Batch {batch_index} (tentativa {attempt}): {exc}")

        if attempt < RETRY_MAX:
            time.sleep(RETRY_BACKOFF ** attempt)

    return {"success": False, "status_code": None, "response_body": None, "error": last_error}
