#!/usr/bin/env python3
import sys
import json
from decimal import Decimal, getcontext

getcontext().prec = 30

TOKEN_SYMBOL = "VLC"

# =========================
# Utils
# =========================
def format_number(value):
    return f"{value:,.2f}"

# =========================
# Mock blockchain data
# (aquí luego conectas TronScan o tu nodo real)
# =========================
MOCK_BALANCES = {
    "6d627bb087faa32a00ed18749af72185de31a038": Decimal("999972388"),
}

# =========================
# Commands
# =========================
def get_balance(address):
    balance = MOCK_BALANCES.get(address, Decimal("0"))
    print(f"💰 Balance: {format_number(balance)} {TOKEN_SYMBOL}")

def transfer(sender, recipient, amount):
    print("⚠️ Transferencia aún no implementada correctamente")
    print("👉 Se recomienda usar clave privada real y firma correcta")

# =========================
# Main
# =========================
def main():
    if len(sys.argv) < 3:
        print("Uso:")
        print("  python velcoin_wallet.py balance <address>")
        print("  python velcoin_wallet.py transfer <from> <to> <amount>")
        sys.exit(1)

    command = sys.argv[1]

    if command == "balance":
        address = sys.argv[2]
        get_balance(address)

    elif command == "transfer":
        if len(sys.argv) != 5:
            print("Uso: python velcoin_wallet.py transfer <from> <to> <amount>")
            sys.exit(1)
        sender = sys.argv[2]
        recipient = sys.argv[3]
        amount = Decimal(sys.argv[4])
        transfer(sender, recipient, amount)

    else:
        print("❌ Comando no reconocido")

if __name__ == "__main__":
    main()
