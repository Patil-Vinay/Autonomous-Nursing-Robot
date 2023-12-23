#!/usr/bin/env python3
"""MLX90640 thermal camera on the Jetson I2C bus, 32 x 24 temperatures in deg C.

The calibration and temperature maths follow the Melexis MLX90640 driver
(MLX90640_API.cpp) and the datasheet, with the pixels done as numpy arrays.
"""
import struct

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from smbus2 import SMBus, i2c_msg

ADDRESS = 0x33
STATUS, CONTROL, RAM, EEPROM = 0x8000, 0x800D, 0x0400, 0x2400
# subpages per second and their code in the control register
RATES = {0.5: 0, 1: 1, 2: 2, 4: 3, 8: 4, 16: 5, 32: 6, 64: 7}
WIDTH, HEIGHT = 32, 24


def signed(value, bits):
    return np.where(value >= 1 << (bits - 1), value - (1 << bits), value)


def nibbles(words):
    """The four signed 4-bit values in each word, lowest first."""
    words = np.array(words)
    return signed(np.stack([(words >> s) & 0xF for s in (0, 4, 8, 12)], axis=1).ravel(), 4)


class Calibration:
    """Constants from the 832 word EEPROM, as in MLX90640_ExtractParameters."""

    def __init__(self, ee):
        ee = [int(w) for w in ee]
        # supply voltage and sensor temperature
        self.k_vdd = signed(ee[51] >> 8, 8) * 32
        self.vdd25 = ((ee[51] & 0xFF) - 256) * 32 - 8192
        self.kv_ptat = signed(ee[50] >> 10, 6) / 4096.0
        self.kt_ptat = signed(ee[50] & 0x3FF, 10) / 8.0
        self.v_ptat25 = signed(ee[49], 16)
        self.alpha_ptat = (ee[16] >> 12) / 4.0 + 8.0
        self.gain = signed(ee[48], 16)
        self.tgc = signed(ee[60] & 0xFF, 8) / 32.0
        self.resolution = (ee[56] >> 12) & 0x3
        self.ks_ta = signed(ee[60] >> 8, 8) / 8192.0

        # four temperature ranges, each with its own KsTo
        step = ((ee[63] >> 12) & 0x3) * 10
        ct3 = ((ee[63] >> 4) & 0xF) * step
        ct4 = ct3 + ((ee[63] >> 8) & 0xF) * step
        self.ct = np.array([-40.0, 0.0, ct3, ct4])
        scale = float(1 << ((ee[63] & 0xF) + 8))
        self.ks_to = np.array([signed(ee[61] & 0xFF, 8), signed(ee[61] >> 8, 8),
                               signed(ee[62] & 0xFF, 8), signed(ee[62] >> 8, 8)]) / scale
        corr2 = 1 + self.ks_to[1] * ct3
        self.alpha_corr = np.array([1 / (1 + self.ks_to[0] * 40), 1.0, corr2,
                                    corr2 * (1 + self.ks_to[2] * (ct4 - ct3))])

        # compensation pixels
        kta_scale1 = ((ee[56] >> 4) & 0xF) + 8
        kta_scale2 = ee[56] & 0xF
        kv_scale = (ee[56] >> 8) & 0xF
        cp_offset = signed(ee[58] & 0x3FF, 10)
        self.cp_offset = [cp_offset, cp_offset + signed(ee[58] >> 10, 6)]
        cp_alpha = signed(ee[57] & 0x3FF, 10) / 2.0 ** ((ee[32] >> 12) + 27)
        cp_alpha = [cp_alpha, (1 + signed(ee[57] >> 10, 6) / 128.0) * cp_alpha]
        self.cp_kta = signed(ee[59] & 0xFF, 8) / 2.0 ** kta_scale1
        self.cp_kv = signed(ee[59] >> 8, 8) / 2.0 ** kv_scale

        pixels = np.array(ee[64:832])
        row = np.arange(768) // WIDTH
        col = np.arange(768) % WIDTH
        # 0 to 3 for odd and even rows and columns
        split = 2 * (row % 2) + col % 2

        # sensitivity
        a = signed((pixels >> 4) & 0x3F, 6) * 2.0 ** (ee[32] & 0xF)
        a += ee[33] + nibbles(ee[34:40])[row] * 2.0 ** ((ee[32] >> 8) & 0xF)
        a += nibbles(ee[40:48])[col] * 2.0 ** ((ee[32] >> 4) & 0xF)
        self.alpha = a / 2.0 ** ((ee[32] >> 12) + 30) - self.tgc * (cp_alpha[0] + cp_alpha[1]) / 2

        # offset
        o = signed((pixels >> 10) & 0x3F, 6) * 2.0 ** (ee[16] & 0xF)
        o += signed(ee[17], 16) + nibbles(ee[18:24])[row] * 2.0 ** ((ee[16] >> 8) & 0xF)
        o += nibbles(ee[24:32])[col] * 2.0 ** ((ee[16] >> 4) & 0xF)
        self.offset = o

        # offset drift with sensor temperature and supply voltage
        kta_rc = np.array([signed(ee[54] >> 8, 8), signed(ee[55] >> 8, 8),
                           signed(ee[54] & 0xFF, 8), signed(ee[55] & 0xFF, 8)])
        kta = kta_rc[split] + signed((pixels >> 1) & 0x7, 3) * 2.0 ** kta_scale2
        self.kta = kta / 2.0 ** kta_scale1
        kv_rc = np.array([signed(ee[52] >> 12, 4), signed((ee[52] >> 4) & 0xF, 4),
                          signed((ee[52] >> 8) & 0xF, 4), signed(ee[52] & 0xF, 4)])
        self.kv = kv_rc[split] / 2.0 ** kv_scale

        # corrections when reading in the other pattern than the one calibrated
        self.chess_calibrated = not ee[10] & 0x0800
        self.il_chess = [signed(ee[53] & 0x3F, 6) / 16.0, signed((ee[53] >> 6) & 0x1F, 5) / 2.0,
                         signed(ee[53] >> 11, 5) / 8.0]
        p = np.arange(768)
        self.il_pattern = row % 2
        self.chess_pattern = self.il_pattern ^ (col % 2)
        self.conversion = (((p + 2) // 4 - (p + 3) // 4 + (p + 1) // 4 - p // 4)
                           * (1 - 2 * self.il_pattern))

        # broken or outlier pixels
        self.bad = (pixels == 0) | (pixels & 1 == 1)

    def temperatures(self, frame, control, subpage, emissivity, ta_shift):
        """deg C for the pixels of one subpage, as in MLX90640_CalculateTo."""
        f = signed(np.array(frame), 16).astype(np.float64)
        resolution = 2.0 ** self.resolution / 2.0 ** ((control >> 10) & 0x3)
        vdd = (resolution * f[810] - self.vdd25) / self.k_vdd + 3.3
        ptat = f[800]
        ptat_art = ptat / (ptat * self.alpha_ptat + f[768]) * 2 ** 18
        ta = (ptat_art / (1 + self.kv_ptat * (vdd - 3.3)) - self.v_ptat25) / self.kt_ptat + 25
        tr = ta - ta_shift
        ta4, tr4 = (ta + 273.15) ** 4, (tr + 273.15) ** 4
        ta_tr = tr4 - (tr4 - ta4) / emissivity

        gain = self.gain / f[778]
        chess = bool(control & 0x1000)
        drift = (1 + self.cp_kta * (ta - 25)) * (1 + self.cp_kv * (vdd - 3.3))
        cp = [f[776] * gain - self.cp_offset[0] * drift, f[808] * gain - self.cp_offset[1] * drift]
        if chess != self.chess_calibrated:
            cp[1] -= self.il_chess[0] * drift

        ir = f[:768] * gain
        ir -= self.offset * (1 + self.kta * (ta - 25)) * (1 + self.kv * (vdd - 3.3))
        if chess != self.chess_calibrated:
            ir += self.il_chess[2] * (2 * self.il_pattern - 1) - self.il_chess[1] * self.conversion
        ir = (ir - self.tgc * cp[subpage]) / emissivity

        alpha = self.alpha * (1 + self.ks_ta * (ta - 25))
        with np.errstate(invalid='ignore'):
            sx = (alpha ** 3 * (ir + alpha * ta_tr)) ** 0.25 * self.ks_to[1]
            to = (ir / (alpha * (1 - self.ks_to[1] * 273.15) + sx) + ta_tr) ** 0.25 - 273.15
            # again with the KsTo of the range it fell in
            r = np.digitize(to, self.ct[1:])
            to = (ir / (alpha * self.alpha_corr[r] * (1 + self.ks_to[r] * (to - self.ct[r])))
                  + ta_tr) ** 0.25 - 273.15

        pattern = self.chess_pattern if chess else self.il_pattern
        return pattern == subpage, to


class Mlx90640(Node):
    def __init__(self):
        super().__init__('mlx90640')
        param = self.declare_parameter
        rate = param('refresh_rate', 4.0).value
        self.emissivity = param('emissivity', 0.98).value
        # reflected temperature this far below the sensor's own, the Melexis value for open air
        self.ta_shift = param('ta_shift', 8.0).value
        self.flip_x = param('flip_horizontal', False).value
        self.flip_y = param('flip_vertical', False).value
        self.frame_id = param('frame_id', 'thermal_optical_frame').value

        self.bus = SMBus(param('bus', 1).value)
        self.cal = Calibration(self.read(EEPROM, 832))
        control = self.read(CONTROL, 1)[0]
        self.write(CONTROL, (control & ~0x0380) | (RATES[rate] << 7))

        self.pixels = np.full(768, np.nan)
        self.pub = self.create_publisher(Image, 'thermal/image', qos_profile_sensor_data)
        self.create_timer(0.25 / rate, self.poll)

    def read(self, address, count):
        words = []
        while count > 0:
            n = min(count, 128)
            write = i2c_msg.write(ADDRESS, [address >> 8, address & 0xFF])
            read = i2c_msg.read(ADDRESS, 2 * n)
            self.bus.i2c_rdwr(write, read)
            words += struct.unpack('>%dH' % n, bytes(list(read)))
            address += n
            count -= n
        return words

    def write(self, address, value):
        self.bus.i2c_rdwr(i2c_msg.write(ADDRESS, [address >> 8, address & 0xFF,
                                                  value >> 8, value & 0xFF]))

    def poll(self):
        try:
            status = self.read(STATUS, 1)[0]
            if not status & 0x0008:
                return
            self.write(STATUS, 0x0030)
            frame = self.read(RAM, 832)
            control = self.read(CONTROL, 1)[0]
        except OSError as e:
            self.get_logger().warn(f'I2C: {e}', throttle_duration_sec=5.0)
            return

        subpage = status & 0x0001
        mask, to = self.cal.temperatures(frame, control, subpage, self.emissivity, self.ta_shift)
        self.pixels[mask] = to[mask]
        if subpage == 1 and not np.isnan(self.pixels).any():
            self.publish()

    def publish(self):
        image = self.pixels.reshape(HEIGHT, WIDTH).copy()
        bad = self.cal.bad.reshape(HEIGHT, WIDTH)
        for r, c in zip(*np.nonzero(bad)):
            near = [image[rr, cc] for rr, cc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1))
                    if 0 <= rr < HEIGHT and 0 <= cc < WIDTH and not bad[rr, cc]]
            if near:
                image[r, c] = np.mean(near)
        if self.flip_x:
            image = image[:, ::-1]
        if self.flip_y:
            image = image[::-1, :]

        msg = Image()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.frame_id
        msg.height, msg.width = HEIGHT, WIDTH
        msg.encoding = '32FC1'
        msg.step = WIDTH * 4
        msg.data = np.ascontiguousarray(image, dtype=np.float32).tobytes()
        self.pub.publish(msg)


def main():
    rclpy.init()
    node = Mlx90640()
    rclpy.spin(node)


if __name__ == '__main__':
    main()
