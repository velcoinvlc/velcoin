#!/bin/bash
# Backup diario de state y wallets
BACKUP_DIR=~/velcoin/backups
DATE=$(date +%Y%m%d_%H%M%S)
cp ~/velcoin/state.json $BACKUP_DIR/state_$DATE.json
cp ~/velcoin/wallet.json $BACKUP_DIR/wallet_$DATE.json
cp ~/velcoin/wallet_user.json $BACKUP_DIR/wallet_user_$DATE.json
echo "💾 Backup completado: $DATE"
