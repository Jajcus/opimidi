
DTC=dtc

all: opimidi.dtbo

%.dtbo: %.dts
	$(DTC) -I dts -O dtb -o $@ -@ $<
