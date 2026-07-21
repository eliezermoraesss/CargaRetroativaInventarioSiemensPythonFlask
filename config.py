"""
config.py — Configurações centralizadas via variáveis de ambiente para Carga Retroativa de Inventário Siemens.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Oracle ────────────────────────────────────────────────────────────────────
ORA_USER = os.getenv("ORA_USER", "SANKHYA")
ORA_PASS = os.getenv("ORA_PASS", "laranja")
ORA_DSN  = os.getenv("ORA_DSN",  "CLOUD.MULTFER.COM.BR:21159/PROD")

# ── Siemens Inventory API ─────────────────────────────────────────────────────
SIEMENS_API_URL               = os.getenv("SIEMENS_API_URL", "https://api.pos.siemens.com/qua/inventory/create_record")
SIEMENS_API_TOKEN             = os.getenv("SIEMENS_API_TOKEN", "4rwtKHdH44oa1K5Zs9kXa20NLEco8FQ95AtbJngh")
SIEMENS_DISTRIBUTOR_SENDER_ID = os.getenv("SIEMENS_DISTRIBUTOR_SENDER_ID", "40212903")

# ── Processamento ─────────────────────────────────────────────────────────────
BATCH_SIZE    = int(os.getenv("BATCH_SIZE", "1000"))
RETRY_MAX     = int(os.getenv("RETRY_MAX", "3"))
RETRY_BACKOFF = int(os.getenv("RETRY_BACKOFF", "2"))   # segundos (dobra a cada tentativa)

# ── Flask ─────────────────────────────────────────────────────────────────────
FLASK_PORT  = int(os.getenv("FLASK_PORT", "5001"))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"
