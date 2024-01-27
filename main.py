import argparse

from doFlash import *

# 解析命令行参数

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Flash a binary file to a microcontroller')
    parser.add_argument('-s', '--serial', help='Serial port', required=False, default=None)
    parser.add_argument('-b', '--baudrate', help='Baudrate', required=False, default="115200")
    parser.add_argument('-l', '--loaderboot', help='Loaderboot binary file', required=False, default=None)
    parser.add_argument('-p', '--app_burn_file', help='All in one file', required=False, default=None)
    args = parser.parse_args()
    if args.app_burn_file is None or args.loaderboot is None or args.serial is None:
        print("启动参数校验失败！")
        print("请输入串口号(Windows)或串口路径(Linux)")
        args.serial = input()
        print("您输入的串口号为: ", args.serial)
        print("请输入下载阶段的波特率(如: 115200)")
        try:
            args.baudrate = int(input())
        except ValueError as e:
            print("输入的波特率格式错误，使用默认值115200！")
            args.baudrate = 115200
        print("您输入的波特率为: ", args.baudrate)
        print("请输入下载阶段的二进制文件路径(如: loaderboot.bin)")
        args.loaderboot = input()
        print("您输入的二进制文件为: ", args.loaderboot)
        print("请输入需要下载的文件路径(如*.app_brun.bin): ")
        args.app_burn_file = input()
        print("您输入的二进制文件为: ", args.app_burn_file)
    bf = hiburn_4_hi3861(args.serial, args.baudrate, args.app_burn_file, args.loaderboot)
    try:
        bf.flash()
    except FileNotFoundError as e:
        print(e)
        print("文件不存在，请检查文件路径是否正确！")
        exit(2)
