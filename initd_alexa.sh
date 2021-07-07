#! /bin/bash

### BEGIN INIT INFO
# Provides:          AlexaOPi
# Required-Start:    $all
# Required-Stop:     $all
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: AlexaOPi Service
# Description:       Start / Stop AlexaOPi Service
### END INIT INFO

exec > /var/log/alexa.log 2>&1
case "$1" in

start)
    echo "Starting Alexa..."
    python /opt/AlexaOPi/start.py /opt/AlexaOPi/Artoo.pmdl &

;;

stop)
    echo "Stopping Alexa.."
    pkill -f AlexaOPi\/start\.py
;;

restart|force-reload)
        echo "Restarting Alexa.."
        $0 stop
        sleep 2
        $0 start
        echo "Restarted."
;;
*)
        echo "Usage: $0 {start|stop|restart}"
        exit 1
esac
