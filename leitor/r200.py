#Bibliteca do módulo R200

#Por Heli Neres Silva

#Declaração das bibliotecas utilizadas
from machine import UART
from time import sleep
import ubinascii

#Declaração do objeto para comunicaçaõ UART, utilizando a UART 2 do ESP32
uart = UART(2, 115200)

#Função para converter o frame de bytes recebido por UART em uma lista
def frametolist(frame):
    frame_decoded = ubinascii.hexlify(frame).decode()
    b = []
    for i in range(0,len(frame_decoded),2):
        b.append(frame_decoded[i]+frame_decoded[i+1])
    return b

#Funções para checar a validade dos dados recebidos
def check_sum(b):
    checksum = b[-2]
    check = hex(sum([int('0x'+i) for i in b[1:-2]]))[-2:]
    validation = checksum==check
    return checksum, check, validation

def check_sum_int(b):
    checksum = b[-2]
    check = hex(sum([i for i in b[1:-2]]))
    if len(check)<4:
        check = int(check)
    else:
        check = int('0x'+check[-2:])
    validation = checksum==check
    return checksum, check, validation

#Funções para converter os bytes recebidos em uma lista com os campos separados
def build_frame(command, param):
    frame_type = 0x00
    header = 0xaa
    end = 0xdd
    pllow,plhigh = divmod(len(param),0x100)
    frame = [header,frame_type,command,pllow,plhigh]
    if len(param)>0: frame.extend(param)
    frame.extend([0x00,end])
    checksum, check, validation = check_sum_int(frame)
    frame[-2] = check
    checksum, check, validation = check_sum_int(frame)
    return frame

def build_frame_bank(command, membank, ap=[0x00,0x00,0xff,0xff], sa=[0x00,0x00], dl=[0x00,0x04]):
    frame_type = 0x00
    header = 0xaa
    end = 0xdd
    param = ap.copy()
    param.extend(membank)
    param.extend(sa)
    param.extend(dl)
    pllow,plhigh = divmod(len(param),0x100)
    frame = [header,frame_type,command,pllow,plhigh]
    if len(param)>0: frame.extend(param)
    frame.extend([0x00,end])
    checksum, check, validation = check_sum_int(frame)
    frame[-2] = check
    checksum, check, validation = check_sum_int(frame)
    return frame

#Função para verificar a validade de um frame recebido e retornar um dicionário com os campos do frame
def check_frame(response):
    b = frametolist(response)
    frame = {}
    frame['frame_type'] = b[1]
    frame['command'] = b[2]
    frame['pl'] = b[3]+b[4]
    
    if frame['command']=='03':
        frame['info_type'] = b[5]
        info = ''.join(b[6:6+int('0x'+frame['pl'])-1])
        frame['info'] = ubinascii.unhexlify(info).decode()
        checksum, check, validation = check_sum(b)
        frame['validation']=validation
    elif frame['command']=='22':
        frame['rssi'] = b[5]
        frame['pc'] = b[6]+b[7]
        frame['epc'] = ''.join(b[8:-4])
        frame['crc'] = ''.join(b[-4:-2])
        checksum, check, validation = check_sum(b)
        frame['validation']=validation
    elif frame['command']=='ff':
        frame['param'] = b[5]
        checksum, check, validation = check_sum(b)
        frame['validation']=validation
    else:
        frame['validation']=False
    
    return frame

#função para ler os dados de versão do sensor
def ler_versao(info_frame):
    data=[]
    for i in info_frame:
        uart.write(bytes(i))
        sleep(0.1)
        if uart.any()>0:
            a = uart.read()
            print(a)
            data.append(check_frame(a))
    return data

#Função para procurar uma vez por tags
def single_polling():
    data=build_frame(0x22,[])
    uart.write(bytes(data))
    sleep(0.1)
    if uart.any()>0:
        a = uart.read()
        a = check_frame(a)
    return a

#Função para procurar várias vezes por tags
def multi_polling(limit):
    data=build_frame(0x27,[0x22,0x27,0x10])
    uart.write(bytes(data))
    sleep(0.2)
    i=0
    leitura = {}
    while True:
        if uart.any()>0:
            a = uart.read()
            i+=1
            try:
                a = check_frame(a)
            except Exception as e:
                print(e)
                continue
            if a['validation'] and a['command']=='22':
                leitura = a
        if i == limit-1:
            data=build_frame(0x28,[])
            uart.write(bytes(data))
            sleep(1)
        if i == limit:
            break
    
    return leitura
