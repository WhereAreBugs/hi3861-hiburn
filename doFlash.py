import sys
import time
from os.path import basename
from time import sleep
import serial
from tqdm.auto import tqdm
import struct

# Magic number
DEADBEEF = struct.pack('<I', 0xdeadbeef)
# Commands
CMD_DL_IMAGE = 0xD2
CMD_FACTORY_IMAGE = 0x78
CMD_FLASH_PROTECT = 0x96
CMD_RUN_RAM = 0xF0
CMD_RESET = 0x87

# ROM mode
CMD_ACK_SUCCESS_ROM = b'\xe1\x1e\x5a\x42'
CMD_ACK_SUCCESS = b'\xe1\x1e\x5a\xa5'
# Y mode
Y_SOH = b'\x01'
Y_STX = b'\x02'
Y_EOT = b'\x04'
Y_ACK = b'\x06'


def make_cmd(payload):
    cmd = bytearray()
    cmd += DEADBEEF
    cmd += struct.pack('<H', 4 + 2 + len(payload) + 2)
    cmd += payload
    cmd += struct.pack('<H', crc16(cmd))
    return cmd


def cmd_download_flash(address, write_size, erase_size):
    return make_cmd(struct.pack(
        '<HIIIH', palindrome(CMD_DL_IMAGE),
        address, write_size, erase_size, 0x00))


def loady(ser, name, data):
    def _soh(seq, name='', size=''):
        payload = f'{name}\x00{size}\x00'.encode().ljust(128, b'\x00')
        pkt = bytearray(Y_SOH)
        pkt += struct.pack('<H', palindrome(seq))
        pkt += payload
        pkt += struct.pack('>H', crc16(payload))
        return pkt

    def _stx(seq, data):
        payload = data.ljust(1024, b'\x00')
        pkt = bytearray(Y_STX)
        pkt += struct.pack('<H', palindrome(seq))
        pkt += payload
        pkt += struct.pack('>H', crc16(payload))
        return pkt

    def _read(expected):
        while True:
            n = ser.read(1024)
            if len(n) == 0:
                continue
            elif len(n) > len(expected):
                print("[ERROR] 返回值过长: " + str(len(expected)), "预期值:", expected, "实际值:", len(n))
                print("RAW: ", n)
                print(n.decode('ascii', errors='replace').strip())
                return False
            return n == expected

    ser.write(_soh(0, name, str(len(data))))
    start_time = time.time()
    # 需要等待系统就绪，尤其是在下载的数据量比较大的情况下
    while True:
        if not _read(Y_ACK):
            if time.time() - start_time > 10:
                print("[ERROR] 等待系统就绪超时")
                return False
        else:
            break
    time_in_send = 0
    time_in_wait = 0
    for i in tqdm(range(0, len(data), 1024), smoothing=0.1, desc=f"正在发送{name}数据包", unit="kb", leave=False,
                  dynamic_ncols=True, file=sys.stdout):
        while True:
            idx = i // 1024 + 1
            block = data[i:i + 1024]
            start_time = time.time_ns()
            ser.write(_stx(idx, block))
            time_in_send += time.time_ns() - start_time
            start_time = time.time_ns()
            if not _read(Y_ACK):
                sys.stdout = sys.__stderr__
                print(f"\r[WARNING] 在第{idx}kb处发生了丢包，正在尝试自动重传....", end='\n', flush=True)
                sys.stdout = sys.__stdout__
                continue
            time_in_wait += time.time_ns() - start_time
            break

    ser.write(Y_EOT)
    start_time = time.time()
    while True:
        if time.time() - start_time > 3:
            print("[ERROR] Y_EOT超时")
            return False
        if not _read(Y_ACK + Y_ACK + b'C'):
            print("[ERROR] Y_EOT最终确认失败")
            continue
        else:
            break

    ser.write(_soh(0))

    if not _read(Y_ACK):
        time.sleep(0.5)
        print("[ERROR] _soh阶段等待Y_ACK失败!")
        _print_device_logs(ser.read(1024))
        return False
    print(f"[INFO] 烧录完成，数据发送耗时:{time_in_send / 1000000} ms, 等待Y_ACK耗时:{time_in_wait / 1000000} ms")
    return True


# /Users/cat/Downloads/Hi3861_wifiiot_app_burn.bin
# 0x6000

# /Users/cat/Downloads/Hi3861_loader_signed.bin

def crc16(data):
    crc = 0
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = (crc << 1) ^ 0x1021 if crc & 0x8000 else crc << 1
    return crc & 0xFFFF


def cmd_run_ram(baud_rate):
    return make_cmd(struct.pack(
        '<HII', palindrome(CMD_RUN_RAM),
        int(baud_rate), 0x0108))


def palindrome(n):
    return ((~n & 0xff) << 8) | (n & 0xff)


def align_up(x: int, align: int) -> int:
    return (x + align - 1) & ~(align - 1)


def _print_device_logs(data):
    print(data.decode('ascii', errors='replace').strip())


class hiburn_hi3861():
    def __init__(self, ser, baudrate, allInOneBin, loaderboot_bin, partition_tables):
        self.ser = ser
        self.baudrate = str(baudrate)  # default 115200
        self.loaderboot_bin = loaderboot_bin
        self.app_burn_bin = allInOneBin
        for i in range(2):
            if partition_tables[i]['type'] == 0:
                self.loaderboot_name = partition_tables[i]['filename']
            elif partition_tables[i]['type'] == 1:
                self.app_burn_name = partition_tables[i]['filename']

    def flash(self):
        loaderboot = self.loaderboot_bin
        app_burn_bin = self.app_burn_bin

        partitions = [
            [0x0000, len(app_burn_bin), basename(self.app_burn_name), app_burn_bin],
        ]

        ser = serial.Serial(self.ser, 115200, timeout=0.05)

        print('[INFO] 等待设备重置......')

        connected = False
        while not connected:
            ser.write(cmd_run_ram(self.baudrate))

            # Check if connected
            for r in self._read_cmd(ser, wait=False):
                if r == CMD_ACK_SUCCESS_ROM:
                    connected = True
                    break
                else:
                    print('[ERROR] 连接失败，建立通讯出现问题')
                    print('[ERROR] 原始返回数据: ', r)
                    return

        print('[INFO] 设备连接成功')

        if ser.baudrate != self.baudrate:
            print(f'[INFO] 当前选择的波特率不为115200，正在协商波特率{self.baudrate}')
            ser.close()
            ser.baudrate = self.baudrate
            ser.open()

        sleep(0.1)

        ser.write(b'\03')

        sleep(0.1)

        ser.write(b'\00')

        # Read logs
        for _ in self._read_cmd(ser):
            continue
        print("[INFO] 烧录过程开始...")
        print(f'开始载入 {basename(self.loaderboot_name)}...', flush=True)

        if not loady(ser, basename(self.loaderboot_name), loaderboot):
            print('[ERROR] Failed to load loaderboot')
            return

        # Read logs and check
        for r in self._read_cmd(ser):
            if r != CMD_ACK_SUCCESS:
                print('[ERROR] Failed to load loaderboot')
                return

        sleep(0.1)

        for [addr, size, name, data] in partitions:
            print(f'开始下载 {name}...')

            ser.write(cmd_download_flash(
                addr, size, align_up(size, 4096)))

            sleep(3.1)

            for r in self._read_cmd(ser):
                if r != CMD_ACK_SUCCESS:
                    print(f'[ERROR] Failed to start download of {name}')
                    return

            if not loady(ser, name, data):
                print(f'[ERROR] Failed to download {name}')
                return

            # Read logs and check
            for r in self._read_cmd(ser):
                if r != CMD_ACK_SUCCESS:
                    print(f'[ERROR] Failed to finish download of {name}')
                    return

        print('Done')
        print("[INFO] 正在尝试自动重置....")
        ser.write(make_cmd(struct.pack('<H', CMD_RESET)))
        sleep(0.1)
        print('[INFO] 已完成')

    def _read_cmd(self, ser, wait=True):
        result = []
        data = bytearray()

        while True:
            read = ser.read(1024)
            data += read
            if len(read) == 0:
                if len(data) > 0:
                    break
                elif not wait:
                    return result

        while len(data) > 0:
            offset = data.find(DEADBEEF)
            if offset == -1:
                _print_device_logs(data)
                break

            if offset > 0:
                _print_device_logs(data[:offset])
                data = data[offset:]

            while len(data) < 6:
                data += ser.read(1024)

            length = struct.unpack('<H', data[4:6])[0]

            while len(data) < length:
                data += ser.read(1024)

            packet = data[:length]
            data = data[length:]

            if crc16(packet[:-2]) == struct.unpack('<H', packet[-2:])[0]:
                result.append(packet[6:-2])

        return result
