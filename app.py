"""
app.py — Servidor Flask principal do dashboard de Carga Retroativa de Inventário Siemens.
Processamento em Batches de no máximo 1000 registros.
"""
import json
import logging
import queue
import threading
import time
from datetime import datetime

from flask import Flask, Response, jsonify, render_template, request

from config import BATCH_SIZE, FLASK_DEBUG, FLASK_PORT
from db_oracle import fetch_records
from siemens_api import send_batch

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ── Estado global do processo ─────────────────────────────────────────────────
_state = {
    "running": False,
    "dry_run": False,
    "started_at": None,
    "finished_at": None,
    "total": 0,
    "processed": 0,
    "success": 0,
    "errors": 0,
    "batches_total": 0,
    "batches_done": 0,
    "log": [],
    "failed_batches": [],
    "stop_requested": False,
}
_state_lock = threading.RLock()

# SSE: fila de eventos para clientes conectados
_sse_clients: list[queue.Queue] = []
_sse_lock = threading.Lock()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _push_log(level: str, message: str):
    """Adiciona entrada ao log e emite evento SSE."""
    entry = {"time": datetime.now().strftime("%H:%M:%S"), "level": level, "message": message}
    with _state_lock:
        _state["log"].append(entry)
        if len(_state["log"]) > 500:
            _state["log"] = _state["log"][-500:]

    _broadcast("log", entry)
    if level == "ERROR":
        logger.error(message)
    elif level == "WARNING":
        logger.warning(message)
    else:
        logger.info(message)


def _broadcast(event_type: str, data: dict):
    """Envia evento SSE para todos os clientes."""
    payload = json.dumps(data, ensure_ascii=False, default=str)
    message = f"event: {event_type}\ndata: {payload}\n\n"
    dead = []
    with _sse_lock:
        for q in _sse_clients:
            try:
                q.put_nowait(message)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _sse_clients.remove(q)


def _emit_progress():
    """Emite evento de progresso."""
    with _state_lock:
        snap = {k: v for k, v in _state.items() if k != "log" and k != "failed_batches"}
        snap["percent"] = (
            round(_state["processed"] / _state["total"] * 100, 1)
            if _state["total"] > 0 else 0
        )
        elapsed = 0
        if _state["started_at"]:
            end = _state["finished_at"] or time.time()
            elapsed = round(end - _state["started_at"])
        snap["elapsed_seconds"] = elapsed
    _broadcast("progress", snap)


# ── Worker thread ─────────────────────────────────────────────────────────────

def _run_backfill(dry_run: bool = False, start_date: str = None, end_date: str = None):
    """Realiza a carga de inventário processando os registros em Batches."""
    with _state_lock:
        _state.update({
            "running": True,
            "dry_run": dry_run,
            "started_at": time.time(),
            "finished_at": None,
            "total": 0,
            "processed": 0,
            "success": 0,
            "errors": 0,
            "batches_total": 0,
            "batches_done": 0,
            "log": [],
            "failed_batches": [],
            "stop_requested": False,
        })

    _push_log("INFO", "▶ Iniciando carga retroativa de inventário…" + (" [DRY-RUN]" if dry_run else ""))
    _emit_progress()

    try:
        # 1. Busca registros de inventário no Oracle
        _push_log("INFO", f"🔌 Consultando Oracle para período AD_DHINC {start_date or '31/07/2019'} — {end_date or 'HOJE'}…")
        records = fetch_records(start_date=start_date, end_date=end_date)

        with _state_lock:
            _state["total"] = len(records)
            # Chunking dos registros com base no BATCH_SIZE (padrão: 1000)
            batches = [records[i:i + BATCH_SIZE] for i in range(0, len(records), BATCH_SIZE)]
            _state["batches_total"] = len(batches)

        _push_log("INFO", f"📊 {len(records)} registros de inventário encontrados — Separados em {len(batches)} batches de até {BATCH_SIZE}.")
        _emit_progress()

        if len(records) == 0:
            _push_log("WARNING", "Nenhum registro de inventário encontrado para o período especificado.")
            return

        # 2. Envia Batch por Batch
        for idx, batch in enumerate(batches, start=1):
            with _state_lock:
                if _state["stop_requested"]:
                    _push_log("WARNING", f"⛔ Interrompido pelo usuário antes de enviar o Batch {idx}.")
                    break

            _push_log("INFO", f"📤 Preparando envio do Batch {idx}/{len(batches)} ({len(batch)} registros)…")

            result = send_batch(batch, batch_index=idx, dry_run=dry_run)

            with _state_lock:
                _state["batches_done"] = idx
                _state["processed"] += len(batch)

                if result["success"]:
                    _state["success"] += len(batch)
                    _push_log("INFO", f"✅ Batch {idx} enviado com sucesso!")
                else:
                    _state["errors"] += len(batch)
                    _state["failed_batches"].append({"index": idx, "size": len(batch), "error": result["error"]})
                    _push_log("ERROR", f"❌ Falha no Batch {idx}: {result['error']}")

            _emit_progress()

        _push_log("INFO", "🏁 Processamento de inventário concluído.")

    except Exception as exc:
        _push_log("ERROR", f"💥 Erro inesperado: {exc}")
        logger.exception("Erro no worker de inventário.")

    finally:
        with _state_lock:
            _state["running"] = False
            _state["finished_at"] = time.time()
        _emit_progress()


# ── Rotas Flask ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status")
def api_status():
    with _state_lock:
        snap = dict(_state)
        snap["percent"] = (round(_state["processed"] / _state["total"] * 100, 1) if _state["total"] > 0 else 0)
        elapsed = 0
        if _state["started_at"]:
            end = _state["finished_at"] or time.time()
            elapsed = round(end - _state["started_at"])
        snap["elapsed_seconds"] = elapsed
    return jsonify(snap)

@app.route("/api/start", methods=["POST"])
def api_start():
    with _state_lock:
        if _state["running"]: return jsonify({"error": "Já em execução."}), 409
    body = request.get_json(silent=True) or {}
    dry_run = bool(body.get("dry_run", False))
    start_date = body.get("start_date")
    end_date = body.get("end_date")

    threading.Thread(target=_run_backfill, args=(dry_run, start_date, end_date), daemon=True).start()
    return jsonify({"started": True, "dry_run": dry_run, "start_date": start_date, "end_date": end_date}), 202

@app.route("/api/stop", methods=["POST"])
def api_stop():
    with _state_lock:
        if not _state["running"]: return jsonify({"error": "Não está rodando."}), 400
        _state["stop_requested"] = True
    return jsonify({"stop_requested": True}), 200

@app.route("/api/stream")
def api_stream():
    client_queue: queue.Queue = queue.Queue(maxsize=200)
    with _sse_lock: _sse_clients.append(client_queue)
    def generate():
        with _state_lock:
            snap = dict(_state)
            snap["percent"] = (round(_state["processed"] / _state["total"] * 100, 1) if _state["total"] > 0 else 0)
        yield f"event: progress\ndata: {json.dumps(snap, default=str)}\n\n"
        try:
            while True:
                msg = client_queue.get(timeout=30)
                yield msg
        except: pass
        finally:
            with _sse_lock:
                if client_queue in _sse_clients: _sse_clients.remove(client_queue)
    return Response(generate(), mimetype="text/event-stream", headers={"Cache-Control": "no-cache","X-Accel-Buffering": "no"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=FLASK_PORT, debug=FLASK_DEBUG, threaded=True)
