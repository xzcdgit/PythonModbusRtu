import crcmod
import serial
import time
import struct

class ModbusRtu(object):
    def __init__(self) -> None:
        self.__com = None
        self.__valueformat = "int"
        self.__intsigned = False
        self.__param_connect_str_en = ""
        self.__param_connect_str_cn = ""

    def __crc16(self,veritydata):
        '''
        @function: crc校验码计算器
        @param: veritydata(class bytes) 待计算数据
        @return: 将计算好的crc校验码返回
        '''
        if not veritydata:
            return
        #return一个function然后调用这个新生成的function
        crc16 = crcmod.mkCrcFun(0x18005, rev=True, initCrc=0xFFFF, xorOut=0x0000)
        return crc16(veritydata)

    def __checkcrc(self,data):
        '''
        @function: 校验数据的crc校验码正确与否
        @param: data(class bytes) 待校验数据
        @return: (class bool) 返回校验结果
        '''
        if not data:
            return False
        if len(data) <= 2:
            return False
        #分离数据中的crc和值
        nocrcdata = data[:-2]
        oldcrc16 = data[-2:]
        oldcrclist = list(oldcrc16)
        crcres = self.__crc16(nocrcdata)
        crc16byts = crcres.to_bytes(2, byteorder="little", signed=False)
        # print("CRC16:", crc16byts.hex())
        crclist = list(crc16byts)
        if oldcrclist[0] != crclist[0] or oldcrclist[1] != crclist[1]:
            return False
        return True

    def __mmodbus(self,add, funcode, startregadd, regnum):
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
        crcres = self.__crc16(sendbytes)
        crc16bytes = crcres.to_bytes(2, byteorder="little", signed=False)
        sendbytes = sendbytes + crc16bytes
        print(sendbytes)
        return sendbytes

    def __smodbus(self,recvdata, valueformat=0, intsigned=False):
        '''
        @function: 解析modbus-rtu返回数据的数值
        @param: recvdata(class bytes) 待解析的数据
        @param: valueformat 数据的转化类型(float short 或者 int)
        @param: intsigned 数据为整型时是否有符号
        @return: 返回解析后的数值list
        '''
        if not recvdata:
            print("Error: data error")
            return
        if not self.__checkcrc(recvdata):
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
        elif valueformat in (1,"short"):
            shortintnums = bytenums / 2
            print("short int nums: ", str(shortintnums))
            for i in range(int(shortintnums)):
                btemp = recvdata[3+i*2:5+i*2]
                shortvalue = int.from_bytes(btemp, byteorder="big", signed=intsigned)
                retdata.append(shortvalue)
                print(f"Data{i+1}: {shortvalue}")
        #双字数据
        elif valueformat in (2,"int"):
            intnums = bytenums / 4
            print("int nums: ", str(intnums))
            for i in range(int(intnums)):
                btemp = recvdata[3+i*4:7+i*4]
                intvalue = int.from_bytes(btemp, byteorder="big", signed=intsigned)
                retdata.append(intvalue)
                print(f"Data{i+1}: {intvalue}")
        return retdata

    def connect(self,port, bps, bytesize, parity, stopbits, timeout):
        '''
        @function: 打开串口，在关闭串口前回保持占用
        @param: port(str) 串口名
        @param: bps(int) 波特率
        @param: bytesize(int) 数据位
        @param: stopbits(int) 停止位
        @param: timeout(float) 连接超时时间，单位 秒(s)
        '''
        try:
            self.__com = serial.Serial(port, bps, bytesize, parity, stopbits, timeout)
            self.__param_connect_str_en = "port: %s\nbaudrate: %s\nbytesize: %s\nparity: %s\nstopbits: %s\ntimeout(s): %s\n"
            self.__param_connect_str_cn = "端口号: %s\n波特率: %s\n数据位: %s\n校验位: %s\n停止位: %s\n超时时间(s): %s\n"
        except Exception as e:
            self.__com = None
            raise ValueError("连接参数错误:\n"+str(e))

    def communicate(self,order:str,rec_byte_num:int = 0):
        '''
        @function: 通用通信
        @param: order(str) 完整的通讯指令,会自动移除字符串中所有的空格,字符串有效长度必须为偶数
        @param: rec_byte_num(int) 需要读取的回传数据的数量(单位：字节)，默认数量为0即不读取回传数据
        @return: recv_data(bytearray) 回传收到的数据，如果rec_byte_num该参数为0则不会回传任何数据
        example:
        order = "01 03 10 00 00 0A C1 0D"
        rec_byte_num = 25
        recv_data = b'01031400010a0400000000000000000000000000000000ff80'
        上述例子中调用该函数，传入的指令为读取设备1的保持寄存器，从0x1000地址开始，读取10个寄存器的值，返回值为25个字节的bytearray
        '''
        if self.__com == None:
            raise TypeError("端口未连接或者连接错误")
        order.replace(" ","")
        if len(order)%2 != 0:
            raise ValueError("指令的长度必须为偶数")
        order_byte_list = []
        for i in range(int(len(order)/2)):
            value_int = int(order[2*i:2*i+2],16)
            order_byte_list.append(value_int)
        order_bytes = bytes(order_byte_list)
        self.__com.write(order_bytes)
        if rec_byte_num != 0:
            recv_data = self.__com.read(rec_byte_num)
            return recv_data
        
    def read(self,slaveadd, funcode, startreg, regnum):
        '''
        @function: 读取串口数据 一般是 01 02 03 04 05 06功能码对应的功能
        @param: slaveadd(int) 地址码
        @param: funcode(int) 功能码
        @param: startreg(int) 寄存器起始地址
        @param: regnum(int) 寄存器读取数量
        @return: (list) 根据设定的数据转换类型将查询到的数据转换后合并成list并回传
        '''
        if self.__com == None:
            raise TypeError("端口未连接或者连接错误")
        send_data = self.__mmodbus(slaveadd, funcode, startreg, regnum)
        self.__com.write(send_data)
        recv_data = self.__com.read(regnum*2+5)
        if len(recv_data) > 0:
            if funcode in (3,4):
                value = self.__smodbus(recv_data, self.__valueformat, self.__intsigned)
            else:
                value = self.__smodbus(recv_data, "int", False)
        else:
            value = None
        return value
    
    def read_data_type_set(self, valueformat = "int", intsigned = False):
        '''
        @function: 返回数据的类型设置
        @param: valueformat 返回数据的转换类型
        @param: intsigned 返回数据的符号有无
        '''
        if valueformat not in ("short","int","float",0,1,2):
            raise ValueError("数值类型参数错误")
        if intsigned not in (False,True):
            raise TypeError("符号类型设置错误，参数只能为布尔值")
        self.__valueformat = valueformat
        self.__intsigned = intsigned
    
    def param_connect_print(self):
        '''
        @function: 返回串口的连接参数
        '''
        return self.__param_connect_str_cn

    def write(self):
        '''
        @function: 未实现功能
        '''
        pass

    def disconnect(self):
        '''
        @function: 关闭串口
        '''
        if self.__com != None:
            self.__com.close()

    def __del__(self):
        '''
        @function: 类实例失效时关闭串口
        '''
        self.disconnect()
        print("类已清除")
    

if __name__ == '__main__':
    port = "com3"
    bps = 9600
    bytesize = 8
    parity = 'E'
    stopbits = 1
    timeout = 0.5
    slaveadd = 1
    funcode = 3
    startreg = 4096
    regnum = 2
    mycom = ModbusRtu()
    mycom.connect(port, bps, bytesize, parity, stopbits, timeout) 
    value_list = mycom.read(slaveadd, funcode, startreg, regnum)
    order = "01031000000AC10D"
    value_list = mycom.communicate(order,25)
    print(value_list.hex())

