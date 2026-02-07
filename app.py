from flask import Flask, jsonify, request
import json, os, hashlib, time
from ecdsa import VerifyingKey, SECP256k1, BadSignatureError

app = Flask(__name__)
STATE_FILE = "state.json"
LEDGER_FILE = "ledger.json"
BLOCKCHAIN_FILE = "blockchain.json"
POOL_FILE = "pool.json"

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

def load_blockchain():
    if os.path.exists(BLOCKCHAIN_FILE):
        with open(BLOCKCHAIN_FILE, "r") as f:
            return json.load(f)
    return []

def save_blockchain(chain):
    with open(BLOCKCHAIN_FILE, "w") as f:
        json.dump(chain, f, indent=2)

def sha256(msg: str) -> str:
    return hashlib.sha256(msg.encode()).hexdigest()

def add_tx_to_block(tx):
    chain = load_blockchain()
    last = chain[-1]

    block = {
        "index": last["index"] + 1,
        "previous_hash": last["block_hash"],
        "timestamp": int(time.time()),
        "transactions": [tx]
    }

    raw = json.dumps(block, sort_keys=True)
    block["block_hash"] = sha256(raw)

    chain.append(block)
    save_blockchain(chain)

# -----------------------
def create_genesis_block():
    chain = load_blockchain()
    if not chain:
        genesis_block = {
            "index": 0,
            "timestamp": int(time.time()),
            "transactions": [],
            "previous_hash": "0"*64,
            "block_hash": "0"*64
        }
        genesis_block["block_hash"] = sha256(json.dumps(genesis_block, sort_keys=True))
        chain.append(genesis_block)
        save_blockchain(chain)
    return chain

def add_block(transactions):
    chain = load_blockchain()
    previous_block = chain[-1]
    block = {
        "index": previous_block["index"] + 1,
        "timestamp": int(time.time()),
        "transactions": transactions,
        "previous_hash": previous_block["block_hash"],
        "block_hash": ""
    }
    block["block_hash"] = sha256(json.dumps(block, sort_keys=True))
    chain.append(block)
    save_blockchain(chain)
    return block

# -----------------------
# Pool functions
def load_pool():
    if os.path.exists(POOL_FILE):
        with open(POOL_FILE, "r") as f:
            return json.load(f)
    # Pool inicial: 200 USDT y 10,000 VelCoin
    pool = {"velcoin": 10000, "usdt": 200, "history": []}
    save_pool(pool)
    return pool

def save_pool(pool):
    with open(POOL_FILE, "w") as f:
        json.dump(pool, f, indent=2)

def pool_price(pool):
    if pool["velcoin"] == 0:
        return 0
    return pool["usdt"] / pool["velcoin"]

# -----------------------
# Node endpoints
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

@app.route("/blocks")
def get_blocks():
    chain = load_blockchain()
    return jsonify(chain)

@app.route("/tx/<tx_hash>")
def get_transaction(tx_hash):
    ledger = load_ledger()
    for tx in ledger:
        if tx["tx_hash"] == tx_hash:
            return jsonify(tx)
    return jsonify({"error": "transaction not found"}), 404

@app.route("/address/<address>/txs")
def get_address_txs(address):
    ledger = load_ledger()
    txs = [tx for tx in ledger if tx["from"] == address or tx["to"] == address]
    return jsonify(txs)

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

    message = f"{sender}->{recipient}:{amount}"
    msg_hash = sha256(message)

    try:
        vk = VerifyingKey.from_string(bytes.fromhex(public_key), curve=SECP256k1)
        vk.verify(bytes.fromhex(signature), bytes.fromhex(msg_hash))
    except BadSignatureError:
        return jsonify({"error": "invalid signature"}), 400
    except Exception as e:
        return jsonify({"error": "verification failed", "details": str(e)}), 500

    state[sender] -= amount
    state[recipient] = state.get(recipient, 0) + amount
    save_state(state)

    ledger = load_ledger()
    tx = {
        "tx_hash": msg_hash,
        "from": sender,
        "to": recipient,
        "amount": amount,
        "timestamp": int(time.time())
    }
    ledger.append(tx)
    save_ledger(ledger)

    add_block([tx])

    return jsonify({
        "status": "success",
        "from": sender,
        "to": recipient,
        "amount": amount,
        "tx_hash": msg_hash
    })

# -----------------------
# Pool endpoints
@app.route("/pool")
def pool_info():
    pool = load_pool()
    return jsonify({
        "velcoin_reserve": pool["velcoin"],
        "usdt_reserve": pool["usdt"],
        "price": pool_price(pool)
    })

@app.route("/buy", methods=["POST"])
def buy_velcoin():
    data = request.get_json()
    address = data.get("address")
    usdt_amount = float(data.get("usdt", 0))

    if not address or usdt_amount <= 0:
        return jsonify({"error": "bad params"}), 400

    pool = load_pool()
    state = load_state()
    price = pool_price(pool)

    if price == 0:
        return jsonify({"error": "pool empty"}), 400

    velcoin_out = usdt_amount / price

    if velcoin_out > pool["velcoin"]:
        return jsonify({"error": "not enough liquidity"}), 400

    pool["usdt"] += usdt_amount
    pool["velcoin"] -= velcoin_out
    save_pool(pool)

    state[address] = state.get(address, 0) + velcoin_out
    save_state(state)

    tx_hash = sha256(f"BUY:{address}:{velcoin_out}:{time.time()}")
    add_tx_to_block({
        "tx_hash": tx_hash,
        "from": "POOL",
        "to": address,
        "amount": velcoin_out,
        "type": "buy"
    })

    return jsonify({
        "status": "success",
        "vlc_received": velcoin_out,
        "price": price,
        "tx_hash": tx_hash
    })

@app.route("/sell", methods=["POST"])
def sell_velcoin():
    data = request.get_json()
    address = data.get("address")
    velcoin_amount = float(data.get("vlc", 0))

    if not address or velcoin_amount <= 0:
        return jsonify({"error": "bad params"}), 400

    pool = load_pool()
    state = load_state()

    if state.get(address, 0) < velcoin_amount:
        return jsonify({"error": "insufficient balance"}), 400

    price = pool_price(pool)
    usdt_out = velcoin_amount * price

    if usdt_out > pool["usdt"]:
        return jsonify({"error": "not enough USDT in pool"}), 400

    pool["usdt"] -= usdt_out
    pool["velcoin"] += velcoin_amount
    save_pool(pool)

    state[address] -= velcoin_amount
    save_state(state)

    tx_hash = sha256(f"SELL:{address}:{velcoin_amount}:{time.time()}")
    add_tx_to_block({
        "tx_hash": tx_hash,
        "from": address,
        "to": "POOL",
        "amount": velcoin_amount,
        "type": "sell"
    })

    return jsonify({
        "status": "success",
        "usdt_received": usdt_out,
        "price": price,
        "tx_hash": tx_hash
    })

# -----------------------
if __name__ == "__main__":
    create_genesis_block()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
