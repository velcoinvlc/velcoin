from flask import Flask, jsonify, request
import json, os, hashlib, time
from ecdsa import VerifyingKey, SECP256k1, BadSignatureError

app = Flask(__name__)

STATE_FILE = "state.json"
LEDGER_FILE = "ledger.json"
BLOCKCHAIN_FILE = "blockchain.json"
POOL_FILE = "pool.json"

# -----------------------
# STATE
def load_state():
    if os.path.exists(STATE_FILE):
        return json.load(open(STATE_FILE))
    return {}

def save_state(s):
    json.dump(s, open(STATE_FILE, "w"), indent=2)

# -----------------------
# LEDGER
def load_ledger():
    if os.path.exists(LEDGER_FILE):
        return json.load(open(LEDGER_FILE))
    return []

def save_ledger(l):
    json.dump(l, open(LEDGER_FILE, "w"), indent=2)

# -----------------------
# BLOCKCHAIN
def load_blockchain():
    if os.path.exists(BLOCKCHAIN_FILE):
        return json.load(open(BLOCKCHAIN_FILE))
    return []

def save_blockchain(c):
    json.dump(c, open(BLOCKCHAIN_FILE, "w"), indent=2)

def sha256(msg):
    return hashlib.sha256(msg.encode()).hexdigest()

def create_genesis_block():
    chain = load_blockchain()
    if not chain:
        g = {
            "index": 0,
            "timestamp": int(time.time()),
            "transactions": [],
            "previous_hash": "0"*64
        }
        g["block_hash"] = sha256(json.dumps(g, sort_keys=True))
        chain.append(g)
        save_blockchain(chain)

def add_tx_to_block(tx):
    chain = load_blockchain()
    if not chain:
        create_genesis_block()
        chain = load_blockchain()

    last = chain[-1]

    block = {
        "index": last["index"] + 1,
        "timestamp": int(time.time()),
        "transactions": [tx],
        "previous_hash": last["block_hash"]
    }

    block["block_hash"] = sha256(json.dumps(block, sort_keys=True))
    chain.append(block)
    save_blockchain(chain)

# -----------------------
# POOL
def load_pool():
    if os.path.exists(POOL_FILE):
        return json.load(open(POOL_FILE))
    return {}

def save_pool(p):
    json.dump(p, open(POOL_FILE, "w"), indent=2)

def migrate_pool(pool):
    if "velcoin" not in pool:
        pool["velcoin"] = 1_000_000
    if "usdt" not in pool:
        pool["usdt"] = 50_000
    if "trx" not in pool:
        pool["trx"] = 100_000
    if "history" not in pool:
        pool["history"] = []
    if "limits" not in pool:
        pool["limits"] = {
            "max_buy_usdt": 5000,
            "max_buy_trx": 20000,
            "max_sell_vlc": 100_000
        }
    return pool

def ensure_pool():
    p = migrate_pool(load_pool())
    save_pool(p)
    return p

def price_usdt(p):
    return p["usdt"] / p["velcoin"] if p["velcoin"] != 0 else 0

def price_trx(p):
    return p["trx"] / p["velcoin"] if p["velcoin"] != 0 else 0

# -----------------------
# LISTING ENDPOINTS
@app.route("/status")
def status():
    p = ensure_pool()
    s = load_state()
    return jsonify({
        "status": "online",
        "network": "velcoin-mainnet",
        "symbol": "VLC",
        "total_supply": sum(s.values()),
        "holders": len([v for v in s.values() if v > 0]),
        "price_usdt": price_usdt(p),
        "price_trx": price_trx(p)
    })

@app.route("/pool")
def pool_info():
    p = ensure_pool()
    return jsonify({
        "velcoin": p["velcoin"],
        "usdt": p["usdt"],
        "trx": p["trx"],
        "price_usdt": price_usdt(p),
        "price_trx": price_trx(p),
        "history_count": len(p["history"])
    })

@app.route("/supply")
def supply():
    s = load_state()
    return jsonify({"total_supply": sum(s.values()), "symbol": "VLC"})

@app.route("/holders")
def holders():
    s = load_state()
    p = ensure_pool()
    # Construir balances sumando state + historial pool
    holder_balances = s.copy()
    for h in p["history"]:
        addr = h["address"]
        vlc = h.get("vlc", 0)
        if h["type"] in ["sell"]:
            holder_balances[addr] = holder_balances.get(addr, 0) - vlc
        elif h["type"] in ["buy_usdt", "buy_trx"]:
            holder_balances[addr] = holder_balances.get(addr, 0) + vlc
    h_list = [{"address": a, "balance": b} for a, b in holder_balances.items() if b > 0]
    return jsonify({"count": len(h_list), "holders": h_list})

@app.route("/volume24h")
def vol24():
    now = int(time.time()) - 86400
    p = ensure_pool()
    v = sum(tx.get("vlc", 0) for tx in p["history"] if tx["timestamp"] >= now)
    return jsonify({"volume_24h": v})

# -----------------------
# BASIC
@app.route("/")
def home():
    return jsonify({"node":"VelCoin", "network":"velcoin-mainnet"})

@app.route("/balance/<addr>")
def balance(addr):
    s = load_state()
    return jsonify({"address":addr,"balance":s.get(addr,0),"symbol":"VLC"})

@app.route("/blocks")
def blocks():
    return jsonify(load_blockchain())

@app.route("/tx/<h>")
def tx(h):
    for t in load_ledger():
        if t["tx_hash"] == h:
            return jsonify(t)
    return jsonify({"error":"not found"}),404

# -----------------------
# BUY WITH USDT
@app.route("/buy", methods=["POST"])
def buy_usdt():
    d = request.get_json()
    addr = d.get("address")
    usdt = float(d.get("usdt",0))

    if usdt <= 0:
        return jsonify({"error":"bad params"}),400

    p = ensure_pool()
    s = load_state()

    price = price_usdt(p)
    out = usdt / price

    if out > p["velcoin"]:
        return jsonify({"error":"no liquidity"}),400

    p["usdt"] += usdt
    p["velcoin"] -= out
    p["history"].append({
        "type": "buy_usdt",
        "address": addr,
        "vlc": out,
        "usdt": usdt,
        "trx": 0,
        "timestamp": int(time.time())
    })
    save_pool(p)

    s[addr] = s.get(addr,0) + out
    save_state(s)

    txh = sha256(f"BUYUSDT:{addr}:{out}:{time.time()}")
    tx = {"tx_hash":txh,"from":"POOL","to":addr,"amount":out,"type":"buy_usdt","timestamp":int(time.time())}

    l = load_ledger(); l.append(tx); save_ledger(l)
    add_tx_to_block(tx)

    return jsonify({"status":"success","vlc_received":out,"price":price,"tx_hash":txh})

# -----------------------
# BUY WITH TRX
@app.route("/buy_trx", methods=["POST"])
def buy_trx():
    d = request.get_json()
    addr = d.get("address")
    trx = float(d.get("trx",0))

    if trx <= 0:
        return jsonify({"error":"bad params"}),400

    p = ensure_pool()
    s = load_state()

    price = price_trx(p)
    out = trx / price

    if out > p["velcoin"]:
        return jsonify({"error":"no liquidity"}),400

    p["trx"] += trx
    p["velcoin"] -= out
    p["history"].append({
        "type": "buy_trx",
        "address": addr,
        "vlc": out,
        "usdt": 0,
        "trx": trx,
        "timestamp": int(time.time())
    })
    save_pool(p)

    s[addr] = s.get(addr,0) + out
    save_state(s)

    txh = sha256(f"BUYTRX:{addr}:{out}:{time.time()}")
    tx = {"tx_hash":txh,"from":"POOL","to":addr,"amount":out,"type":"buy_trx","timestamp":int(time.time())}

    l = load_ledger(); l.append(tx); save_ledger(l)
    add_tx_to_block(tx)

    return jsonify({"status":"success","vlc_received":out,"price":price,"tx_hash":txh})

# -----------------------
# SELL → USDT
@app.route("/sell", methods=["POST"])
def sell():
    d = request.get_json()
    addr = d.get("address")
    vlc = float(d.get("vlc",0))

    s = load_state()
    if s.get(addr,0) < vlc:
        return jsonify({"error":"balance"}),400

    p = ensure_pool()
    price = price_usdt(p)
    usdt = vlc * price

    if usdt > p["usdt"]:
        return jsonify({"error":"pool usdt"}),400

    p["usdt"] -= usdt
    p["velcoin"] += vlc
    p["history"].append({
        "type": "sell",
        "address": addr,
        "vlc": vlc,
        "usdt": usdt,
        "trx": 0,
        "timestamp": int(time.time())
    })
    save_pool(p)

    s[addr] -= vlc
    save_state(s)

    txh = sha256(f"SELL:{addr}:{vlc}:{time.time()}")
    tx = {"tx_hash":txh,"from":addr,"to":"POOL","amount":vlc,"type":"sell","timestamp":int(time.time())}

    l = load_ledger(); l.append(tx); save_ledger(l)
    add_tx_to_block(tx)

    return jsonify({"status":"success","usdt_received":usdt,"tx_hash":txh})

# -----------------------
if __name__ == "__main__":
    create_genesis_block()
    ensure_pool()
    port = int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0", port=port)
