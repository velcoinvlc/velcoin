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
WALLET_FILE = os.path.join(BASE_DIR, "wallet.json")  # Local wallets, nunca en GitHub

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

def create_genesis_block():
    chain = load_blockchain()
    if chain: return
    g = {
        "index":0,
        "timestamp":int(time.time()),
        "transactions":[],
        "previous_hash":"0"*64
    }
    g["block_hash"]=sha256(json.dumps(g,sort_keys=True))
    chain.append(g)
    save_blockchain(chain)

def add_tx_to_block(tx):
    chain = load_blockchain()
    last = chain[-1]
    b = {
        "index": last["index"]+1,
        "timestamp": int(time.time()),
        "transactions":[tx],
        "previous_hash": last["block_hash"]
    }
    b["block_hash"]=sha256(json.dumps(b,sort_keys=True))
    chain.append(b)
    save_blockchain(chain)

# -----------------------
# WALLET CONFIG
TRX_WALLET = "TJXrApg9D7xPSdGKVdCeeCvsmDbiEbDL34"        # Wallet real de TRX/USDT
FUND_WALLET = None  # Se cargará desde wallet.json
TRONGRID = "https://api.trongrid.io/v1/accounts"
USDT_CONTRACT = "TLa2f6VPqDgRE67v1736s7bJ8Ray5wYjU7"

processed = set(load_json(PROCESSED_FILE, []))
last_trx_balance = 0
last_usdt_balance = 0

def save_processed():
    save_json(PROCESSED_FILE, list(processed))

# -----------------------
# CARGAR WALLET FUNDADORA
def load_fund_wallet():
    global FUND_WALLET
    wallets = load_json(WALLET_FILE, [])
    if wallets:
        FUND_WALLET = wallets[0]["address"]
    else:
        logging.error("No se encontró wallet fundadora. Crear wallet.json local en el servidor.")

# -----------------------
# POOL REAL
def ensure_pool():
    """
    Pool real: toma saldo actual de wallets TRX y USDT
    y cantidad de VLC en wallet fundadora.
    """
    p = load_json(POOL_FILE,{})
    try:
        # Saldo real TRX
        trx_balance = get_trx_balance(TRX_WALLET)
        # Saldo real USDT
        usdt_balance = scan_usdt_txs(TRX_WALLET)
        # Saldo VLC real
        s = load_state()
        vlc_balance = s.get(FUND_WALLET,0)

        p = {
            "trx": trx_balance,
            "usdt": usdt_balance,
            "velcoin": vlc_balance,
            "history": [],
        }
        save_json(POOL_FILE,p)
        return p
    except Exception as e:
        logging.error(f"Error al cargar pool: {e}")
        # fallback en caso de error
        return {"trx":0,"usdt":0,"velcoin":0,"history":[]}

def price_usdt(p): return p["usdt"]/p["velcoin"] if p["velcoin"]>0 else 0
def price_trx(p): return p["trx"]/p["velcoin"] if p["velcoin"]>0 else 0

def get_total_supply():
    s = load_state()
    p = load_json(POOL_FILE, {})
    return sum(s.values())

# -----------------------
# FUNCIONES DE TRON
def get_trx_balance(wallet):
    try:
        r = requests.get(f"{TRONGRID}/{wallet}")
        data = r.json()
        balance = int(data["data"][0]["balance"])
        return float(f"{balance/1_000_000:.6f}")  # 6 decimales exactos
    except:
        return 0

def scan_usdt_txs(wallet):
    try:
        r=requests.get(f"{TRONGRID}/{wallet}/transactions/trc20?limit=50")
        data=r.json()["data"]
        new=0
        for tx in data:
            if tx["to"]!=wallet: continue
            if tx["contract_address"]!=USDT_CONTRACT: continue
            h=tx["transaction_id"]
            if h in processed: continue
            processed.add(h)
            new += int(tx["value"])/1_000_000
        save_processed()
        return new
    except:
        return 0

# -----------------------
# DEPOSIT MONITOR
def check_deposits_loop():
    global last_trx_balance, last_usdt_balance
    while True:
        try:
            p = ensure_pool()
            s = load_state()

            # TRX delta
            trx_now = get_trx_balance(TRX_WALLET)
            delta_trx = max(trx_now - last_trx_balance, 0)
            last_trx_balance = trx_now

            if delta_trx>0:
                price = price_trx(p)
                if price>0:
                    vlc = delta_trx / price
                    s[FUND_WALLET] = s.get(FUND_WALLET,0) + vlc
                    save_state(s)
                    tx={
                        "tx_hash":sha256(f"TRX:{time.time()}"),
                        "from":"TRON",
                        "to":FUND_WALLET,
                        "amount":vlc,
                        "type":"buy_trx",
                        "timestamp":int(time.time())
                    }
                    ensure_ledger().append(tx)
                    add_tx_to_block(tx)
                    logging.info(f"Deposit TRX: {delta_trx} TRX -> {vlc} VLC")

            # USDT delta
            usdt_now = scan_usdt_txs(TRX_WALLET)
            delta_usdt = max(usdt_now - last_usdt_balance, 0)
            last_usdt_balance = usdt_now

            if delta_usdt>0:
                price = price_usdt(p)
                if price>0:
                    vlc = delta_usdt / price
                    s[FUND_WALLET] = s.get(FUND_WALLET,0) + vlc
                    save_state(s)
                    tx={
                        "tx_hash":sha256(f"USDT:{time.time()}"),
                        "from":"TRON",
                        "to":FUND_WALLET,
                        "amount":vlc,
                        "type":"buy_usdt",
                        "timestamp":int(time.time())
                    }
                    ensure_ledger().append(tx)
                    add_tx_to_block(tx)
                    logging.info(f"Deposit USDT: {delta_usdt} USDT -> {vlc} VLC")

        except Exception as e:
            logging.error(f"Deposit loop error: {e}")

        time.sleep(15)

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
    if a == TRX_WALLET:
        trx_balance = get_trx_balance(TRX_WALLET)
        return jsonify({"address": a, "balance": f"{trx_balance:.6f}"})
    b = load_state().get(a, 0)
    return jsonify({"address": a, "balance": f"{b:.6f}"})

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
        if price <= 0: return jsonify({"error":"no liquidity or price undefined"}),400
        out = usdt / price
        if out>p["velcoin"]: return jsonify({"error":"liquidity"}),400
        p["usdt"] += usdt; p["velcoin"] -= out
        s[addr] = s.get(addr,0) + out
        save_json(POOL_FILE,p); save_state(s)
        tx={"tx_hash":sha256(str(time.time())),"from":"POOL","to":addr,"amount":out,"type":"buy_usdt","timestamp":int(time.time())}
        ensure_ledger().append(tx); add_tx_to_block(tx)
        logging.info(f"BUY: {addr} bought {out} VLC for {usdt} USDT")
        return jsonify({"vlc":out})
    except Exception as e:
        return jsonify({"error": str(e)}),500

@app.route("/sell",methods=["POST"])
def sell():
    try:
        d=request.json
        addr=d["address"]
        vlc=float(d["vlc"])
        s=load_state(); p=ensure_pool()
        price = price_usdt(p)
        if price <= 0: return jsonify({"error":"no liquidity or price undefined"}),400
        if s.get(addr,0)<vlc: return jsonify({"error":"balance"}),400
        usdt = vlc * price
        if usdt > p["usdt"]: return jsonify({"error":"insufficient pool USDT"}),400
        p["usdt"] -= usdt; p["velcoin"] += vlc
        s[addr]-=vlc
        save_json(POOL_FILE,p); save_state(s)
        tx={"tx_hash":sha256(str(time.time())),"from":addr,"to":"POOL","amount":vlc,"type":"sell","timestamp":int(time.time())}
        ensure_ledger().append(tx); add_tx_to_block(tx)
        logging.info(f"SELL: {addr} sold {vlc} VLC for {usdt} USDT")
        return jsonify({"usdt":usdt})
    except Exception as e:
        return jsonify({"error": str(e)}),500

# -----------------------
# INIT
load_fund_wallet()
create_genesis_block()
ensure_pool()
ensure_ledger()
threading.Thread(target=check_deposits_loop,daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0", port=port)
