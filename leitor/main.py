#Código de principal do Leitor

#Por Heli Neres Silva

#Declaração das bibliotecas utilizadas
import ufirestore
from ufirestore.json import FirebaseJson
from firebase_auth import FirebaseAuth
import urequests
from machine import RTC, Pin, SoftI2C, I2C
from ds1307 import DS1307
import r200
import json
from lcd_api import LcdApi
from i2c_lcd import I2cLcd
from time import sleep, time_ns
from rotary_irq_esp import RotaryIRQ
import network
from blecentral import BLESimpleCentral
import bluetooth

#Inicialização do objeto para comunicação com o módulo RTC
i2c_rtc = I2C(0,scl = Pin(26),sda = Pin(25),freq = 100000)
rtc = DS1307(i2c_rtc)

#Definição do pino para o botão do encoder
pin = Pin(35, Pin.IN, Pin.PULL_UP)

#Definição do objeto para controle do encoder
r = RotaryIRQ(
    pin_num_clk=33,
    pin_num_dt=32, 
    min_val=0, 
    max_val=4,
    reverse=True,
    incr=1,
    range_mode=RotaryIRQ.RANGE_BOUNDED,
    pull_up=True,
    half_step=False,
)

#Inicialização do objeto para comunicação com o display
I2C_ADDR = 0x27
totalRows = 2
totalColumns = 16

i2c = SoftI2C(scl=Pin(22), sda=Pin(21), freq=10000)
lcd = I2cLcd(i2c, I2C_ADDR, totalRows, totalColumns)

#Variáveis auxiliares para o menu
val_old = r.value()
pin_old = pin.value()
nivel = False
aux = True
time_old = time_ns()
lcd.clear()
itens = ["Leitura         Individual",
         "Pesagem         ",
         "Cadastrar       Animal Novo",
         "Registrar       Baixa de Animal",
         "Atualizar       Servidor Web"]

#Inicialização do objeto para comunicação Bluetooth
ble = bluetooth.BLE()
central = BLESimpleCentral(ble)
peso = '0'

#Função para realizar a pesagem
def balanca():
    wlan.active(0)
    ble.active(1)
    global peso
    not_found = False

    def on_scan(addr_type, addr, name):
        if addr_type is not None:
            lcd.clear()
            lcd.putstr('Balança Conectada')
            central.connect()
        else:
            nonlocal not_found
            not_found = True
            lcd.clear()
            lcd.putstr('Balança nao Conectada')

    central.scan(callback=on_scan)

    # Wait for connection...
    while not central.is_connected():
        time.sleep_ms(1000)
        if not_found:
            return

    def on_rx(v):
        global peso
        peso = str(bytes(v),'utf-8')

    central.on_notify(on_rx)

    with_response = False
    cont = 0
    while central.is_connected():
        try:
            v = '0'
            central.write(v, with_response)
        except:
            print("TX failed")
        time.sleep_ms(100)
        if cont>20: break
        cont += 1

#Função para reescrever a hora fornecida pelo RTC no formato aceito pelo Firestore
def fireTimestamp(hora):
    return str(hora[0]) + '-' + str(hora[1]) + '-' + str(hora[2]) + 'T' + str(hora[4]) + ':' + str(hora[5]) + ':' + str(hora[6]) + '.' + str(hora[7]) + 'Z'

#Função para escrever o log
def escreve_log(texto):
    hora = fireTimestamp(rtc.datetime())
    log = '\n' + hora + ' : ' + texto
    with open('log.txt','a') as base:
        base.write(log)
        base.close()

#Função para adicionar item à fila de espera
def adiciona_fila(tipo, epc, dados, index):
    with open('fila_de_espera.txt','a') as fila:
        y=tipo+' '+epc+' '+dados+' '+index+'\n'
        fila.write(y)
        fila.close()

#Função para obter os ids cadastrados e com saída regisitrada
def cadastrados():
    lista = [[],[]]
    with open('base.json') as base:
        y = json.load(base)
    for n in y['fazenda'][0]['rebanho']:
        for i in n.keys():
            lista[0].append(i)
            #lista[1].append('abate' in n[i][-1]['dados'][-1])
            lista[1].append(len(n[i][-1]['dados']))
    return lista

#Função para cadastrar novo animal
def cadastro():
    base_local = FirebaseJson()
    id_novo = r200.multi_polling(50)
    lista_cadastrados = cadastrados()
    #id_novo = {'command':'22','epc':'42'}
    
    if not('command' in id_novo) or id_novo['command'] != '22' or not(id_novo['validation']):
        lcd.clear()
        lcd.putstr('Nenhuma Tag Detectada')
        escreve_log('Tentativa de cadastro. Nenhuma Tag Detectada')
        return
    elif id_novo['epc'] in lista_cadastrados[0] and lista_cadastrados[1][lista_cadastrados[0].index(id_novo['epc'])]%2==1:
        lcd.clear()
        lcd.putstr('Tag já cadastrada')
        escreve_log('Tentativa de cadastro. Tag já cadastrada')
        return
    
    cadastro_novo = {"pai":0,"mae":0,"cadastro":fireTimestamp(rtc.datetime()),"nascimento":fireTimestamp(rtc.datetime())}
    cadastro_str = ''
    for i in cadastro_novo.keys():
        cadastro_str += str(i)+','+str(cadastro_novo[i])+','
    
    try:
        index = str(lista_cadastrados[1][lista_cadastrados[0].index(id_novo['epc'])]//2)
    except:
        index = '1'
    adiciona_fila('cadastro',id_novo['epc'],cadastro_str,index)
    
    with open('base.json','r') as base:
        y = json.load(base)
        if id_novo['epc'] in lista_cadastrados[0]:
            y['fazenda'][0]['rebanho'][lista_cadastrados[0].index(id_novo['epc'])][id_novo['epc']][-1]['dados'].append(cadastro_novo)
            #print('usado')
        else:
            y['fazenda'][0]['rebanho'].append({id_novo['epc']:[{"dados":[cadastro_novo],"pesagem":[]}]})
            #print('novo')
        base.close()
    with open('base.json','w') as base:
        base.write(json.dumps(y))
        base.close()
    escreve_log(id_novo['epc'] + ' cadastrado. Base local atualizada')
    lcd.clear()
    lcd.putstr('Animal Cadastrado')

#Função para registrar saída de animal
def abate():
    base_local = FirebaseJson()
    id_novo = r200.multi_polling(50)
    lista_cadastrados = cadastrados()
    
    if not('command' in id_novo) or id_novo['command'] != '22' or not(id_novo['validation']):
        lcd.clear()
        lcd.putstr('Nenhuma Tag Detectada')
        escreve_log('Tentativa de cadastro de abate. Nenhuma Tag Detectada')
        return
    elif not(id_novo['epc'] in lista_cadastrados[0]):
        lcd.clear()
        lcd.putstr('Tag não cadastrada')
        escreve_log('Tentativa de cadastro de abate. Tag não cadastrada')
        return
    elif lista_cadastrados[1][lista_cadastrados[0].index(id_novo['epc'])]%2==0:
        lcd.clear()
        lcd.putstr('Tag de animal abatido')
        escreve_log('Tentativa de cadastro de abate. Tag de animal abatido')
        return
    
    cadastro_novo = {"abate":True,"data_abate":fireTimestamp(rtc.datetime())}
    cadastro_str = ''
    for i in cadastro_novo.keys():
        if i == 'abate':
            cadastro_str += str(i)+','+str(int(cadastro_novo[i]))+','
        else:
            cadastro_str += str(i)+','+str(cadastro_novo[i])+','
        
    adiciona_fila('abate', id_novo['epc'], cadastro_str, str(lista_cadastrados[1][lista_cadastrados[0].index(id_novo['epc'])]//2))
    
    with open('base.json','r') as base:
        y = json.load(base)
        y['fazenda'][0]['rebanho'][lista_cadastrados[0].index(id_novo['epc'])][id_novo['epc']][-1]['dados'].append(cadastro_novo)
        base.close()
    with open('base.json','w') as base:
        base.write(json.dumps(y))
        base.close()
    escreve_log(id_novo['epc'] + ' abatido. Base local atualizada')
    lcd.clear()
    lcd.putstr('Abate registrado')

#Função para a pesagem dos animais
def pesagem():
    global peso
    balanca()
    if not central.is_connected():
        return
    
    base_local = FirebaseJson()
    id_novo = r200.multi_polling(50)
    peso = 150
    lista_cadastrados = cadastrados()
    #id_novo = {'command':'22','epc':'42'}
    
    if not('command' in id_novo) or id_novo['command'] != '22' or not(id_novo['validation']):
        lcd.clear()
        lcd.putstr('Nenhuma Tag Detectada')
        escreve_log('Tentativa de pesagem. Nenhuma Tag Detectada')
        return
    elif not(id_novo['epc'] in lista_cadastrados[0]):
        lcd.clear()
        lcd.putstr('Tag não cadastrada')
        escreve_log('Tentativa de pesagem. Tag não cadastrada')
        return
    elif lista_cadastrados[1][lista_cadastrados[0].index(id_novo['epc'])]%2==0:
        lcd.clear()
        lcd.putstr('Tag de animal abatido')
        escreve_log('Tentativa de pesagem. Tag de animal abatido')
        return
    
    peso_novo = {"peso":str(peso),"data_pesagem":fireTimestamp(rtc.datetime())}
    peso_str = ''
    for i in peso_novo.keys():
        peso_str += str(i)+','+str(peso_novo[i])+','
    adiciona_fila('pesagem', id_novo['epc'], peso_str, '0')
    
    with open('base.json','r') as base:
        y = json.load(base)
        y['fazenda'][0]['rebanho'][lista_cadastrados[0].index(id_novo['epc'])][id_novo['epc']][-1]['pesagem'].append(peso_novo)
        base.close()
        #print('escrito')
    with open('base.json','w') as base:
        base.write(json.dumps(y))
        base.close()
    escreve_log(id_novo['epc'] + ' pesado. Base local atualizada')
    lcd.clear()
    lcd.putstr('Animal pesado')

#Função para limpar o arquivo da Fila de Espera
def limpa_fila(atualizados):
    with open('fila_de_espera.txt') as fila:
        y = fila.read()
        x = [i.split(' ') for i in y.split('\n')]
        x = [[i[0],i[1],i[2].split(','),i[3]] for i in x if len(i)>1]
    
    if not(len(atualizados)>0):
        return
    
    atualizados.reverse()
    
    for i in atualizados:
        x.pop(i)
    
    restantes = ''
    for i in x:
        restantes += str(i)
        
    with open('fila_de_espera.txt','w') as fila:
        fila.write(restantes)

#Função para atualizar o servidor Firestore
def atualiza_web():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        lcd.clear()
        lcd.putstr('Erro. Sem acesso à internet')
        return

    ufirestore.set_project_id("teste-rfid-r200")

    auth = FirebaseAuth("AIzaSyCtq1Dca7UA2ftdiirhZ3SiteamDe1_Is4")
    auth.sign_in('helinelas@gmail.com', 'Theflash10*')

    ufirestore.set_access_token(auth.session.access_token)
    
    with open('fila_de_espera.txt') as fila:
        y = fila.read()
        x = [i.split(' ') for i in y.split('\n')]
        x = [[i[0],i[1],i[2].split(','),i[3]] for i in x if len(i)>1]
        fila.close()
        #remover da fila após atualizar
    atualizados = []
    for j,i in enumerate(x):
        print(j)
        if i[0] == 'pesagem':
            base_local = FirebaseJson()
            base_local.set("peso/integerValue", int(i[2][i[2].index('peso')+1]))
            base_local.set("data_pesagem/timestampValue", i[2][i[2].index('data_pesagem')+1])

            try:
                response = ufirestore.create("fazenda/rebanho/" + i[1] + "/pesagem/pesagem", base_local, bg=False)
            except Exception as e:
                response = e.message.split('"')
                #print(response)
                
            if response == None or ('createTime' in response):
                escreve_log(i[1] + ' pesado. Base web atualizada')
                atualizados.append(j)
            else:
                escreve_log(response[response.index('message')+2])
            
        elif i[0] == 'cadastro':
            base_local = FirebaseJson()
            base_local.set("pai/integerValue", int(i[2][i[2].index('pai')+1]))
            base_local.set("mae/integerValue", int(i[2][i[2].index('mae')+1]))
            base_local.set("cadastro/timestampValue", i[2][i[2].index('cadastro')+1])
            base_local.set("nascimento/timestampValue", i[2][i[2].index('nascimento')+1])

            try:
                response = ufirestore.create("fazenda/rebanho/" + i[1] + "/dados" + i[3] + "/cadastro", base_local, bg=False)
            except Exception as e:
                response = e.message.split('"')
                print(response)
                
            if response == None or ('createTime' in response):
                escreve_log(i[1] + ' cadastrado. Base web atualizada')
                atualizados.append(j)
            else:
                escreve_log(response[response.index('message')+2])
                                     
        elif i[0] == 'abate':
            base_local = FirebaseJson()
            base_local.set("abate/booleanValue", bool(int(i[2][i[2].index('abate')+1])))
            base_local.set("data_abate/timestampValue", i[2][i[2].index('data_abate')+1])
            
            try:
                response = ufirestore.create("fazenda/rebanho/" + i[1] + "/dados" + i[3] + "/abate", base_local, bg=False)
            except Exception as e:
                response = e.message.split('"')
                print(response)
                
            if response == None or ('createTime' in response):
                escreve_log(i[1] + ' abatido. Base web atualizada')
                atualizados.append(j)
            else:
                escreve_log(response[response.index('message')+2])
        
        dados = base_local.data
        for i in dados:
            base_local.remove(i)
                
    limpa_fila(atualizados)
    lcd.clear()
    lcd.putstr("Servidor    Atualizado")

#Função para ler uma tag
def ler_tag():
    lcd.clear()
    lcd.putstr('Lendo...')
    tag = r200.multi_polling(50)
    
    if not('command' in tag) or tag['command'] != '22' or not(tag['validation']):
        lcd.clear()
        lcd.putstr('Erro na Leitura')
        return
    
    lcd.clear()
    lcd.putstr('id: ' + str(tag['epc']))

#Código principal do menu
while True:
    val_new = r.value()
    pin_new = pin.value()
    time_new = time_ns()
    
    if (time_new-time_old)<10000:
        time_old = time_new
        continue
        
    if (val_old != val_new and not(nivel)) or aux:
        val_old = val_new
        aux = False
        lcd.clear()
        lcd.putstr(itens[val_new])

    if pin_old != pin_new:
        pin_old = pin_new
        if pin_new == 0:
            nivel = not(nivel)
            if nivel:
                if val_old == 0:
                    ler_tag()
                elif val_old == 1:
                    pesagem()
                elif val_old == 2:
                    cadastro()
                elif val_old == 3:
                    lcd.clear()
                    lcd.putstr("Registro        de Baixa")
                    abate()
                elif val_old == 4:
                    wlan.active(1)
                    ble.active(0)
                    lcd.clear()
                    lcd.putstr("Atualizando Web Aguarde")
                    atualiza_web()
            else:
                aux = True
