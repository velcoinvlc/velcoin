#!/bin/bash
# ==========================================
# Setup de Producción Termux para VelCoin
# ==========================================

echo "🔧 Iniciando setup de producción Termux para VelCoin..."

# Crear carpetas necesarias
mkdir -p ~/velcoin/logs ~/velcoin/backups ~/velcoin/scripts

# ===============================
# 1️⃣ Script para iniciar nodo
# ===============================
cat > ~/velcoin/scripts/start_node.sh << 'EON'
#!/bin/bash
# Iniciar nodo VelCoin en background
LOG_FILE=~/velcoin/logs/velcoin_node.log
echo "🟢 Iniciando nodo VelCoin..."
nohup python ~/velcoin/app.py >> $LOG_FILE 2>&1 &
NODE_PID=$!
echo $NODE_PID > ~/velcoin/velcoin_node.pid
echo "✅ Nodo iniciado con PID $NODE_PID, logs en $LOG_FILE"
EON
chmod +x ~/velcoin/scripts/start_node.sh

# ===============================
# 2️⃣ Script para backup automático
# ===============================
cat > ~/velcoin/scripts/backup_state.sh << 'EOB'
#!/bin/bash
# Backup diario de state y wallets
BACKUP_DIR=~/velcoin/backups
DATE=$(date +%Y%m%d_%H%M%S)
cp ~/velcoin/state.json $BACKUP_DIR/state_$DATE.json
cp ~/velcoin/wallet.json $BACKUP_DIR/wallet_$DATE.json
cp ~/velcoin/wallet_user.json $BACKUP_DIR/wallet_user_$DATE.json
echo "💾 Backup completado: $DATE"
EOB
chmod +x ~/velcoin/scripts/backup_state.sh

# ===============================
# 3️⃣ Script para chequeos periódicos
# ===============================
cat > ~/velcoin/scripts/check_node.sh << 'EOC'
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
EOC
chmod +x ~/velcoin/scripts/check_node.sh

# ===============================
# 4️⃣ Configurar Termux Job Scheduler
# ===============================
echo "📆 Configurando tareas periódicas con termux-job-scheduler..."

# Backup diario a medianoche
termux-job-scheduler -s 0:0:0 -t 24h -c "~/velcoin/scripts/backup_state.sh" -n "velcoin_backup"

# Chequeo nodo cada 5 minutos
termux-job-scheduler -s 0:0:0 -t 5m -c "~/velcoin/scripts/check_node.sh" -n "velcoin_check"

# ===============================
# 5️⃣ Iniciar nodo por primera vez
# ===============================
echo "🟢 Iniciando nodo VelCoin..."
~/velcoin/scripts/start_node.sh

# ===============================
# 6️⃣ Chequeo inicial
# ===============================
echo "🔎 Realizando chequeo inicial..."
python ~/velcoin/velcoin_check.py

echo "🎉 Setup de producción Termux completado. Nodo listo y funcionando."
