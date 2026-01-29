#!/bin/bash
echo "🔧 Iniciando setup simplificado de producción VelCoin..."

# Carpetas de logs y backups
mkdir -p ~/velcoin/logs ~/velcoin/backups

# Script para iniciar nodo en background
cat > ~/velcoin/scripts/start_node.sh << 'EON'
#!/bin/bash
LOG_FILE=~/velcoin/logs/velcoin_node.log
echo "🟢 Iniciando nodo VelCoin..."
nohup python ~/velcoin/app.py >> $LOG_FILE 2>&1 &
NODE_PID=$!
echo $NODE_PID > ~/velcoin/velcoin_node.pid
echo "✅ Nodo iniciado con PID $NODE_PID, logs en $LOG_FILE"
EON
chmod +x ~/velcoin/scripts/start_node.sh

# Script para backup diario
cat > ~/velcoin/scripts/backup_state.sh << 'EOB'
#!/bin/bash
BACKUP_DIR=~/velcoin/backups
DATE=$(date +%Y%m%d_%H%M%S)
cp ~/velcoin/state.json $BACKUP_DIR/state_$DATE.json
cp ~/velcoin/wallet.json $BACKUP_DIR/wallet_$DATE.json
cp ~/velcoin/wallet_user.json $BACKUP_DIR/wallet_user_$DATE.json
echo "💾 Backup completado: $DATE"
EOB
chmod +x ~/velcoin/scripts/backup_state.sh

# Script de chequeo
cat > ~/velcoin/scripts/deploy_cron.sh << 'EOC'
#!/bin/bash
NODE_URL="http://127.0.0.1:5000"
FUNDADORA=$(cat ~/velcoin/wallet.json | jq -r '.address')

# Verificar nodo
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
chmod +x ~/velcoin/scripts/deploy_cron.sh

# Configurar cron jobs
crontab -l > /tmp/mycron 2>/dev/null
grep -v "velcoin" /tmp/mycron > /tmp/mycron_cleaned
echo "*/5 * * * * ~/velcoin/scripts/deploy_cron.sh >> ~/velcoin/logs/cron.log 2>&1" >> /tmp/mycron_cleaned
echo "0 0 * * * ~/velcoin/scripts/backup_state.sh >> ~/velcoin/logs/backup.log 2>&1" >> /tmp/mycron_cleaned
crontab /tmp/mycron_cleaned
rm /tmp/mycron /tmp/mycron_cleaned

# Iniciar nodo por primera vez
~/velcoin/scripts/start_node.sh

# Prueba rápida
python ~/velcoin/velcoin_check.py

echo "🎉 Setup simplificado de producción completado. Nodo listo y funcionando."
