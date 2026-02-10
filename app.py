import os
print("Wallet fundadora detectada:", os.environ.get("VELCOIN_FUND_WALLET"))

from flask import Flask, jsonify, request
import json, hashlib, time, threading, logging, random, string

app = Flask(__name__)

# -----------------------
# PATHS
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "state.json")
LEDGER_FILE = os.path.join(BASE_DIR, "ledger.json")
BLOCKCHAIN_FILE = os.path.join(BASE_DIR, "blockchain.json")
MEMPOOL_FILE = os.path.join(BASE_DIR, "mempool.json")
POOL_FILE = os.path.join(BASE_DIR, "pool.json")
LOG_FILE = os.path.join(BASE_DIR, "node.log")

# -----------------------
# LOGGING
logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# -----------------------
def sha256(msg):
    return hashlib.sha256(msg.encode()).hexdigest()

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

# -----------------------
# LEDGER
def load_ledger(): return load_json(LEDGER_FILE, [])
def save_ledger(x): save_json(LEDGER_FILE, x)
def ensure_ledger():
    if not os.path.exists(LEDGER_FILE): save_ledger([])
    return load_ledger()

# -----------------------
# MEMPOOL
def load_mempool(): return load_json(MEMPOOL_FILE, [])
def save_mempool(x): save_json(MEMPOOL_FILE, x)
def add_tx_to_mempool(tx):
    mempool = load_mempool()
    mempool.append(tx)
    save_mempool(mempool)

# -----------------------
# BLOCKCHAIN
def load_blockchain(): return load_json(BLOCKCHAIN_FILE, [])
def save_blockchain(x): save_json(BLOCKCHAIN_FILE, x)

DIFFICULTY = 4  # número de ceros al inicio del hash (PoW)

def create_genesis_block():
    chain = load_blockchain()
    if chain: return
    g = {
        "index":0,
        "timestamp":int(time.time()),
        "transactions":[],
        "previous_hash":"0"*64,
        "nonce":0
    }
    g["block_hash"]=sha256(json.dumps(g,sort_keys=True))
    chain.append(g)
    save_blockchain(chain)

def mine_block(transactions):
    chain = load_blockchain()
    last = chain[-1]
    index = last["index"] + 1
    previous_hash = last["block_hash"]
    nonce = 0
    while True:
        block = {
            "index": index,
            "timestamp": int(time.time()),
            "transactions": transactions,
            "previous_hash": previous_hash,
            "nonce": nonce
        }
        block_hash = sha256(json.dumps(block, sort_keys=True))
        if block_hash.startswith("0"*DIFFICULTY):
            block["block_hash"] = block_hash
            chain.append(block)
            save_blockchain(chain)
            logging.info(f"Block mined: {block_hash} | txs: {len(transactions)}")
            return block
        nonce += 1

# -----------------------
# WALLET FUNDADORA
# La variable de entorno debe contener un JSON completo de la wallet fundadora
FUND_WALLET_DATA = os.environ.get("VELCOIN_FUND_WALLET")
if not FUND_WALLET_DATA:
    logging.error("No se encontró wallet fundadora en variable de entorno VELCOIN_FUND_WALLET")
    raise Exception("Wallet fundadora requerida para iniciar nodo.")

try:
    FUND_WALLET_JSON = json.loads(FUND_WALLET_DATA)
    FUND_WALLET = FUND_WALLET_JSON["address"]
except Exception as e:
    logging.error(f"Error leyendo wallet fundadora desde variable de entorno: {e}")
    raise Exception("Wallet fundadora inválida")

# -----------------------
# POOL
def ensure_pool():
    p = load_json(POOL_FILE, {})
    s = load_state()
    vlc_balance = s.get(FUND_WALLET, 0)
    p = {
        "velcoin": vlc_balance,
        "history": [],
    }
    save_json(POOL_FILE, p)
    return p

def get_total_supply():
    s = load_state()
    return sum(s.values())

# -----------------------
# WALLET FUNCTIONS
def generate_wallet():
    private_key = ''.join(random.choices(string.hexdigits, k=64)).lower()
    public_key = sha256(private_key)
    address = sha256(public_key)[:40]
    return {"private_key": private_key, "public_key": public_key, "address": address}

# -----------------------
# API
@app.route("/")
def index():
    return jsonify({
        "network":"velcoin-mainnet",
        "node":"VelCoin",
        "status":"online",
        "message":"Nodo VelCoin online. Usa /status, /pool, /balance/<address>, /create_wallet, /send o /mine."
    })

@app.route("/status")
def status():
    p=ensure_pool(); s=load_state()
    return jsonify({
        "network":"velcoin-mainnet",
        "node":"VelCoin",
        "status":"online",
        "symbol":"VLC",
        "total_supply": get_total_supply(),
        "holders":len([v for v in s.values() if v>0]),
    })

@app.route("/pool")
def pool(): 
    p=ensure_pool()
    return jsonify(p)

@app.route("/balance/<address>")
def balance(address):
    s = load_state()
    b = s.get(address, 0)
    return jsonify({"address": address, "balance": f"{b:.6f}"})

@app.route("/create_wallet", methods=["POST"])
def create_wallet():
    w = generate_wallet()
    return jsonify(w)

@app.route("/send", methods=["POST"])
def send():
    try:
        data = request.json
        sender = data["from"]
        recipient = data["to"]
        amount = float(data["amount"])
        s = load_state()
        if s.get(sender,0) < amount:
            return jsonify({"error":"insufficient balance"}),400
        s[sender] -= amount
        s[recipient] = s.get(recipient,0) + amount
        save_state(s)
        tx = {
            "tx_hash": sha256(f"{sender}{recipient}{amount}{time.time()}"),
            "from": sender,
            "to": recipient,
            "amount": amount,
            "timestamp": int(time.time())
        }
        add_tx_to_mempool(tx)
        ensure_ledger().append(tx)
        logging.info(f"TX: {sender} -> {recipient} : {amount} VLC")
        return jsonify(tx)
    except Exception as e:
        return jsonify({"error": str(e)}),500

@app.route("/mine", methods=["POST"])
def mine():
    try:
        mempool = load_mempool()
        if not mempool:
            return jsonify({"error":"No transactions to mine"}),400
        block = mine_block(mempool)
        save_mempool([])
        return jsonify(block)
    except Exception as e:
        return jsonify({"error": str(e)}),500

@app.route("/blocks")
def blocks(): return jsonify(load_blockchain())

# -----------------------
# INIT
create_genesis_block()
ensure_pool()
ensure_ledger()

if __name__ == "__main__":
    port = int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0", port=port)
