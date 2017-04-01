#!/bin/sh -e

name=$1

if [ ! -n "$name" -o "$name" = "-h" -o "$name" = "--help" ] ; then
	echo "Usage:"
	echo "    $0 name.dtbo"
	exit 0
fi

if [ ! -f /lib/firmware/$name ] ; then
	echo "/lib/firmware/$name missing" 
	exit 1
fi

! [ -d /sys/kernel/config/device-tree/overlays/opimidi ] || rmdir /sys/kernel/config/device-tree/overlays/opimidi
mkdir /sys/kernel/config/device-tree/overlays/opimidi
echo opimidi.dtbo > /sys/kernel/config/device-tree/overlays/opimidi/path
