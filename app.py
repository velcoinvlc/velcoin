from flask import Flask, jsonify, request
import json, os, hashlib, time
from ecdsa import VerifyingKey, SECP256k1, BadSignatureError

app = Flask(__name__)
STATE_FILE = "state.json"
LEDGER_FILE = "ledger.json"

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

def sha256(msg: str) -> str:
    return hashlib.sha256(msg.encode()).hexdigest()

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

    # mensaje y hash de transacción
    message = f"{sender}->{recipient}:{amount}"
    msg_hash = sha256(message)

    # verificar firma ECDSA
    try:
        vk = VerifyingKey.from_string(bytes.fromhex(public_key), curve=SECP256k1)
        vk.verify(bytes.fromhex(signature), bytes.fromhex(msg_hash))
    except BadSignatureError:
        return jsonify({"error": "invalid signature"}), 400
    except Exception as e:
        return jsonify({"error": "verification failed", "details": str(e)}), 500

    # aplicar transferencia
    state[sender] -= amount
    state[recipient] = state.get(recipient, 0) + amount
    save_state(state)

    # guardar en ledger
    ledger = load_ledger()
    tx = {
        "tx_hash": msg_hash,
        "from": sender,
        "to": recipient,
        "amount": amount,
        "timestamp": time.time()
    }
    ledger.append(tx)
    save_ledger(ledger)

    return jsonify({
        "status": "success",
        "from": sender,
        "to": recipient,
        "amount": amount,
        "tx_hash": msg_hash
    })

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))  # Railway asigna su puerto
    app.run(host="0.0.0.0", port=port, debug=False)
