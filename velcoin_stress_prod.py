import json
import random
import os
import subprocess

WALLET_FOUNDER_FILE = "wallet.json"
WALLET_USERS_FILE = "wallet_user.json"
LOG_FILE = "velcoin_stress_log.json"

NUM_TRANSFERS = 50  # Ajusta aquí la cantidad de transferencias a simular

# --- Cargar wallets ---
def load_wallets(file):
    if not os.path.exists(file):
        return []
    with open(file, "r") as f:
        data = json.load(f)
        # Acepta tanto lista de wallets (usuarios) como dict (fundadora)
        if isinstance(data, dict):
            return [data]
        return data

founder = load_wallets(WALLET_FOUNDER_FILE)[0]
users = load_wallets(WALLET_USERS_FILE)

# --- Asegurar al menos 5 wallets de usuario ---
if len(users) < 5:
    for _ in range(5 - len(users)):
        # Crear nueva wallet de usuario usando CLI
        subprocess.run(["python", "velcoin_wallet.py", "new", WALLET_USERS_FILE])
    users = load_wallets(WALLET_USERS_FILE)

all_wallets = [founder] + users

# --- Función para enviar transferencia ---
def send_transfer(sender, recipient, amount):
    # Usa faucet para simular transferencia de VLC
    result = subprocess.run(
        ["python", "velcoin_faucet.py", str(all_wallets.index(sender)), str(amount)],
        capture_output=True,
        text=True
    )
    return result.stdout.strip()

# --- Registrar log ---
log = []

print(f"📊 Iniciando stress test con {NUM_TRANSFERS} transferencias...")

for _ in range(NUM_TRANSFERS):
    sender = random.choice(all_wallets)
    recipient = random.choice(all_wallets)
    while recipient["address"] == sender["address"]:
        recipient = random.choice(all_wallets)
    amount = random.randint(1, 1000)
    try:
        output = send_transfer(sender, recipient, amount)
        log.append({
            "from": sender["address"],
            "to": recipient["address"],
            "amount": amount,
            "status": "sent",
            "output": output
        })
        print(f"✅ {amount} VLC de {sender['address'][:8]} a {recipient['address'][:8]} completada")
    except Exception as e:
        log.append({
            "from": sender["address"],
            "to": recipient["address"],
            "amount": amount,
            "status": "error",
            "error": str(e)
        })
        print(f"❌ Error en transferencia de {amount} VLC de {sender['address'][:8]} a {recipient['address'][:8]}: {e}")

# --- Guardar log completo ---
with open(LOG_FILE, "w") as f:
    json.dump(log, f, indent=2)

# --- Mostrar balances finales ---
print("\n🏦 Balances finales:")
for w in all_wallets:
    try:
        output = subprocess.run(
            ["python", "velcoin_wallet.py", "balance", w.get("address", "")],
            capture_output=True, text=True
        )
        print(output.stdout.strip())
    except Exception as e:
        print(f"❌ No se pudo consultar balance de {w['address']}: {e}")
