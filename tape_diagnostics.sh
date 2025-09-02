#!/bin/bash
# tape_diagnostics.sh

DEVICE=/dev/nst0
LOGDIR=/var/log/tape_diagnostics
mkdir -p $LOGDIR

DATE=$(date +%Y%m%d_%H%M%S)

echo "=== Tape Diagnostics $DATE ===" | tee $LOGDIR/report_$DATE.txt

echo -e "\n--- MT Status ---" | tee -a $LOGDIR/report_$DATE.txt
mt -f $DEVICE status | tee -a $LOGDIR/report_$DATE.txt

echo -e "\n--- Write Errors ---" | tee -a $LOGDIR/report_$DATE.txt
sg_logs --page=0x02 $DEVICE | tee -a $LOGDIR/report_$DATE.txt

echo -e "\n--- Read Errors ---" | tee -a $LOGDIR/report_$DATE.txt
sg_logs --page=0x03 $DEVICE | tee -a $LOGDIR/report_$DATE.txt

echo -e "\n--- Non-Medium Errors ---" | tee -a $LOGDIR/report_$DATE.txt
sg_logs --page=0x17 $DEVICE | tee -a $LOGDIR/report_$DATE.txt

echo -e "\n--- Tape Usage ---" | tee -a $LOGDIR/report_$DATE.txt
sg_logs --page=0x31 $DEVICE | tee -a $LOGDIR/report_$DATE.txt

echo -e "\n--- Kernel Messages ---" | tee -a $LOGDIR/report_$DATE.txt
dmesg | grep -i "st[0-9]\|scsi\|sense" | tail -20 | tee -a $LOGDIR/report_$DATE.txt


