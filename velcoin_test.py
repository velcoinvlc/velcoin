import requests
import json

NODE_URL = "http://127.0.0.1:5000"

# --- Tu wallet fundadora ---
WALLET_FILE = "wallet.json"

with open(WALLET_FILE, "r") as f:
    wallet = json.load(f)

SENDER = wallet["address"]
PUBLIC_KEY = wallet["public_key"]
PRIVATE_KEY = wallet["private_key"]  # solo para firmar localmente

# --- Funciones ---
def format_number(n):
    return f"{n:,.2f}"

def get_balance(address):
    r = requests.get(f"{NODE_URL}/balance/{address}")
    data = r.json()
    print(f"💰 Balance de {address}: {format_number(data.get('balance',0))} VLC")
    return data.get("balance",0)

def sign_transaction(sender, recipient, amount, private_key):
    import hashlib, ecdsa
    message = f"{sender}->{recipient}:{amount}"
    sk = ecdsa.SigningKey.from_string(bytes.fromhex(private_key), curve=ecdsa.SECP256k1)
    signature = sk.sign(hashlib.sha256(message.encode()).digest())
    return signature.hex()

def transfer(sender, recipient, amount, public_key, private_key):
    signature = sign_transaction(sender, recipient, amount, private_key)
    payload = {
        "from": sender,
        "to": recipient,
        "amount": amount,
        "public_key": public_key,
        "signature": signature
    }
    r = requests.post(f"{NODE_URL}/transfer", json=payload)
    data = r.json()
    print("📦 Respuesta nodo:")
    print(data)
    if "tx_hash" in data:
        print("🧾 TX HASH:", data["tx_hash"])

# --- EJEMPLO DE USO ---
if __name__ == "__main__":
    print("=== CONSULTA INICIAL ===")
    get_balance(SENDER)

    # --- TRANSFERENCIA DE PRUEBA ---
    TEST_RECIPIENT = "421fe2ca5041d7fcc82f0abb96a7f03080c2e17c"
    AMOUNT = 10

    print("\n=== TRANSFERENCIA DE PRUEBA ===")
    transfer(SENDER, TEST_RECIPIENT, AMOUNT, PUBLIC_KEY, PRIVATE_KEY)

    print("\n=== CONSULTA FINAL ===")
    get_balance(SENDER)
    get_balance(TEST_RECIPIENT)
