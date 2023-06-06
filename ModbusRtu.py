import crcmod
import serial
import time
import struct
#######################################################
#基础函数

def crc16(veritydata):
    '''
    @function: crc校验码计算器
    @param: veritydata 待计算数据
    @return: 将计算好的crc校验码返回
    '''
    if not veritydata:
        return
    #return一个function然后调用这个新生成的function
    crc16 = crcmod.mkCrcFun(0x18005, rev=True, initCrc=0xFFFF, xorOut=0x0000)
    return crc16(veritydata)

def checkcrc(data):
    '''
    @function: 校验数据的crc校验码正确与否
    @data: 待校验数据
    @return: 返回校验结果 bool值
    '''
    if not data:
        return False
    if len(data) <= 2:
        return False
    #分离数据中的crc和值
    nocrcdata = data[:-2]
    oldcrc16 = data[-2:]
    oldcrclist = list(oldcrc16)
    crcres = crc16(nocrcdata)
    crc16byts = crcres.to_bytes(2, byteorder="little", signed=False)
    # print("CRC16:", crc16byts.hex())
    crclist = list(crc16byts)
    if oldcrclist[0] != crclist[0] or oldcrclist[1] != crclist[1]:
        return False
    return True

#######################################################
#功能函数

def mmodbus(add, funcode, startregadd, regnum):
    '''
    @function: 生成标准的modbus-rtu通讯指令串
    @param: add modbus从站地址
    @param: funcode 功能码
    @param: startregadd 需要读取的寄存器起始地址
    @param: regnum 需要读取的寄存器数量
    @return: sendbytes 生成的发送指令 
    '''
    if add < 0 or add > 0xFF or startregadd < 0 or startregadd > 0xFFFF or regnum < 1 or regnum > 0x7D:
        print("Error: parameter error")
        return
    if funcode not in (1,2,3,4,5,6,15,16):
        print("Error: parameter error")
        return
    sendbytes = add.to_bytes(1, byteorder="big", signed=False)
    sendbytes = sendbytes + funcode.to_bytes(1, byteorder="big", signed=False) + startregadd.to_bytes(2, byteorder="big", signed=False) + \
                regnum.to_bytes(2, byteorder="big", signed=False)
    crcres = crc16(sendbytes)
    crc16bytes = crcres.to_bytes(2, byteorder="little", signed=False)
    sendbytes = sendbytes + crc16bytes
    return sendbytes

def smodbus(recvdata, valueformat=0, intsigned=False):
    '''
    @function: 解析modbus-rtu返回数据的数值
    @param: recvdata 待解析的数据
    @param: valueformat 数据的转化类型(float 或者 int)
    @param: intsigned 数据为整型时是否有符号
    @return: 返回解析后的数值list
    '''
    if not recvdata:
        print("Error: data error")
        return
    if not checkcrc(recvdata):
        print("Error: crc error")
        return
    datalist = list(recvdata)
    #判定返回数据的功能码是否合法s
    if datalist[1] not in (1,2,3,4,5,6,15,16):
        print("Error: recv data funcode error")
        return
    bytenums = datalist[2]
    #判定返回数据的有效数据长度
    if bytenums % 2 != 0:
        print("Error: recv data reg data error")
        return
    retdata = []
    #根据设定的数据类型计算返回数据的实际值
    if valueformat in (0,"float"):
        floatnums = bytenums / 4
        print("float nums: ", str(floatnums))
        floatlist = [0, 0, 0, 0]
        for i in range(int(floatnums)):
            floatlist[1] = datalist[3+i*4]
            floatlist[0] = datalist[4+i*4]
            floatlist[3] = datalist[5+i*4]
            floatlist[2] = datalist[6+i*4]
            bfloatdata = bytes(floatlist)
            [fvalue] = struct.unpack('f', bfloatdata)
            retdata.append(fvalue)
            print(f'Data{i+1}: {fvalue:.3f}')
    elif valueformat in (1,"int"):
        shortintnums = bytenums / 2
        print("short int nums: ", str(shortintnums))
        for i in range(int(shortintnums)):
            btemp = recvdata[3+i*2:5+i*2]
            shortvalue = int.from_bytes(btemp, byteorder="big", signed=intsigned)
            retdata.append(shortvalue)
            print(f"Data{i+1}: {shortvalue}")
    return retdata

if __name__ == '__main__':
    port = "com3"
    bps = 9600
    bytesize = 8
    parity = 'N'
    stopbits = 1
    timeout = 0.5
    slaveadd = 1
    funcode = 3
    startreg = 0
    regnum = 8
    send_data = mmodbus(slaveadd, funcode, startreg, regnum)
    print("send data: ",send_data.hex())
    com = serial.Serial(port, bps, bytesize, parity, stopbits, timeout)
    print("com is opened")
    for i in range(25):
        com.write(send_data)
        recv_data = com.read(regnum*2+5)
        if len(recv_data) > 0:
            print("recv: ", recv_data.hex())
            value = smodbus(recv_data)
            print("value: ", value)
        time.sleep(0.2)
    com.close()
    print("com is closed")

