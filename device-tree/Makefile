
DTC=dtc

all: opimidi.dtbo opimidi-tinyrtc.dtbo

%.dtbo: %.dts
	$(DTC) -I dts -O dtb -o $@ -@ $<
