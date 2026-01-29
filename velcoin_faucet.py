import sys
import json
import requests
import os
import hmac
import hashlib

FOUNDER_FILE = "wallet.json"
NODE_URL = "http://127.0.0.1:5000"

def sign_message(private_key, message):
    return hmac.new(private_key.encode(), message.encode(), hashlib.sha256).hexdigest()

def load_wallet():
    with open(FOUNDER_FILE, "r") as f:
        return json.load(f)

def faucet(user_index, amount):
    user_file = "wallet_user.json"
    with open(user_file, "r") as f:
        users = json.load(f)
    recipient = users[int(user_index)]["address"]
    founder = load_wallet()
    message = f"{founder['address']}->{recipient}:{amount}"
    signature = sign_message(founder["private_key"], message)
    data = {"from": founder["address"], "to": recipient, "amount": amount, "signature": signature, "private_key": founder["private_key"]}
    r = requests.post(f"{NODE_URL}/transfer", json=data)
    if r.status_code == 200:
        print(f"✅ Transferencia de {amount} VLC a {recipient} completada")
        print(f"Respuesta nodo: {r.json()}")
    else:
        print(f"❌ Error en transferencia: {r.json()}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python velcoin_faucet.py <user_index> <amount>")
    else:
        faucet(sys.argv[1], int(sys.argv[2]))
