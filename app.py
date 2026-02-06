#!/usr/bin/env python3
from flask import Flask, jsonify, request
import json, os, hashlib, time
from ecdsa import VerifyingKey, SECP256k1, BadSignatureError

app = Flask(__name__)

# Archivos de persistencia
STATE_FILE = "state.json"
LEDGER_FILE = "ledger.json"
BLOCKS_FILE = "blocks.json"

# -----------------------
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def load_ledger():
    if os.path.exists(LEDGER_FILE):
        with open(LEDGER_FILE, "r") as f:
            return json.load(f)
    return []

def save_ledger(ledger):
    with open(LEDGER_FILE, "w") as f:
        json.dump(ledger, f, indent=2)

def load_blocks():
    if os.path.exists(BLOCKS_FILE):
        with open(BLOCKS_FILE, "r") as f:
            return json.load(f)
    return []

def save_blocks(blocks):
    with open(BLOCKS_FILE, "w") as f:
        json.dump(blocks, f, indent=2)

def sha256(msg: str) -> str:
    return hashlib.sha256(msg.encode()).hexdigest()

# -----------------------
# Inicializar bloque génesis si no existe
if not os.path.exists(BLOCKS_FILE):
    genesis_block = {
        "index": 0,
        "timestamp": time.time(),
        "transactions": [],
        "previous_hash": "0"*64,
        "block_hash": "0"*64
    }
    save_blocks([genesis_block])

# -----------------------
@app.route("/")
def home():
    return jsonify({"status": "VelCoin node online", "network": "velcoin-mainnet"})

@app.route("/balance/<address>")
def balance(address):
    state = load_state()
    return jsonify({
        "address": address,
        "balance": state.get(address, 0),
        "symbol": "VLC"
    })

@app.route("/transfer", methods=["POST"])
def transfer():
    data = request.get_json()
    sender = data.get("from")
    recipient = data.get("to")
    amount = data.get("amount")
    signature = data.get("signature")
    public_key = data.get("public_key")

    if not all([sender, recipient, amount, signature, public_key]):
        return jsonify({"error": "missing fields"}), 400

    state = load_state()
    if state.get(sender, 0) < amount:
        return jsonify({"error": "insufficient balance"}), 400

    # Calcular hash de transacción
    timestamp = time.time()
    message = f"{sender}->{recipient}:{amount}:{timestamp}"
    tx_hash = sha256(message)

    # Verificación ECDSA
    try:
        vk = VerifyingKey.from_string(bytes.fromhex(public_key), curve=SECP256k1)
        vk.verify(bytes.fromhex(signature), bytes.fromhex(sha256(f"{sender}->{recipient}:{amount}")))
    except BadSignatureError:
        return jsonify({"error": "invalid signature"}), 400
    except Exception as e:
        return jsonify({"error": "verification failed", "details": str(e)}), 500

    # Aplicar transferencia
    state[sender] -= amount
    state[recipient] = state.get(recipient, 0) + amount
    save_state(state)

    # Guardar en ledger
    ledger = load_ledger()
    tx = {
        "tx_hash": tx_hash,
        "from": sender,
        "to": recipient,
        "amount": amount,
        "timestamp": timestamp
    }
    ledger.append(tx)
    save_ledger(ledger)

    # -----------------------
    # Agrupar en bloque simple
    blocks = load_blocks()
    last_block = blocks[-1]
    block_index = last_block["index"] + 1
    previous_hash = last_block["block_hash"]
    new_block = {
        "index": block_index,
        "timestamp": timestamp,
        "transactions": [tx],
        "previous_hash": previous_hash,
        "block_hash": sha256(f"{block_index}{timestamp}{previous_hash}{tx_hash}")
    }
    blocks.append(new_block)
    save_blocks(blocks)

    return jsonify({
        "status": "success",
        "from": sender,
        "to": recipient,
        "amount": amount,
        "tx_hash": tx_hash,
        "block_index": block_index
    })

# -----------------------
# Consultas tipo blockchain
@app.route("/blocks")
def get_blocks():
    blocks = load_blocks()
    return jsonify(blocks)

@app.route("/tx/<tx_hash>")
def get_transaction(tx_hash):
    ledger = load_ledger()
    for tx in ledger:
        if tx["tx_hash"] == tx_hash:
            return jsonify(tx)
    return jsonify({"error": "tx not found"}), 404

@app.route("/address/<address>/txs")
def get_address_txs(address):
    ledger = load_ledger()
    txs = [tx for tx in ledger if tx["from"] == address or tx["to"] == address]
    return jsonify(txs)

# -----------------------
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
