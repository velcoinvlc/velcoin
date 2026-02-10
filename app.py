from flask import Flask, jsonify, request
import json, os, hashlib, time, threading, logging
import requests

app = Flask(__name__)

# -----------------------
# PATHS
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "state.json")
LEDGER_FILE = os.path.join(BASE_DIR, "ledger.json")
BLOCKCHAIN_FILE = os.path.join(BASE_DIR, "blockchain.json")
POOL_FILE = os.path.join(BASE_DIR, "pool.json")
PROCESSED_FILE = os.path.join(BASE_DIR, "processed_txs.json")
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
# BLOCKCHAIN
def load_blockchain(): return load_json(BLOCKCHAIN_FILE, [])
def save_blockchain(x): save_json(BLOCKCHAIN_FILE, x)

# -----------------------
# WALLET FUNDADORA DESDE ENV
try:
    fund_wallet_json = os.environ["VELCOIN_FUND_WALLET"]
    FUND_WALLET = json.loads(fund_wallet_json)["address"]
except Exception as e:
    logging.error(f"Wallet fundadora no encontrada. Setea VELCOIN_FUND_WALLET. Error: {e}")
    raise Exception("Wallet fundadora no encontrada. Nodo no puede iniciar.")

# -----------------------
# POOL Y PROCESADOS
processed = set(load_json(PROCESSED_FILE, []))
last_trx_balance = 0
last_usdt_balance = 0

def save_processed():
    save_json(PROCESSED_FILE, list(processed))

# -----------------------
# POOL REAL
POOL = load_json(POOL_FILE, {"velcoin":0,"trx":0,"usdt":0,"history":[]})

def ensure_pool():
    global POOL
    return POOL

def price_usdt(p): return p["usdt"]/p["velcoin"] if p["velcoin"]>0 else 0
def price_trx(p): return p["trx"]/p["velcoin"] if p["velcoin"]>0 else 0
def get_total_supply():
    s = load_state()
    return sum(s.values()) + POOL.get("velcoin",0)

# -----------------------
# PROOF-OF-WORK
DIFFICULTY = 4  # número de ceros iniciales requeridos

def mine_block(transactions, previous_hash):
    index = len(load_blockchain())
    timestamp = int(time.time())
    nonce = 0
    while True:
        block = {
            "index": index,
            "timestamp": timestamp,
            "transactions": transactions,
            "previous_hash": previous_hash,
            "nonce": nonce
        }
        block_hash = sha256(json.dumps(block, sort_keys=True))
        if block_hash.startswith("0"*DIFFICULTY):
            block["block_hash"] = block_hash
            return block
        nonce += 1

def add_tx_to_block(tx):
    chain = load_blockchain()
    last = chain[-1]
    block = mine_block([tx], last["block_hash"])
    chain.append(block)
    save_blockchain(chain)

# -----------------------
# INIT GENESIS
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

# -----------------------
# FUNCIONES DE TRX/USDT SIMULADAS
TRX_WALLET = "TRX_SIMULADO"
USDT_CONTRACT = "USDT_SIMULADO"

def get_trx_balance(wallet):
    return 0  # simulado

def scan_usdt_txs(wallet):
    return 0  # simulado

# -----------------------
# DEPOSIT MONITOR SIMULADO
def check_deposits_loop():
    while True:
        try:
            time.sleep(15)
        except Exception as e:
            logging.error(f"Deposit loop error: {e}")

# -----------------------
# API
@app.route("/")
def index():
    return jsonify({
        "network":"velcoin-mainnet",
        "node":"VelCoin",
        "status":"online",
        "message":"Bienvenido a VelCoin node API. Usa /status, /pool, /balance/<address>, /blocks, /buy o /sell."
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
        "price_usdt":price_usdt(p),
        "price_trx":price_trx(p)
    })

@app.route("/pool")
def pool(): 
    p=ensure_pool()
    return jsonify(p)

@app.route("/balance/<a>")
def bal(a):
    if a == FUND_WALLET:
        b = POOL.get("velcoin",0)
        return jsonify({"address": a, "balance": f"{b:.6f}"})
    b = load_state().get(a,0)
    return jsonify({"address":a,"balance":f"{b:.6f}"})

@app.route("/blocks")
def blocks(): return jsonify(load_blockchain())

@app.route("/buy",methods=["POST"])
def buy():
    try:
        d=request.json
        addr=d["address"]
        usdt=float(d["usdt"])
        if usdt<=0: return jsonify({"error":"bad params"}),400
        p=ensure_pool(); s=load_state()
        price = price_usdt(p)
        if price<=0: return jsonify({"error":"no liquidity"}),400
        out = usdt / price if price>0 else 0
        if out>p["velcoin"]: return jsonify({"error":"liquidity"}),400
        p["usdt"] += usdt
        p["velcoin"] -= out
        s[addr] = s.get(addr,0)+out
        save_json(POOL_FILE,p); save_state(s)
        tx={"tx_hash":sha256(str(time.time())),"from":"POOL","to":addr,"amount":out,"type":"buy_usdt","timestamp":int(time.time())}
        ensure_ledger().append(tx); add_tx_to_block(tx)
        logging.info(f"BUY: {addr} bought {out} VLC for {usdt} USDT")
        return jsonify({"vlc":out})
    except Exception as e:
        return jsonify({"error":str(e)}),500

@app.route("/sell",methods=["POST"])
def sell():
    try:
        d=request.json
        addr=d["address"]
        vlc=float(d["vlc"])
        s=load_state(); p=ensure_pool()
        price = price_usdt(p)
        if price<=0: return jsonify({"error":"no liquidity"}),400
        if s.get(addr,0)<vlc: return jsonify({"error":"balance"}),400
        usdt = vlc * price
        if usdt>p["usdt"]: return jsonify({"error":"insufficient pool USDT"}),400
        p["usdt"] -= usdt
        p["velcoin"] += vlc
        s[addr] -= vlc
        save_json(POOL_FILE,p); save_state(s)
        tx={"tx_hash":sha256(str(time.time())),"from":addr,"to":"POOL","amount":vlc,"type":"sell","timestamp":int(time.time())}
        ensure_ledger().append(tx); add_tx_to_block(tx)
        logging.info(f"SELL: {addr} sold {vlc} VLC for {usdt} USDT")
        return jsonify({"usdt":usdt})
    except Exception as e:
        return jsonify({"error":str(e)}),500

# -----------------------
# INIT
create_genesis_block()
ensure_pool()
ensure_ledger()
threading.Thread(target=check_deposits_loop,daemon=True).start()

if __name__=="__main__":
    port = int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0", port=port)
