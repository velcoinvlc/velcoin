#!/bin/bash
# Chequeo de nodo y balances
NODE_URL="http://127.0.0.1:5000"
FUNDADORA=$(cat ~/velcoin/wallet.json | jq -r '.address')

# Revisar si nodo responde
STATUS=$(curl -s $NODE_URL/)
if [[ $STATUS != *"VelCoin node online"* ]]; then
    echo "❌ Nodo caído, reiniciando..."
    pkill -f "python ~/velcoin/app.py"
    ~/velcoin/scripts/start_node.sh
else
    echo "🟢 Nodo activo"
fi

# Balance fundadora
BALANCE=$(curl -s $NODE_URL/balance/$FUNDADORA | jq -r '.balance')
echo "💰 Balance fundadora $FUNDADORA: $BALANCE VLC"
