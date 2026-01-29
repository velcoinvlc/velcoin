#!/bin/bash
# Script maestro de setup de producción VelCoin (versión segura)
# Evita duplicar procesos y asegura que todo esté listo para producción

VELCOIN_DIR=~/velcoin
LOG_DIR=$VELCOIN_DIR/logs
BACKUP_DIR=$VELCOIN_DIR/backups
SCRIPTS_DIR=$VELCOIN_DIR/scripts
NODE_PID_FILE=$VELCOIN_DIR/velcoin_node.pid

echo "🔧 Iniciando setup seguro de producción VelCoin..."

# Crear carpetas necesarias
mkdir -p $LOG_DIR $BACKUP_DIR $SCRIPTS_DIR
echo "📂 Carpetas de logs y backups listas."

# Asegurar permisos de scripts base
chmod +x $SCRIPTS_DIR/start_node.sh
chmod +x $SCRIPTS_DIR/backup_state.sh
chmod +x $SCRIPTS_DIR/deploy_cron.sh
echo "⚙️ Scripts base listos y permisos asignados."

# Verificar si nodo ya está corriendo
if [ -f "$NODE_PID_FILE" ]; then
    NODE_PID=$(cat $NODE_PID_FILE)
    if ps -p $NODE_PID > /dev/null 2>&1; then
        echo "🟢 Nodo VelCoin ya está corriendo con PID $NODE_PID."
    else
        echo "⚠️ Nodo PID file encontrado pero proceso no existe. Reiniciando nodo..."
        $SCRIPTS_DIR/start_node.sh
    fi
else
    echo "🟢 Nodo no está corriendo. Iniciando..."
    $SCRIPTS_DIR/start_node.sh
fi

# Configurar cron jobs (evita duplicados)
echo "📆 Configurando cron jobs seguros..."
(crontab -l 2>/dev/null | grep -v "velcoin/scripts/deploy_cron.sh" | grep -v "velcoin/scripts/backup_state.sh"; \
echo "*/5 * * * * $SCRIPTS_DIR/deploy_cron.sh >> $LOG_DIR/cron.log 2>&1"; \
echo "0 0 * * * $SCRIPTS_DIR/backup_state.sh >> $LOG_DIR/backup.log 2>&1") | crontab -
echo "✅ Cron jobs configurados sin duplicados."

# Test rápido de nodo y wallets
echo "🔎 Haciendo chequeo seguro del nodo y wallets..."
python3 $VELCOIN_DIR/velcoin_check.py

echo "🎉 Setup seguro de producción completado. Nodo listo y funcionando."
