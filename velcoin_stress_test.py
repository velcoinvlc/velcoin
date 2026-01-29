import json
import random
import requests
import time
import os

NODE_URL = "http://127.0.0.1:5000"
USER_WALLET_FILE = "wallet_user.json"
FOUNDER_WALLET_FILE = "wallet.json"

# --- Cargar wallets
def load_wallet(file):
    with open(file, "r") as f:
        data = json.load(f)
        # Puede ser lista de wallets o una sola wallet
        if isinstance(data, list):
            return data
        else:
            return [data]

# --- Función de transferencia simple
def send_transfer(sender_private, sender_address, recipient_address, amount):
    message = f"{sender_address}->{recipient_address}:{amount}"
    import hmac, hashlib
    signature = hmac.new(sender_private.encode(), message.encode(), hashlib.sha256).hexdigest()

    payload = {
        "from": sender_address,
        "to": recipient_address,
        "amount": amount,
        "signature": signature,
        "private_key": sender_private
    }

    r = requests.post(f"{NODE_URL}/transfer", json=payload)
    if r.status_code == 200:
        print(f"✅ Transferencia de {amount} VLC de {sender_address[:8]} a {recipient_address[:8]} completada")
    else:
        print(f"❌ Error: {r.json()}")

# --- Revisar balances
def show_balances():
    print("\n=== Balances ===")
    all_wallets = load_wallet(USER_WALLET_FILE) + load_wallet(FOUNDER_WALLET_FILE)
    for w in all_wallets:
        try:
            r = requests.get(f"{NODE_URL}/balance/{w['address']}")
            if r.status_code == 200:
                print(r.json())
            else:
                print(f"Error consultando balance de {w['address']}")
        except Exception as e:
            print("Excepción:", e)
    print("================\n")

# --- Main
def main():
    founders = load_wallet(FOUNDER_WALLET_FILE)
    users = load_wallet(USER_WALLET_FILE)

    founder = founders[0]
    print("1️⃣ Balance inicial de la wallet fundadora:")
    show_balances()

    print("2️⃣ Iniciando stress test: 10 transferencias aleatorias entre usuarios...")
    for i in range(10):
        sender = founder if random.random() < 0.5 else random.choice(users)
        recipient = random.choice(users)
        amount = random.randint(1, 1000)
        send_transfer(sender["private_key"], sender["address"], recipient["address"], amount)
        time.sleep(0.5)  # Pausa ligera

    print("\n3️⃣ Balances finales después del stress test:")
    show_balances()

if __name__ == "__main__":
    main()
