from flask import Flask, jsonify, request
import json, os, hashlib, time, threading
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
# POOL
def migrate_pool(p):
    p.setdefault("velcoin",1_000_000)
    p.setdefault("usdt",50_000)
    p.setdefault("trx",100_000)
    p.setdefault("history",[])
    return p

def ensure_pool():
    p = migrate_pool(load_json(POOL_FILE,{}))
    save_json(POOL_FILE,p)
    return p

def price_usdt(p): return p["usdt"]/p["velcoin"]
def price_trx(p): return p["trx"]/p["velcoin"]

# -----------------------
# TRON CONFIG
TRON_WALLET="TJXrApg9D7xPSdGKVdCeeCvsmDbiEbDL34"
TRONGRID="https://api.trongrid.io/v1/accounts"
USDT_CONTRACT="TLa2f6VPqDgRE67v1736s7bJ8Ray5wYjU7"

processed = set(load_json(PROCESSED_FILE, []))
last_trx_balance = 0

def save_processed():
    save_json(PROCESSED_FILE, list(processed))

def get_trx_balance():
    try:
        r=requests.get(f"{TRONGRID}/{TRON_WALLET}")
        data=r.json()
        return data["data"][0]["balance"]/1_000_000
    except:
        return 0

def scan_usdt_txs():
    try:
        r=requests.get(f"{TRONGRID}/{TRON_WALLET}/transactions/trc20?limit=50")
        data=r.json()["data"]
        new=0
        for tx in data:
            if tx["to"]!=TRON_WALLET: continue
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
    global last_trx_balance
    while True:
        try:
            p=ensure_pool()
            s=load_state()

            # TRX delta
            trx_now=get_trx_balance()
            delta_trx=max(trx_now-last_trx_balance,0)
            last_trx_balance=trx_now

            if delta_trx>0:
                vlc=delta_trx/price_trx(p)
                s[TRON_WALLET]=s.get(TRON_WALLET,0)+vlc
                save_state(s)
                tx={
                    "tx_hash":sha256(f"TRX:{time.time()}"),
                    "from":"TRON","to":TRON_WALLET,
                    "amount":vlc,"type":"buy_trx",
                    "timestamp":int(time.time())
                }
                ensure_ledger().append(tx)
                add_tx_to_block(tx)

            # USDT deposits
            new_usdt=scan_usdt_txs()
            if new_usdt>0:
                vlc=new_usdt/price_usdt(p)
                s[TRON_WALLET]=s.get(TRON_WALLET,0)+vlc
                save_state(s)
                tx={
                    "tx_hash":sha256(f"USDT:{time.time()}"),
                    "from":"TRON","to":TRON_WALLET,
                    "amount":vlc,"type":"buy_usdt",
                    "timestamp":int(time.time())
                }
                ensure_ledger().append(tx)
                add_tx_to_block(tx)

        except Exception as e:
            print("deposit loop error:",e)

        time.sleep(15)

# -----------------------
# API
@app.route("/status")
def status():
    p=ensure_pool(); s=load_state()
    return jsonify({
        "status":"online",
        "symbol":"VLC",
        "total_supply":sum(s.values()),
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
    return jsonify({"address":a,"balance":load_state().get(a,0)})

@app.route("/blocks")
def blocks(): return jsonify(load_blockchain())

@app.route("/buy",methods=["POST"])
def buy():
    d=request.json
    addr=d["address"]; usdt=float(d["usdt"])
    p=ensure_pool(); s=load_state()
    out=usdt/price_usdt(p)
    if out>p["velcoin"]: return jsonify({"error":"liquidity"}),400
    p["usdt"]+=usdt; p["velcoin"]-=out
    s[addr]=s.get(addr,0)+out
    save_json(POOL_FILE,p); save_state(s)
    tx={"tx_hash":sha256(str(time.time())),"from":"POOL","to":addr,"amount":out}
    ensure_ledger().append(tx); add_tx_to_block(tx)
    return jsonify({"vlc":out})

@app.route("/sell",methods=["POST"])
def sell():
    d=request.json
    addr=d["address"]; vlc=float(d["vlc"])
    s=load_state(); p=ensure_pool()
    if s.get(addr,0)<vlc: return jsonify({"error":"balance"}),400
    usdt=vlc*price_usdt(p)
    p["usdt"]-=usdt; p["velcoin"]+=vlc
    s[addr]-=vlc
    save_json(POOL_FILE,p); save_state(s)
    tx={"tx_hash":sha256(str(time.time())),"from":addr,"to":"POOL","amount":vlc}
    ensure_ledger().append(tx); add_tx_to_block(tx)
    return jsonify({"usdt":usdt})

# -----------------------
# INIT FOR GUNICORN / RENDER
create_genesis_block()
ensure_pool()
ensure_ledger()

threading.Thread(target=check_deposits_loop,daemon=True).start()
