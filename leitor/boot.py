#Código de inicialização do Leitor

#Por Heli Neres Silva

#Declaração das bibliotecas utilizadas
import time
import network
from machine import RTC, Pin, SoftI2C, I2C
from ds1307 import DS1307
from lcd_api import LcdApi
from i2c_lcd import I2cLcd

#Inicialização do objeto para comunicação com o módulo RTC
i2c_rtc = I2C(0,scl = Pin(26),sda = Pin(25),freq = 100000)
rtc = DS1307(i2c_rtc)

#Inicialização do objeto para comunicação com o display LCD
I2C_ADDR = 0x27
totalRows = 2
totalColumns = 16

i2c = SoftI2C(scl=Pin(22), sda=Pin(21), freq=10000)
lcd = I2cLcd(i2c, I2C_ADDR, totalRows, totalColumns)

#Inicialização do objeto para controle do Wifi
wlan = network.WLAN(network.STA_IF)
#Ativação do Wifi
wlan.active(True)
if not wlan.isconnected():
    #Tentativa de conexão com a rede definida
    try:
        wlan.connect("NOME_DA_REDE", "SENHA")
    except Exception as e:
        print(e)
    cont = 0
    lcd.clear()
    lcd.putstr('Conectando ao   Wifi...')
    while not wlan.isconnected():
        if cont > 20:
            lcd.clear()
            lcd.putstr('Falha na Conexao')
            break
        time.sleep(1)
        cont +=1

#Caso seja conectado, atualiza o horário do RTC por um servidor
if wlan.isconnected():
    import ntptime
    rtc2 = RTC()
    ntptime.settime()
    rtc.datetime(rtc2.datetime())
    
    lcd.clear()
    lcd.putstr('Conexão Realizada')
