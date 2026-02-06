from flask import Flask, jsonify, request
import json, os, hashlib, time
from ecdsa import VerifyingKey, SECP256k1, BadSignatureError

app = Flask(__name__)

STATE_FILE = "state.json"      # balances (NO SE TOCA ESTRUCTURA)
LEDGER_FILE = "ledger.json"    # mempool (tx pendientes)
BLOCKS_FILE = "blocks.json"    # blockchain real

BLOCK_TX_LIMIT = 5  # cuántas tx forman un bloque

# -----------------------
# Utils básicos
# -----------------------

def sha256(msg: str) -> str:
    return hashlib.sha256(msg.encode()).hexdigest()

# -----------------------
# State (balances)
# -----------------------

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

# -----------------------
# Ledger (mempool)
# -----------------------

def load_ledger():
    if os.path.exists(LEDGER_FILE):
        with open(LEDGER_FILE, "r") as f:
            return json.load(f)
    return []

def save_ledger(ledger):
    with open(LEDGER_FILE, "w") as f:
        json.dump(ledger, f, indent=2)

# -----------------------
# Blockchain
# -----------------------

def load_blocks():
    if os.path.exists(BLOCKS_FILE):
        with open(BLOCKS_FILE, "r") as f:
            return json.load(f)
    return []

def save_blocks(blocks):
    with open(BLOCKS_FILE, "w") as f:
        json.dump(blocks, f, indent=2)

def get_last_block():
    blocks = load_blocks()
    return blocks[-1] if blocks else None

def hash_block(block):
    block_copy = dict(block)
    block_copy.pop("hash", None)
    block_string = json.dumps(block_copy, sort_keys=True)
    return sha256(block_string)

def create_genesis_block_if_needed():
    blocks = load_blocks()
    if blocks:
        return

    genesis = {
        "index": 1,
        "timestamp": time.time(),
        "transactions": [],
        "previous_hash": "0" * 64,
        "nonce": 0
    }
    genesis["hash"] = hash_block(genesis)
    save_blocks([genesis])

def create_block_from_mempool():
    ledger = load_ledger()
    if len(ledger) < BLOCK_TX_LIMIT:
        return None

    blocks = load_blocks()
    last_block = blocks[-1]

    txs = ledger[:BLOCK_TX_LIMIT]
    remaining = ledger[BLOCK_TX_LIMIT:]

    block = {
        "index": last_block["index"] + 1,
        "timestamp": time.time(),
        "transactions": txs,
        "previous_hash": last_block["hash"],
        "nonce": 0
    }

    block["hash"] = hash_block(block)

    blocks.append(block)
    save_blocks(blocks)
    save_ledger(remaining)

    return block

# -----------------------
# Arranque
# -----------------------

create_genesis_block_if_needed()

# -----------------------
# API básica
# -----------------------

@app.route("/")
def home():
    return jsonify({
        "status": "VelCoin node online",
        "network": "velcoin-mainnet",
        "blocks": len(load_blocks())
    })

# -----------------------
# Balance REAL desde blockchain
# -----------------------

@app.route("/balance/<address>")
def balance(address):
    balance = 0
    blocks = load_blocks()

    for block in blocks:
        for tx in block["transactions"]:
            if tx["to"] == address:
                balance += tx["amount"]
            if tx["from"] == address:
                balance -= tx["amount"]

    # fallback al state (para no romper wallet fundadora existente)
    if balance == 0:
        state = load_state()
        balance = state.get(address, 0)

    return jsonify({
        "address": address,
        "balance": balance,
        "symbol": "VLC"
    })

# -----------------------
# Transferencia firmada
# -----------------------

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

    amount = int(amount)

    state = load_state()

    if state.get(sender, 0) < amount:
        return jsonify({"error": "insufficient balance"}), 400

    message = f"{sender}->{recipient}:{amount}"
    msg_hash = sha256(message)

    try:
        vk = VerifyingKey.from_string(bytes.fromhex(public_key), curve=SECP256k1)
        vk.verify(bytes.fromhex(signature), bytes.fromhex(msg_hash))
    except BadSignatureError:
        return jsonify({"error": "invalid signature"}), 400
    except Exception as e:
        return jsonify({"error": "verification failed", "details": str(e)}), 500

    # actualizar balances (NO cambia estructura fundadora)
    state[sender] -= amount
    state[recipient] = state.get(recipient, 0) + amount
    save_state(state)

    # crear tx
    tx = {
        "tx_hash": msg_hash,
        "from": sender,
        "to": recipient,
        "amount": amount,
        "timestamp": time.time()
    }

    ledger = load_ledger()
    ledger.append(tx)
    save_ledger(ledger)

    # intentar minar bloque automáticamente
    new_block = create_block_from_mempool()

    return jsonify({
        "status": "success",
        "tx_hash": msg_hash,
        "included_in_block": new_block["index"] if new_block else None
    })

# -----------------------
# Explorer endpoints (CoinMarketCap style)
# -----------------------

@app.route("/blocks")
def blocks():
    return jsonify(load_blocks())

@app.route("/blocks/<int:index>")
def block_by_index(index):
    for b in load_blocks():
        if b["index"] == index:
            return jsonify(b)
    return jsonify({"error": "block not found"}), 404

@app.route("/tx/<tx_hash>")
def tx_by_hash(tx_hash):
    for block in load_blocks():
        for tx in block["transactions"]:
            if tx["tx_hash"] == tx_hash:
                return jsonify(tx)
    return jsonify({"error": "transaction not found"}), 404

@app.route("/address/<address>/txs")
def txs_by_address(address):
    result = []
    for block in load_blocks():
        for tx in block["transactions"]:
            if tx["from"] == address or tx["to"] == address:
                result.append(tx)
    return jsonify(result)

# -----------------------
# Estado de red
# -----------------------

@app.route("/network/stats")
def net_stats():
    blocks = load_blocks()
    tx_count = sum(len(b["transactions"]) for b in blocks)

    return jsonify({
        "blocks": len(blocks),
        "transactions": tx_count,
        "mempool": len(load_ledger())
    })

# -----------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
