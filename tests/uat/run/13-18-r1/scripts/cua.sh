#!/bin/bash
# usage: cua.sh <tool> '<json>'
echo "$2" | MSYS_NO_PATHCONV=1 docker exec -i -u cua fcb-desktop bash -c 'eval "$(fcb-session-env)"; /usr/local/bin/cua-driver call '"$1"
