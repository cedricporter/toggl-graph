#!/bin/sh
#
# File: rebuild_blog.sh
#
# Created: 星期日, 十一月 24 2013 by Hua Liang[Stupid ET] <et@everet.org>
#

cd /home/projects/my-summary && git pull && rake gen_deploy
