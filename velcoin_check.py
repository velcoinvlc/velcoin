#!/usr/bin/env python3
import requests
import json
import os
import sys
import time

NODE_URL = "http://127.0.0.1:5000"
FOUNDER_WALLET_FILE = "wallet.json"
USER_WALLET_FILE = "wallet_user.json"

def load_wallet(file):
    if not os.path.exists(file):
        print(f"❌ Archivo {file} no encontrado")
        return None
    with open(file, "r") as f:
        return json.load(f)

def check_node():
    try:
        r = requests.get(f"{NODE_URL}/")
        if r.status_code == 200:
            print("✅ Nodo activo:", r.json())
        else:
            print("❌ Nodo respondió con error:", r.status_code)
    except Exception as e:
        print("❌ No se pudo conectar al nodo:", e)

def check_balance(address, label="Wallet"):
    try:
        r = requests.get(f"{NODE_URL}/balance/{address}")
        if r.status_code == 200:
            data = r.json()
            print(f"💰 {label} {address} balance:", data["balance"], data["symbol"])
            return data["balance"]
        else:
            print(f"❌ Error consultando balance de {label} {address}: {r.status_code}")
    except Exception as e:
        print(f"❌ Error consultando balance de {label} {address}:", e)

def test_transfer(sender_priv, sender_addr, recipient_addr, amount=10):
    # Firma simple HMAC
    import hmac, hashlib
    message = f"{sender_addr}->{recipient_addr}:{amount}"
    signature = hmac.new(sender_priv.encode(), message.encode(), hashlib.sha256).hexdigest()
    payload = {
        "from": sender_addr,
        "to": recipient_addr,
        "amount": amount,
        "private_key": sender_priv,
        "signature": signature
    }
    try:
        r = requests.post(f"{NODE_URL}/transfer", json=payload)
        if r.status_code == 200:
            print(f"✅ Transferencia de prueba de {amount} VLC completada a {recipient_addr}")
            print("Respuesta nodo:", r.json())
        else:
            print(f"❌ Error en transferencia de prueba: {r.status_code}", r.text)
    except Exception as e:
        print("❌ Error en transferencia de prueba:", e)

def main():
    print("🔎 Iniciando chequeo completo VelCoin...\n")
    check_node()
    
    # Fundadora
    founder = load_wallet(FOUNDER_WALLET_FILE)
    if founder is None:
        return
    founder_addr = founder["address"]
    founder_priv = founder["private_key"]
    check_balance(founder_addr, "Fundadora")
    
    # Usuarios
    users = load_wallet(USER_WALLET_FILE)
    if users is None:
        users = []
    print("\n📋 Wallets de usuario y balances:")
    for i, w in enumerate(users):
        check_balance(w["address"], f"Usuario {i}")
    
    # Transferencia de prueba
    if users:
        test_transfer(founder_priv, founder_addr, users[0]["address"], amount=10)
        print("\n🔄 Verificando balances después de la transferencia de prueba...")
        check_balance(founder_addr, "Fundadora")
        check_balance(users[0]["address"], "Usuario 0")
    else:
        print("⚠️ No hay wallets de usuario para transferencia de prueba.")

if __name__ == "__main__":
    main()
