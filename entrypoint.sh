#!/bin/bash
cd /

if [[ -n "$INPUT_LOGGROUPNAME" && -n "$INPUT_LOGSTREAMPREFIX" ]]; then
    python3 python_cicd.py $INPUT_APPLICATION $INPUT_ENVIRONMENT -g $INPUT_LOGGROUPNAME -p $INPUT_LOGSTREAMPREFIX
elif [[ -n "$INPUT_LOGGROUPNAME" && -z "$INPUT_LOGSTREAMPREFIX" ]]; then
    python3 python_cicd.py $INPUT_APPLICATION $INPUT_ENVIRONMENT -g $INPUT_LOGGROUPNAME
elif [[ -z "$INPUT_LOGGROUPNAME" && -n "$INPUT_LOGSTREAMPREFIX" ]]; then
    python3 python_cicd.py $INPUT_APPLICATION $INPUT_ENVIRONMENT -p $INPUT_LOGSTREAMPREFIX
else
    python3 python_cicd.py $INPUT_APPLICATION $INPUT_ENVIRONMENT
fi
