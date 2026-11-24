#!/bin/bash
# usage: cua.sh <tool> '<json>'
export MSYS_NO_PATHCONV=1
echo "$2" | docker exec -i -u cua fcb-desktop bash -c 'eval "$(fcb-session-env)"; /usr/local/bin/cua-driver call '"$1"
