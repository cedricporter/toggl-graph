#!/bin/bash
#
# File: cron.sh
#
# Created: 星期五, 十一月  8 2013 by Hua Liang[Stupid ET] <et@everet.org>
#

COUNTER=0
while [  $COUNTER -lt 10 ]; do
    echo The counter is $COUNTER
    # let COUNTER=COUNTER+1
    curl -L $1
    sleep $2
done
