#!/usr/bin/python3
import argparse
import serial.tools.list_ports
import imageProcessor
from doFlash import *
from imageProcessor import *

# 解析命令行参数

if __name__ == "__main__":
    # 列出系统中的串口列表
    serial_ports = []
    serial_ports_raw = serial.tools.list_ports.comports(True)
    for i in serial_ports_raw:
        serial_ports.append(i.device)

    parser = argparse.ArgumentParser(description='Flash a binary file to hi3861 (针对hi3861芯片的hiburn跨平台烧录脚本)')
    parser.usage = ("python3 main.py ./OHOS_image.bin [-b 3000000] [-s /dev/tty.usbserial-10]\n"
                    "\t   python3 main.py 文件路径 [-b 波特率] [-s 串口设备路径(/dev/xxx)或串口号(COMx)]")
    parser.add_argument('allInOneBin', help='All in one binary file (烧录文件)', default=None)
    flash_group = parser.add_argument_group('flash', 'flash options(烧录选项)')
    flash_group.add_argument('-s', '--serial', help='Serial port(串口路径(/dev/xxx)或串口号(COMx))', required=False,
                             default=None)
    flash_group.add_argument('-b', '--baudrate', help='Baudrate(下载时运行的波特率)', required=False, default="115200")
    args = parser.parse_args()
    if imageProcessor.judgefile(args.allInOneBin) == 'all_in_one':
        print("[INFO] 您输入的二进制文件为: ", args.allInOneBin)
        partition_table = imageProcessor.get_partition_table(args.allInOneBin)
        files = read_file(args.allInOneBin, partition_table)
        for i in range(2):
            if partition_table[i]['type'] == 0:
                args.loaderboot = files[i]
            elif partition_table[i]['type'] == 1:
                args.app_burn_file = files[i]
        if args.serial is None:
            print("[INFO] 没有指定串口，请选择串口:")
            if len(serial_ports) == 1:
                args.serial = serial_ports[0]
                print(f"[INFO] 自动选择串口 {args.serial}")
            else:
                for i in range(1, len(serial_ports) + 1):
                    print(i, serial_ports[i - 1])
                args.serial = serial_ports[int(input("请输入序号: ")) - 1]
                print("[INFO] 选择的串口为: ", args.serial)
    else:
        print("[ERROR] 您输入的二进制文件不是all_in_one格式或不受支持，请检查文件是否正确！")
        exit(1)
    bf = hiburn_hi3861(args.serial, args.baudrate, args.app_burn_file, args.loaderboot, partition_table)
    try:
        bf.flash()
    except FileNotFoundError as e:
        print(e)
        print("文件不存在，请检查文件路径是否正确！")
