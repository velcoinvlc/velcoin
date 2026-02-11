import os
print("Wallet fundadora detectada:", os.environ.get("VELCOIN_FUND_WALLET"))

from flask import Flask, jsonify, request
import json, hashlib, time, logging, random, string
from functools import wraps
from collections import defaultdict
from ecdsa import SigningKey, VerifyingKey, SECP256k1, BadSignatureError

app = Flask(__name__)

# -----------------------
# PATHS
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "state.json")
BLOCKCHAIN_FILE = os.path.join(BASE_DIR, "blockchain.json")
MEMPOOL_FILE = os.path.join(BASE_DIR, "mempool.json")
NONCE_FILE = os.path.join(BASE_DIR, "nonces.json")
LOG_FILE = os.path.join(BASE_DIR, "node.log")

MAX_TX_AMOUNT = 1_000_000

# -----------------------
# LOGGING
logging.basicConfig(filename=LOG_FILE, level=logging.INFO)

# -----------------------
# RATE LIMIT
RATE_LIMIT = defaultdict(list)

def rate_limit(max_calls=20, window=60):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            ip = request.remote_addr
            now = time.time()
            RATE_LIMIT[ip] = [t for t in RATE_LIMIT[ip] if now - t < window]
            if len(RATE_LIMIT[ip]) >= max_calls:
                return jsonify({"error":"rate limit"}),429
            RATE_LIMIT[ip].append(now)
            return f(*args, **kwargs)
        return wrapped
    return decorator

# -----------------------
# CRYPTO

def sha256(msg):
    return hashlib.sha256(msg.encode()).hexdigest()

def derive_address(pub_hex):
    return sha256(pub_hex)[:40]

def verify_signature(pub_hex, payload, signature_hex):
    try:
        vk = VerifyingKey.from_string(bytes.fromhex(pub_hex), curve=SECP256k1)
        vk.verify(bytes.fromhex(signature_hex), payload.encode())
        return True
    except BadSignatureError:
        return False
    except Exception:
        return False

# -----------------------
# JSON IO

def load_json(path, default):
    if os.path.exists(path):
        try:
            return json.load(open(path))
        except:
            return default
    return default

def save_json(path, data):
    json.dump(data, open(path,"w"), indent=2)

# -----------------------
# STATE

def load_state(): return load_json(STATE_FILE, {})
def save_state(x): save_json(STATE_FILE, x)

def load_mempool(): return load_json(MEMPOOL_FILE, [])
def save_mempool(x): save_json(MEMPOOL_FILE, x)

def load_chain(): return load_json(BLOCKCHAIN_FILE, [])
def save_chain(x): save_json(BLOCKCHAIN_FILE, x)

def load_nonces(): return load_json(NONCE_FILE, {})
def save_nonces(x): save_json(NONCE_FILE, x)

# -----------------------
# BLOCKCHAIN

DIFFICULTY = 4

def create_genesis():
    chain = load_chain()
    if chain:
        return
    g = {
        "index":0,
        "timestamp":int(time.time()),
        "transactions":[],
        "previous_hash":"0"*64,
        "nonce":0
    }
    g["block_hash"]=sha256(json.dumps(g,sort_keys=True))
    chain.append(g)
    save_chain(chain)

def pow_block(index, prev_hash, txs):
    nonce = 0
    while True:
        block = {
            "index": index,
            "timestamp": int(time.time()),
            "transactions": txs,
            "previous_hash": prev_hash,
            "nonce": nonce
        }
        h = sha256(json.dumps(block, sort_keys=True))
        if h.startswith("0"*DIFFICULTY):
            block["block_hash"] = h
            return block
        nonce += 1

# -----------------------
# TX VALIDATION

def validate_tx_basic(tx):
    required = ["from","to","amount","nonce","public_key","signature"]
    for r in required:
        if r not in tx:
            return False,"missing "+r

    if float(tx["amount"]) <= 0 or float(tx["amount"]) > MAX_TX_AMOUNT:
        return False,"amount invalid"

    if derive_address(tx["public_key"]) != tx["from"]:
        return False,"addr/pub mismatch"

    payload = f'{tx["from"]}{tx["to"]}{tx["amount"]}{tx["nonce"]}'
    if not verify_signature(tx["public_key"], payload, tx["signature"]):
        return False,"bad sig"

    return True,"ok"

def validate_tx_state(tx, state, nonces):
    sender = tx["from"]
    amt = float(tx["amount"])

    if state.get(sender,0) < amt:
        return False,"no balance"

    if tx["nonce"] <= nonces.get(sender,0):
        return False,"bad nonce"

    return True,"ok"

# -----------------------
# APPLY BLOCK STATE

def apply_block(block):
    state = load_state()
    nonces = load_nonces()

    for tx in block["transactions"]:
        sender = tx["from"]
        to = tx["to"]
        amt = float(tx["amount"])

        state[sender] = state.get(sender,0) - amt
        state[to] = state.get(to,0) + amt
        nonces[sender] = tx["nonce"]

    save_state(state)
    save_nonces(nonces)

# -----------------------
# WALLET GEN

def generate_wallet():
    sk = SigningKey.generate(curve=SECP256k1)
    vk = sk.get_verifying_key()
    priv = sk.to_string().hex()
    pub = vk.to_string().hex()
    addr = derive_address(pub)
    return {"private_key":priv,"public_key":pub,"address":addr}

# -----------------------
# API

@app.route("/")
@rate_limit()
def index():
    return jsonify({"status":"online","network":"velcoin-mainnet"})

@app.route("/status")
@rate_limit()
def status():
    s=load_state()
    return jsonify({
        "status":"online",
        "holders":len([v for v in s.values() if v>0]),
        "supply":sum(s.values()),
        "height": len(load_chain())-1
    })

@app.route("/balance/<addr>")
@rate_limit()
def balance(addr):
    return jsonify({"balance": load_state().get(addr,0)})

@app.route("/create_wallet", methods=["POST"])
@rate_limit()
def create_wallet_api():
    return jsonify(generate_wallet())

@app.route("/send", methods=["POST"])
@rate_limit()
def send():
    tx = request.json

    ok,msg = validate_tx_basic(tx)
    if not ok:
        return jsonify({"error":msg}),400

    mem = load_mempool()
    mem.append(tx)
    save_mempool(mem)

    return jsonify({"accepted":True})

@app.route("/mine", methods=["POST"])
@rate_limit(5,60)
def mine():
    mem = load_mempool()
    if not mem:
        return jsonify({"error":"no tx"}),400

    state = load_state()
    nonces = load_nonces()

    valid=[]
    for tx in mem:
        ok,_ = validate_tx_basic(tx)
        if not ok: continue
        ok,_ = validate_tx_state(tx,state,nonces)
        if not ok: continue

        valid.append(tx)
        state[tx["from"]] -= float(tx["amount"])
        state[tx["to"]] = state.get(tx["to"],0)+float(tx["amount"])
        nonces[tx["from"]] = tx["nonce"]

    if not valid:
        return jsonify({"error":"no valid tx"}),400

    chain = load_chain()
    last = chain[-1]
    block = pow_block(last["index"]+1, last["block_hash"], valid)

    chain.append(block)
    save_chain(chain)
    save_state(state)
    save_nonces(nonces)
    save_mempool([])

    return jsonify(block)

@app.route("/blocks")
@rate_limit()
def blocks():
    return jsonify(load_chain())

@app.route("/confirmations/<int:index>")
@rate_limit()
def confirmations(index):
    h = len(load_chain())-1
    return jsonify({"confirmations": max(0, h-index)})

# -----------------------
# INIT

create_genesis()

if __name__ == "__main__":
    port = int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0", port=port)
