#!/bin/bash
# Script todo-en-uno para levantar nodo VelCoin y hacer chequeo completo

LOG_FILE=~/velcoin/logs/velcoin_node.log
PID_FILE=~/velcoin/velcoin_node.pid
NODE_URL="http://127.0.0.1:5000"

echo "🔹 Deteniendo cualquier nodo VelCoin activo..."
if [ -f "$PID_FILE" ]; then
    kill $(cat $PID_FILE) 2>/dev/null
    rm -f $PID_FILE
fi
pkill -f "python ~/velcoin/app.py" 2>/dev/null

# Liberar puerto 5000 si está ocupado
echo "🔹 Verificando puerto 5000..."
PID_PORT=$(lsof -ti :5000)
if [ ! -z "$PID_PORT" ]; then
    echo "❌ Puerto 5000 ocupado por PID $PID_PORT, matando proceso..."
    kill -9 $PID_PORT
fi

echo "🟢 Iniciando nodo VelCoin en background..."
nohup python ~/velcoin/app.py >> $LOG_FILE 2>&1 &
NODE_PID=$!
echo $NODE_PID > $PID_FILE
echo "✅ Nodo iniciado con PID $NODE_PID, logs en $LOG_FILE"

sleep 5

echo "🔎 Realizando chequeo completo y transferencia de prueba..."
python ~/velcoin/velcoin_check.py

echo "🎉 Nodo listo y funcionando. Revisa logs con: tail -f $LOG_FILE"
