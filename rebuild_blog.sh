#!/bin/bash
#
# File: rebuild_blog.sh
#
# Created: 星期日, 十一月 24 2013 by Hua Liang[Stupid ET] <et@everet.org>
#

(
    flock -x -w 10 345 || exit 1

    cd /home/projects/my-summary && git pull && rake gen_deploy

) 345>/var/lock/.$(basename $0).exclusivelock
