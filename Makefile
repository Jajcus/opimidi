
.PHONY: device-tree build install

PYTHON=python3

all: device-tree build

device-tree:
	$(MAKE) -C device-tree

build:
	$(PYTHON) setup.py build

install: device-tree/opimidi.dtbo
	install -m 644 device-tree/opimidi.dtbo /boot/dtb/overlay/opimidi.dtbo
	install -m 644 device-tree/opimidi-tinyrtc.dtbo /boot/dtb/overlay/opimidi-tinyrtc.dtbo
	ln -sf /boot/dtb/overlay/opimidi-tinyrtc.dtbo /lib/firmware/opimidi-tinyrtc.dtbo
	install -m 644 systemd/hwclock.service /etc/systemd/system/hwclock.service
	install -m 644 systemd/10-opimidi.rules /etc/udev/rules.d/10-opimidi.rules
	systemctl enable hwclock.service
	$(PYTHON) setup.py install --skip-build

.PHONY: apply-dt apply-dt-rtc

apply-dt:
	! [ -d /sys/kernel/config/device-tree/overlays/opimidi ] || rmdir /sys/kernel/config/device-tree/overlays/opimidi
	mkdir /sys/kernel/config/device-tree/overlays/opimidi
	echo opimidi.dtbo > /sys/kernel/config/device-tree/overlays/opimidi/path

apply-dt-rtc:
	! [ -d /sys/kernel/config/device-tree/overlays/opimidi-tinyrtc ] || rmdir /sys/kernel/config/device-tree/overlays/opimidi-tinyrtc
	mkdir /sys/kernel/config/device-tree/overlays/opimidi-tinyrtc
	echo opimidi-tinyrtc.dtbo > /sys/kernel/config/device-tree/overlays/opimidi-tinyrtc/path
