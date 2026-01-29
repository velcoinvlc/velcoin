#!/bin/bash
# Iniciar nodo VelCoin en background
LOG_FILE=~/velcoin/logs/velcoin_node.log
echo "🟢 Iniciando nodo VelCoin..."
nohup python ~/velcoin/app.py >> $LOG_FILE 2>&1 &
NODE_PID=$!
echo $NODE_PID > ~/velcoin/velcoin_node.pid
echo "✅ Nodo iniciado con PID $NODE_PID, logs en $LOG_FILE"
