"""
db_oracle.py — Conexão e consultas ao banco Oracle para Inventário Siemens.
Driver thin (sem necessidade de Oracle Client instant).
"""
import logging
import oracledb
from datetime import date
from config import ORA_USER, ORA_PASS, ORA_DSN, SIEMENS_DISTRIBUTOR_SENDER_ID

logger = logging.getLogger(__name__)

# Query A: Dados da Filial / Distribuidor
QUERY_BRANCH = """
SELECT NVL(TO_CHAR(:sender_id), '40212903')
           AS distributor_sender_id,
       EMP.RAZAOSOCIALCOMPLETA
           AS distributor_order_taking_branch_name,
       EMP.CGC
           AS distributor_order_taking_branch_id
  FROM TSIEMP EMP
 WHERE CODEMP = 3
"""

# Query B: Dados de Inventário / Estoque dos Produtos Siemens
QUERY_ITEMS = """
SELECT NVL (
             TO_CHAR (
                 (SELECT MAX (CAB.DTNEG)
                   FROM TGFITE ITE
                        LEFT OUTER JOIN TGFCAB CAB ON CAB.NUNOTA = ITE.NUNOTA
                  WHERE     CAB.CODTIPOPER IN (2015,
                                               2021,
                                               5213,
                                               5222)
                        AND CAB.STATUSNOTA = 'L'
                        AND ITE.CODPROD = PRO.CODPROD),
                 'YYYY-MM-DD'),
             '')
             AS distributor_inventory_date,
         PRO.REFFORN
             AS vendor_item_number,
         ''
             AS vendor_item_options,
         (SELECT   FC_RETORNA_ESTOQUE_MTF (PRO.CODPROD,
                                           0,
                                           'DI',
                                           1001,
                                           NULL)
                 + FC_RETORNA_ESTOQUE_MTF (PRO.CODPROD,
                                           0,
                                           'DI',
                                           1010,
                                           NULL)
            FROM DUAL)
             AS quantity,
         PRO.CODVOL
             AS quantity_unit_of_measure,
         PRO.REFERENCIA
             AS upc_ean,
         (SELECT CASE WHEN MAX (ESTOQUE) = 'S' THEN 'Y' ELSE 'N' END
            FROM AD_PLANCOMP
           WHERE     ESTOQUE = 'S'
                 AND CODPROD = PRO.CODPROD
                 AND TRUNC (DHINC) = (SELECT MAX (TRUNC (DHINC))
                                        FROM AD_PLANCOMP
                                       WHERE CODPROD = PRO.CODPROD))
             AS stock_item,
         ''
             AS product_deeplink
    FROM TGFPRO PRO
   WHERE     PRO.MARCA = 'SIEMENS'
         AND PRO.ATIVO = 'S'
         AND PRO.CODPARCFORN = 52559
         AND PRO.AD_DHINC BETWEEN TO_DATE(:start_date, 'DD/MM/YYYY')
                              AND TO_DATE(:end_date || ' 23:59:59', 'DD/MM/YYYY HH24:MI:SS')
ORDER BY PRO.CODPROD ASC
"""


def get_connection():
    """Cria e retorna uma conexão Oracle (thin mode — sem Oracle Client)."""
    logger.info("Conectando ao Oracle: %s", ORA_DSN)
    conn = oracledb.connect(user=ORA_USER, password=ORA_PASS, dsn=ORA_DSN)
    logger.info("Conexão estabelecida com sucesso.")
    return conn


def _str_or_empty(val) -> str:
    """Retorna string sem espaços ou '' se for None / 'N/A'."""
    if val is None or val == 'N/A':
        return ""
    return str(val).strip()


def _format_upc_ean(val):
    """Converte upc_ean para int se for puramente numérico, senão retorna 0 se vazio ou inválido."""
    if val is None or val == '' or val == 'N/A':
        return 0
    s = str(val).strip()
    if not s:
        return 0
    if s.isdigit():
        try:
            return int(s)
        except ValueError:
            return 0
    return 0


def fetch_records(start_date: str = None, end_date: str = None, progress_callback=None):
    """
    Executa Query A (filial) e Query B (inventário) no Oracle e combina em uma lista de registros JSON.

    Args:
        start_date: Data inicial no formato DD/MM/YYYY
        end_date: Data final no formato DD/MM/YYYY
        progress_callback: callable(msg: str)

    Returns:
        list[dict]: lista de objetos prontos para envio no payload de inventário.
    """
    if not start_date:
        start_date = '31/07/2019'
    if not end_date:
        end_date = date.today().strftime('%d/%m/%Y')

    conn = get_connection()
    cursor = None
    try:
        cursor = conn.cursor()

        # 1. Executa Query A para buscar dados da filial
        logger.info("Executando Query A (dados da filial)...")
        cursor.execute(QUERY_BRANCH, {"sender_id": SIEMENS_DISTRIBUTOR_SENDER_ID})
        branch_cols = [col[0].lower() for col in cursor.description]
        branch_row = cursor.fetchone()

        branch_info = {}
        if branch_row:
            for col, val in zip(branch_cols, branch_row):
                branch_info[col] = _str_or_empty(val)
        else:
            branch_info = {
                "distributor_sender_id": SIEMENS_DISTRIBUTOR_SENDER_ID,
                "distributor_order_taking_branch_name": "MULTFER SOLUCOES PARA INDUSTRIA E CONSTRUCAO LTDA",
                "distributor_order_taking_branch_id": "64580707000954"
            }

        logger.info("Filial obtida: %s (%s)", branch_info.get("distributor_order_taking_branch_name"), branch_info.get("distributor_order_taking_branch_id"))

        # 2. Executa Query B para buscar itens de inventário
        logger.info("Executando Query B (inventário) para período AD_DHINC %s — %s...", start_date, end_date)
        cursor.execute(QUERY_ITEMS, {"start_date": start_date, "end_date": end_date})

        item_cols = [col[0].lower() for col in cursor.description]
        records = []

        for row in cursor:
            raw_item = {}
            for col, val in zip(item_cols, row):
                if hasattr(val, 'read'):
                    val = val.read()
                elif hasattr(val, 'strftime'):
                    val = str(val)
                raw_item[col] = val

            # Formata e combina com dados da filial conforme contrato da API Siemens Inventory
            record = {
                "distributor_sender_id": _str_or_empty(branch_info.get("distributor_sender_id")) or SIEMENS_DISTRIBUTOR_SENDER_ID,
                "distributor_order_taking_branch_name": _str_or_empty(branch_info.get("distributor_order_taking_branch_name")),
                "distributor_order_taking_branch_id": _str_or_empty(branch_info.get("distributor_order_taking_branch_id")),
                "distributor_inventory_date": _str_or_empty(raw_item.get("distributor_inventory_date")),
                "vendor_item_number": _str_or_empty(raw_item.get("vendor_item_number")),
                "vendor_item_options": _str_or_empty(raw_item.get("vendor_item_options")),
                "quantity": int(raw_item.get("quantity") or 0) if isinstance(raw_item.get("quantity"), (int, float)) else 0,
                "quantity_unit_of_measure": _str_or_empty(raw_item.get("quantity_unit_of_measure")),
                "upc_ean": _format_upc_ean(raw_item.get("upc_ean")),
                "stock_item": _str_or_empty(raw_item.get("stock_item")) or "N",
                "product_deeplink": _str_or_empty(raw_item.get("product_deeplink"))
            }
            records.append(record)

        logger.info("Total de registros de inventário encontrados: %d", len(records))
        if progress_callback:
            progress_callback(f"Oracle: {len(records)} registros de inventário carregados.")
        return records

    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        try:
            conn.close()
        except Exception:
            pass
