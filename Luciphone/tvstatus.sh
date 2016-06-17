#!/bin/bash
echo 'pow 0' | cec-client -t p -p 1 -d 1 -s | tail -n1 | grep 'power' | awk '{print $3}'
