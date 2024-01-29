import os
import sys
import struct

fileType = {
    0: 'loaderboot_or_app_burn',
    1: 'app_ota',
    2: 'all_in_one'
}


def judgefile(filename):
    if os.path.exists(filename):
        # 数据存在，继续操作
        with open(filename, 'rb') as f:
            data = f.read(4)
            if data == b'\xdf\xad\xbe\xef':
                print("[INFO] 当前选择的是All in one 类型的文件，正在尝试解析...")
                return fileType[2]
            elif data == b'\xaa\x55\xaa\x55':
                print("[INFO] 当前选择的是loaderboot或app_burn类型的文件")
                return fileType[0]
            elif data == b'\x1e\x96\x78\x3c':
                print("[INFO] 当前选择的是app_ota类型的文件")
                return fileType[1]
    else:
        print("[ERROR] 文件不存在，请检查文件路径")
        sys.exit(1)


def get_partition_table(filename):
    # 此时应该是检查过了文件是否存在
    with open(filename, 'rb') as f:
        _ = f.read(12)  # 跳过头
        partions = []
        for _ in range(2):
            data = f.read(52)
            res = struct.unpack('32b5I', data)
            filename = ""
            partion = dict()
            fields = ["filename", "offset", "size", "burn_addr", "burn_size", "type"]
            for i in range(0, 32):
                if chr(res[i]) == '\x00':
                    break
                filename += chr(res[i])
            partion.update({fields[0]: filename})
            for i in range(32, 37):
                partion.update({fields[i - 31]: res[i]})
            partions.append(partion)
        return partions


def read_file(filename, partions):
    datas = []
    for partion in partions:
        f = open(filename, 'rb')
        f.seek(partion['offset'])
        data = f.read(partion['size'])
        datas.append(data)
    return datas
