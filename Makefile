
PYTHON=python3

all: device-tree build

device-tree:
	$(MAKE) -C device-tree

build:
	$(PYTHON) setup.py build

install:
	$(MAKE) -C device-tree install
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

apply-dt:
	$(MAKE) -C device-tree apply-dt

.PHONY: all device-tree build install apply-dt
