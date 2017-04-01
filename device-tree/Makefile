
DTC=dtc

OVERLAYS=opimidi-lcd.dtbo opimidi-buttons.dtbo opimidi-pedals.dtbo opimidi-tinyrtc.dtbo opimidi-nowifi.dtbo

all: $(OVERLAYS)

%.dtbo: %.dts
	$(DTC) -I dts -O dtb -o $@ -@ $<

install:
	install -d /boot/dtb/overlay
	install -m 644 $(OVERLAYS) /boot/dtb/overlay/
	for name in $(OVERLAYS) ; do ln -sf /boot/dtb/overlay/$$name /lib/firmware/$$name ; done

apply-dt:
	[ -d /sys/firmware/devicetree/base/opimidi-lcd-leds ] || ./load_overlay.sh opimidi-lcd.dtbo
	[ -d /sys/firmware/devicetree/base/opimidi-keys ] || ./load_overlay.sh opimidi-buttons.dtbo
	./load_overlay.sh opimidi-pedals.dtbo
	[ -d /sys/firmware/devicetree/base/opimidi-w1 ] || ./load_overaly.sh opimidi-tinyrtc.dtbo
	./load_overlay.sh opimidi-nowifi.dtbo

.PHONY: all install apply-dt
