#! /bin/bash

### BEGIN INIT INFO
# Provides:          AlexaPi
# Required-Start:    $all
# Required-Stop:     $all
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: AlexaPi Service
# Description:       Start / Stop AlexaPi Service
### END INIT INFO

exec > /var/log/alexa.log 2>&1 
case "$1" in

start)
    echo "Starting Alexa..."
    python /opt/AlexaPi/start.py /opt/AlexaPi/Artoo.pmdl &
    /opt/AlexaPi/monitorAlexa.sh &
;;

silent)
    echo "Starting Alexa in silent mode..."
    python /opt/AlexaPi/start.py /opt/AlexaPi/Artoo.pmdl &
;;

stop)
    echo "Stopping Alexa.."
    pkill -f AlexaPi\/start\.py
;;

restart|force-reload)
        echo "Restarting Alexa.."
        $0 stop
        sleep 2
        $0 start
        echo "Restarted."
;;
*)
        echo "Usage: $0 {start|silent|stop|restart}"
        exit 1
esac
