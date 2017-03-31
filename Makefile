
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
	install -m 644 systemd/10-opimidi.rules /etc/udev/rules.d/10-opimidi.rules
	install -m 644 systemd/hwclock.service /etc/systemd/system/hwclock.service
	systemctl enable hwclock.service
	install -m 644 systemd/opimidi_usb.service /etc/systemd/system/opimidi_usb.service
	install -m 644 systemd/opimidi_perms.service /etc/systemd/system/opimidi_perms.service
	install -m 644 systemd/opimidi_be.service /etc/systemd/system/opimidi_be.service
	install -m 644 systemd/opimidi_be.socket /etc/systemd/system/opimidi_be.socket
	install -m 644 systemd/opimidi_fe.service /etc/systemd/system/opimidi_fe.service
	systemctl enable opimidi_usb.service opimidi_be.service opimidi_fe.service opimidi_perms.service
	install -m 644 opimidi.config /etc/opimidi.config
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
