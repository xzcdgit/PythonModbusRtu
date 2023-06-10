import crcmod
import serial
import struct

class ModbusRtu(object):
    '''
    modbus-rtu通信类
    使用时需要先调用`connect()`打开串口，然后调用communicate或者read等进行串口通讯
    '''
    def __init__(self) -> None:
        '''
        类实例变量初始化

        参数说明:
            self.__com 端口对象属于serial.Serial库中定义的对象
            self.__valueformat 标准格式的modbus-rtu数据(如读取输入寄存器、保持寄存器等的值)读取后转换标准，默认转为int类型
            self.__intsigned 标准格式的modbus-rtu数据(如读取输入寄存器、保持寄存器等的值)读取后转换标准，如果为int或者short类型，设定是否为有符号数
            self.__param_connect_str_en self.__param_connect_str_cn 连接成功后记录的连接参数，可以用函数直接print出来
        '''
        self.__com = None
        self.__valueformat = "int"
        self.__intsigned = False
        self.__param_connect_str_en = ""
        self.__param_connect_str_cn = ""

    def __crc16(self,veritydata):
        '''
        crc校验码计算器
        :param veritydata(bytearray): 待计算数据
        :return (bytearray): 将计算好的crc校验码返回
        '''
        if not veritydata:
            return
        #return一个function然后调用这个新生成的function
        crc16 = crcmod.mkCrcFun(0x18005, rev=True, initCrc=0xFFFF, xorOut=0x0000)
        return crc16(veritydata)

    def __checkcrc(self,data):
        '''
        校验数据的crc校验码正确与否

        :param data(bytearray): 待校验数据
        :return (bool): 返回校验结果
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
        生成标准的modbus-rtu通讯指令串

        :param: add(int): modbus从站地址
        :param funcode(int): 功能码
        :param startregadd(int): 需要读取的寄存器起始地址
        :param regnum(int): 需要读取的寄存器数量
        :return (bytearray): 生成的发送指令 
        '''
        if add < 0 or add > 0xFF:
            raise ValueError("地址码超出范围 add∈[0-255]")
        if startregadd < 0 or startregadd > 0xFFFF:
            raise ValueError("寄存器起始地址超出范围 startregadd∈[0,65535]")
        if regnum < 1 or regnum > 0x7D:
            raise ValueError("寄存器读取数量范围 regnum∈[1,125]")
        if funcode not in (1,2,3,4,5,6,15,16):
            raise ValueError("功能码不在范围内 funcode∈{1,2,3,4,5,6,15,16}")
        sendbytes = add.to_bytes(1, byteorder="big", signed=False)
        sendbytes = sendbytes + funcode.to_bytes(1, byteorder="big", signed=False) + startregadd.to_bytes(2, byteorder="big", signed=False) + \
                    regnum.to_bytes(2, byteorder="big", signed=False)
        crcres = self.__crc16(sendbytes)
        crc16bytes = crcres.to_bytes(2, byteorder="little", signed=False)
        sendbytes = sendbytes + crc16bytes
        return sendbytes

    def __smodbus(self,recvdata, valueformat=0, intsigned=False):
        '''
        解析modbus-rtu返回数据的数值

        :param: recvdata(bytes): 待解析的数据
        :param: valueformat(str|int): 数据的转化类型(float short 或者 int)直接输入类型名称字符串或者序号整数,默认值0("float")
        :param: intsigned(bool): 数据为整型时是否有符号
        :return 
                int: 运算结果
                    0: 运算成功
                    1: 无数据传入
                    2: 校验码错误
                    3: 功能码非法
                    4: 数据长度非法
                list: 除了运算成功状态下返回有值外，其他情况返回的均为[]
        '''
        if not recvdata:
            return 1,[]
        if not self.__checkcrc(recvdata):
            return 2,[]
        datalist = list(recvdata)
        #判定返回数据的功能码是否合法s
        if datalist[1] not in (1,2,3,4,5,6,15,16):
            return 3,[]
        bytenums = datalist[2]
        #判定返回数据的有效数据长度，合法数据必然为偶数个
        if bytenums % 2 != 0:
            return 4,[]
        retdata = []
        #根据设定的数据类型计算返回数据的实际值
        if valueformat in (0,"float"):
            floatnums = bytenums / 4
            floatlist = [0, 0, 0, 0]
            for i in range(int(floatnums)):
                floatlist[1] = datalist[3+i*4]
                floatlist[0] = datalist[4+i*4]
                floatlist[3] = datalist[5+i*4]
                floatlist[2] = datalist[6+i*4]
                bfloatdata = bytes(floatlist)
                [fvalue] = struct.unpack('f', bfloatdata)
                retdata.append(fvalue)
        elif valueformat in (1,"short"):
            shortintnums = bytenums / 2
            for i in range(int(shortintnums)):
                btemp = recvdata[3+i*2:5+i*2]
                shortvalue = int.from_bytes(btemp, byteorder="big", signed=intsigned)
                retdata.append(shortvalue)
        #双字数据
        elif valueformat in (2,"int"):
            intnums = bytenums / 4
            for i in range(int(intnums)):
                btemp = recvdata[3+i*4:7+i*4]
                intvalue = int.from_bytes(btemp, byteorder="big", signed=intsigned)
                retdata.append(intvalue)
        return 0,retdata

    def connect(self,port, bps, bytesize, parity, stopbits, timeout):
        '''
        打开串口，在关闭串口前回保持占用

        :param: port(str): 串口名
        :param: bps(int): 波特率
        :param: bytesize(int): 数据位
        :param: stopbits(int): 停止位
        :param: timeout(float): 连接超时时间，单位 秒(s)
        :raise ValueError: 输入的参数非法回导致连接时报错
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
        modbus-rtu自由通信，只需要输入完整的命令字符串和从站回复数据的长度

        :param order(str): 完整的通讯指令字符串,会自动移除字符串中所有的空格,字符串有效长度必须为偶数
        :param rec_byte_num(int): 需要读取的回传数据的数量(单位：字节)，默认数量为0即不读取回传数据
        :return (bytearray): 回传收到的数据，如果rec_byte_num该参数为0则不会回传任何数据
        
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
        读取串口数据 一般是 01 02 03 04 05 06功能码对应的功能

        :param slaveadd(int): 地址码
        :param funcode(int): 功能码
        :param startreg(int): 寄存器起始地址
        :param regnum(int): 寄存器读取数量
        :return (list): 根据设定的数据转换类型将查询到的数据转换后合并成list并回传
        :raises TypeError: 在端口未连接的情况下就调用该函数
        '''
        if self.__com == None:
            raise TypeError("端口未连接或者连接错误")
        send_data = self.__mmodbus(slaveadd, funcode, startreg, regnum)
        self.__com.write(send_data)
        recv_data = self.__com.read(regnum*2+5)
        if len(recv_data) > 0:
            if funcode in (3,4):
                res,value = self.__smodbus(recv_data, self.__valueformat, self.__intsigned)
            else:
                res,value = self.__smodbus(recv_data, "int", False)
        else:
            value = None
        return value
    
    def read_data_type_set(self, valueformat = "int", intsigned = False):
        '''
        返回数据的类型设置

        :param valueformat(str|int): 返回数据的转换类型
        :param intsigned(bool): 返回数据的符号有无
        '''
        if valueformat not in ("short","int","float",0,1,2):
            raise ValueError("数值类型参数错误")
        if intsigned not in (False,True):
            raise TypeError("符号类型设置错误，参数只能为布尔值")
        self.__valueformat = valueformat
        self.__intsigned = intsigned
    
    def param_connect_print(self):
        '''
        返回串口的连接参数
        '''
        return self.__param_connect_str_cn

    def write(self):
        '''
        未实现功能
        '''
        pass

    def disconnect(self):
        '''
        关闭串口,解除对串口的占用
        '''
        if self.__com != None:
            self.__com.close()
            self.__com = None

    def __del__(self):
        '''
        类实例失效时自动关闭串口，避免对串口的占用
        '''
        self.disconnect()
    
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
