#!/usr/bin/env sh
set -e

# Determine the default module name
if [ -f /app/app/main.py ]; then
    DEFAULT_MODULE_NAME=app.main
elif [ -f /app/main.py ]; then
    DEFAULT_MODULE_NAME=main
fi
MODULE_NAME=${MODULE_NAME:-$DEFAULT_MODULE_NAME}
VARIABLE_NAME=${VARIABLE_NAME:-app}
export APP_MODULE=${APP_MODULE:-"$MODULE_NAME:$VARIABLE_NAME"}

HOST=${HOST:-0.0.0.0}
PORT=${POSTGRES_SERVICE_PORT:-5434}  
LOG_LEVEL=${LOG_LEVEL:-info}

# Check and run prestart script
PRE_START_PATH=${PRE_START_PATH:-/app/prestart.sh}
echo "Checking for script in $PRE_START_PATH"
if [ -f $PRE_START_PATH ] ; then
    echo "Running script $PRE_START_PATH"
    . "$PRE_START_PATH"
else 
    echo "There is no script $PRE_START_PATH"
fi

# Configure Logfire and set up auto-tracing
# python -c "
# import os
# import logfire
# if os.environ.get('LOGFIRE_API_KEY') != '':
#     logfire.configure()
#     logfire.install_auto_tracing(modules=['app'], min_duration=0.01)
# else:
#     print('No LOGFIRE_API_KEY found, continuing without database tracing')
# "

# Start Uvicorn with live reload
exec uvicorn --reload --host $HOST --port $PORT --log-level $LOG_LEVEL "$APP_MODULE"

