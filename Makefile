
.PHONY: device-tree build install apply-dt

PYTHON=python3

all: device-tree build

device-tree:
	$(MAKE) -C device-tree

build:
	$(PYTHON) setup.py build

install: device-tree/opimidi.dtbo build
	install -m 644 device-tree/opimidi.dtbo /boot/dtb/overlay/opimidi.dtbo
	ln -sf /boot/dtb/overlay/opimidi.dtbo /lib/firmware/opimidi.dtbo
	$(PYTHON) setup.py install --skip-build

apply-dt:
	! [ -d /sys/kernel/config/device-tree/overlays/opimidi ] || rmdir /sys/kernel/config/device-tree/overlays/opimidi
	mkdir /sys/kernel/config/device-tree/overlays/opimidi
	echo opimidi.dtbo > /sys/kernel/config/device-tree/overlays/opimidi/patha
