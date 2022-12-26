#!/usr/bin/env python
import sys

import dbus
import gatt
import struct
from typing import List
from threading import Thread, Barrier

LIGHT_CHARACTERISTIC = "932c32bd-0002-47a2-835a-a8d455b859dd"
BRIGHTNESS_CHARACTERISTIC = "932c32bd-0003-47a2-835a-a8d455b859dd"
TEMPERATURE_CHARACTERISTIC = "932c32bd-0004-47a2-835a-a8d455b859dd"
COLOR_CHARACTERISTIC = "932c32bd-0005-47a2-835a-a8d455b859dd"


def convert_rgb(rgb):
    scale = 0xFF
    adjusted = [max(1, chan) for chan in rgb]
    total = sum(adjusted)
    adjusted = [int(round(chan / total * scale)) for chan in adjusted]

    # Unknown, Red, Blue, Green
    return bytearray([0x1, adjusted[0], adjusted[2], adjusted[1]])

class HueLight(gatt.Device):
    def __init__(
        self, action: str, extra_args: List[str], mac_address: str, manager: gatt.DeviceManager,
        barrier: Barrier
    ) -> None:
        self.action = action
        self.extra_args = extra_args
        self.barrier = barrier

        print(f"connect to {mac_address}...")
        super(HueLight, self).__init__(mac_address=mac_address, manager=manager)

    def introspect(self) -> None:
        for s in self.services:
            print(f"service: {s.uuid}")
            for c in s.characteristics:
                val = c.read_value()
                if val is not None:
                    ary = bytearray()
                    for i in range(len(val)):
                        ary.append(int(val[i]))
                    try:
                        val = ary.decode("utf-8")
                    except UnicodeDecodeError:
                        val = ary
                print(f"  characteristic: {c.uuid}: {val}")

    def set_temperature(self, val: int) -> None:
        val = max(153, min(val, 454))
        self.temperature.write_value(struct.pack("h", val))
        print(self.temperature.read_value())

    def set_color(self, val) -> None:
        print(val[0]+"val")
        color = convert_rgb([int(val[0]), int(val[1]), int(val[2])])
        #print(color+"color")
        self.color.write_value(color)
        print(self.color.read_value())

    def set_brightness(self, val: int) -> None:
        self.brightness.write_value(struct.pack("B", val))
        print(self.brightness.read_value())

    def toggle_light(self) -> None:
        val = self.light_state.read_value()
        if val is None:
            msg = (
                "Could not read characteristic. If that is your first pairing"
                "you may need to perform a firmware reset using the mobile phillips hue app and try connect again"
            )
            print(msg, file=sys.stderr)
            sys.exit(1)
        on = val[0] == 1
        self.light_state.write_value(b"\x00" if on else b"\x01")

    def light_on(self) -> None:
        val = self.light_state.read_value()
        if val is None:
            msg = (
                "Could not read characteristic. If that is your first pairing"
                "you may need to perform a firmware reset using the mobile phillips hue app and try connect again"
            )
            print(msg, file=sys.stderr)
            sys.exit(1)
        on = val[0] == 1
        self.light_state.write_value(b"\x01")

    def light_off(self) -> None:
        val = self.light_state.read_value()
        if val is None:
            msg = (
                "Could not read characteristic. If that is your first pairing"
                "you may need to perform a firmware reset using the mobile phillips hue app and try connect again"
            )
            print(msg, file=sys.stderr)
            sys.exit(1)
        on = val[0] == 1
        self.light_state.write_value(b"\x00")

    def services_resolved(self) -> None:
        super().services_resolved()
        for s in self.services:
            for char in s.characteristics:
                if char.uuid == LIGHT_CHARACTERISTIC:
                    print("found light characteristics")
                    self.light_state = char
                elif char.uuid == BRIGHTNESS_CHARACTERISTIC:
                    print("found brightness characteristics")
                    self.brightness = char
                elif char.uuid == TEMPERATURE_CHARACTERISTIC:
                    print("found temperature characteristics")
                    self.temperature = char
                elif char.uuid == COLOR_CHARACTERISTIC:
                    print("found color characteristics")
                    self.color = char
        if self.action == "toggle":
            self.toggle_light()
        elif self.action == "switch_on":
            self.light_on()
        elif self.action == "switch_off":
            self.light_off()
        elif self.action == "introspect":
            self.introspect()
        elif self.action == "temperature":
            self.set_temperature(int(self.extra_args[0]))
        elif self.action == "brightness":
            self.set_brightness(int(self.extra_args[0]))
        elif self.action == "color":
            self.set_color(self.extra_args)
        else:
            print(f"unknown action {self.action}")
            sys.exit(1)
        self.barrier.wait()


def main():
    if len(sys.argv) < 3:
        print(f"USAGE: {sys.argv[0]} toggle|switch_on|switch_off|color|brightness|temperature|introspect macaddress args...", file=sys.stderr)
        sys.exit(1)

    mac_address = sys.argv[2]
    # FIXME adapter_name should be configurable
    manager = gatt.DeviceManager(adapter_name="hci0")
    # this is a bit of a hack. gatt blocks indefinitely
    b = Barrier(2)
    device = HueLight(sys.argv[1], sys.argv[3:], mac_address=mac_address, manager=manager, barrier=b)
    def run():
        device.connect()
        manager.run()
    t = Thread(target=run, daemon=True)
    t.start()
    b.wait()

if __name__ == "__main__":
    main()
