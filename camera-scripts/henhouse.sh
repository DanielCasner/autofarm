#!/usr/bin/env sh
raspivid -o - -t 0 -hf -w 720 -h 480 -fps 25 | cvlc -vvv stream:///dev/stdin --sout '#rtp{sdp=rtsp://:8554/henhouse}' :demux=h264
