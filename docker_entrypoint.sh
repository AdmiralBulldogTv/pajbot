#!/usr/bin/env bash

/app/venv/bin/python3 main.py --config "configs/config.ini" &
bpid=$!
echo "Started Bot: $bpid";

/app/venv/bin/uwsgi --ini "/app/uwsgi_shared.ini" --http "0.0.0.0:3000" --pyargv "--config configs/config.ini" &
wpid=$!
echo "Started Web: $wpid";

stop() {
    kill -SIGTERM $bpid;
    echo "Killing Bot: $bpid";
    kill -SIGTERM $wpid;
    echo "Killing Web: $wpid";

    echo "Waiting Bot: $bpid";
    wait $bpid;
    echo "Waiting Web: $wpid";
    wait $wpid;
    
    exit 0;
}

trap stop SIGTERM;

wait -n

echo "Shutting down :("

exit $? + 127
