#coding=utf-8
from flask import Flask,request,flash,Response,jsonify
from flask_socketio import SocketIO
from punc_predictor import PuncPredictor
from asr import AsrDecoder
from datetime import datetime
from utils.convert import to_json
from utils.console import console,get_date,get_full_datetime,get_timestamp_13
console.log(f'{"*"*10} The server is starting. {"*"*10}')
from utils.common import audio_data_to_wav_bytes
from rich.table import Table
from evaluator import Evaluator
from config import config,CONFIG_FILE_NAME
from aedetector import Aed
from queue import Queue

import os
import io
import threading
import base64
import json
import time
import sys
import requests
import logging
import copy
import random
import asyncio
import sqlite3
log = logging.getLogger('werkzeug')
log.disabled = True

STATUS_CODE_UNPROCESSED = 0
STATUS_CODE_SUCCESS = 20000
STATUS_CODE_ERROR_IO = 21000
STATUS_CODE_ERROR_RUNTIME = 40000

debug_mode = config.raw['debug_mode']
drop_data_in_advance = config.raw['drop_data_in_advance']
score_threshold = float(config.raw['threshold_bullying_recognition'])
weight_aed = float(config.raw['weight_aed'])
weight_asr = float(config.raw['weight_asr'])
batch_size = config.asr_config['batch_size']
external_interface_config = config.raw['external_interface']
downstream_sever_url = external_interface_config['downstream_server_url']
connection_callback_url = external_interface_config['connection_callback_url']
connection_callback_code = external_interface_config['connection_callback_code']
connection_callback_key = external_interface_config['connection_callback_key']

app = Flask(__name__)
socketio = SocketIO(app)
asr = AsrDecoder(config.asr_config)
eva = Evaluator(config.eva_config)
aed = Aed()

asr_workflow_delay = 1.5

# region RuntimeData
sid_mac_mapping = {}
clients = {}

queue_from_client = Queue()
queue_to_client = Queue()
queue_to_downstream_server = Queue()

asr_workflow_available = threading.Event()
client_communication_available = threading.Event()
downstream_server_communication_available = threading.Event()

exit_flag = False
# endregion

"""
数据库操作
"""
###################################################
def insert_event(device_id, mac_address, event_date):
    conn = sqlite3.connect("./violence_events.db")
    cursor = conn.cursor()
    try:
        cursor.execute('''
        INSERT INTO events (device_id, mac_address, event_date)
        VALUES (?, ?, ?)
        ''', (device_id, mac_address, event_date))
        conn.commit()
    except sqlite3.IntegrityError:
        print(f"Error: Event with mac_address {mac_address} and event_date {event_date} already exists.")
    
    conn.close()

def count_events_per_day():
    conn = sqlite3.connect("./violence_events.db")
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT mac_address, SUBSTR(event_date, 1, 10) AS event_day, COUNT(*) AS count
    FROM events
    GROUP BY mac_address, event_day
    ORDER BY event_day, mac_address
    ''')
    
    results = cursor.fetchall()
    conn.close()
    
    return results


def save_audio_to_local(audio_data, mac_address, device_id):
    # 定义基础目录
    base_dir = "/root/bullyingdectection/logs"
    
    # 获取当前日期并格式化
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 构建保存目录路径
    save_dir = os.path.join(base_dir, today)
    
    # 确保保存目录存在
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    
    # 构建音频文件名
    audio_filename = f"{device_id}_{mac_address}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
    audio_path = os.path.join(save_dir, audio_filename)
    
    # 保存音频文件到本地
    with open(audio_path, "wb") as audio_file:
        audio_file.write(audio_data)
    
    return audio_path
#################################################

# region EventHandler
def query_clients_info():
    if request.method == 'GET':
        global clients
        return Response(to_json(clients))
    elif request.method == 'POST':
        # TODO 指定查询
        return str(1)
    
def update_device_name_event_handler():
    global clients
    global debug_mode
    data = {}
    
    if request.content_type == 'application/json':
        data = request.get_json()
    elif request.content_type == 'application/x-www-form-urlencoded':
        data = request.form
    try:
        if debug_mode:
            console.log_success(f'Changed device "{data["mac"]}" name from "{config.device_dict[data["mac"]]}" to "{data["name"]}"')
        
        config.device_dict[data['mac']] = data['name']
        
        if data['mac'] in clients:
            clients[data['mac']]['device_name'] = data['name']
                    
        config.save()
    except KeyError as ke:
        console.log_error(f'Key Exception(update_device_name_event_handler):{ke}')
        return Response(f'Key Exception(update_device_name_event_handler):{ke}')
    except Exception as e:
        console.log_error(f'Exception(update_device_name_event_handler):{e}')
        return Response(f'Exception(update_device_name_event_handler):{e}')
    
    return Response('succeed')

def query_device_name_event_handler():
    return Response(to_json(config.device_dict))
    
def connect_event_handler():
    client_sid = request.sid
    client_header = dict(request.headers)
    client_mac = client_header['Mac']
    
    sid_mac_mapping[client_sid] = client_mac
    
    if client_mac not in clients:
        clients[client_mac] = {
            'device_name':client_header['Device-Name'],
            'speech_state':client_header['Speech-State'],
            'connected':True
        }
    else:
        clients[client_mac]['connected'] = True
    connection_callback(sid_mac_mapping[request.sid])
    
    if client_mac in config.device_dict:
        clients[client_mac]['device_name'] = config.device_dict[client_mac]
    else:
        clients[client_mac]['device_name'] = config.device_dict[client_mac] = f'新设备{random.randint(1000,9999)}'
        config.save() 
    
    socketio.emit('set_session_id',client_sid,to=client_sid)
    console.log_highlight(f"Client connected: '{clients[client_mac]['device_name']}/{sid_mac_mapping[request.sid]}'")
    
def disconnect_event_handler():
    console.log_highlight(f"Client disconnected: '{clients[sid_mac_mapping[request.sid]]['device_name']}/{sid_mac_mapping[request.sid]}'")
    
    clients[sid_mac_mapping[request.sid]]['connected'] = False
    connection_callback(sid_mac_mapping[request.sid])
    del sid_mac_mapping[request.sid]
    
def connection_callback(mac:str):
    info = {
        "code":connection_callback_code,
        "key":connection_callback_key,
        "mac":mac,
        "online_state": '1' if clients[mac]['connected'] else '2'
    }
    
    try:
        headers = {'Content-Type': 'application/json'}
        request = requests.post(connection_callback_url,data=to_json(info),headers=headers)
        request.raise_for_status()
        
    except ConnectionError as ce:
        console.log_error(f'Connection Exception(connection_callback): {ce}')
    except requests.exceptions.RequestException as re:
        console.log_error(f'Request Exception(connection_callback): {re}')
    except KeyError as ke:
        console.log_error(f'KeyError Exception(connection_callback): {ke}')
    except Exception as e:
        console.log_error(f'Exception(connection_callback): {e}')
    finally:
        if 'request' in locals():
            request.close()
    
def message_event_handler(data):
    console.log(f"Received message from '{clients[sid_mac_mapping[request.sid]]['device_name']}-{sid_mac_mapping[request.sid]}': {data}")
    
def receive_audio_data_event_handler(raw_data):
    global clients
    global debug_mode
    
    data_from_client = {}
    data_from_client['sid'] = request.sid
    data_from_client['mac'] = sid_mac_mapping[request.sid]
    data_from_client['data'] = json.loads(raw_data)
    data_from_client['timestamp'] = get_timestamp_13()
    data_from_client['request_time'] = get_full_datetime()
    
    queue_from_client.put(data_from_client)
    
    if debug_mode:
        console.log(f'Received data from "{clients[data_from_client["mac"]]["device_name"]}" - Task Size [{queue_from_client.qsize()}]')
    
    if not asr_workflow_available.is_set():
        if debug_mode:
            console.log_highlight('Try to waken asr workflow thread.')
        asr_workflow_available.set()
    
def data_processing_thread():
    global queue_from_client
    global queue_to_client
    global clients
    global asr_workflow_delay
    global exit_flag
    global score_threshold,debug_mode,weight_aed,weight_asr,batch_size,drop_data_in_advance
    
    while not exit_flag:
        asr_workflow_available.wait()
        console.log_success('Data processing thread is now active.')

        time_cost = 0
        
        while not queue_from_client.empty():
            try:
                if time_cost < asr_workflow_delay:
                    console.log_highlight(f'Data processing thread is waiting for more data. [{asr_workflow_delay}s]',False)
                    time.sleep(asr_workflow_delay)
                
                time_start = time.time()
                valid_entry_count = 0
                
                data_to_client_batch = []
                
                table = Table(header_style="bold cyan",title_style="bold cyan")
                table.add_column('timestamp')
                table.add_column("device")
                table.add_column("mac")
                table.add_column("channels")
                table.add_column("sample_rate")
                table.add_column("width")
                table.add_column("request_time")

                wave_bytes_list = []
            
                for index in range(min(batch_size,queue_from_client.qsize())):
                    processed_data = queue_from_client.get()
                    data_to_client_batch.append(processed_data)
                    audio_data = processed_data['data']
                    
                    flames_bytes = base64.urlsafe_b64decode(audio_data['bytes_base64'])
                    del processed_data['data']['bytes_base64']
                    processed_data['data']['bytes'] = flames_bytes
                    sample_rate = audio_data['sample_rate']
                    width = audio_data['width']
                    channels = audio_data['channels']
                    
                    table.add_row(
                        str(processed_data['timestamp']),
                        clients[processed_data['mac']]['device_name'],
                        processed_data['mac'],
                        str(channels),
                        str(sample_rate),
                        str(width),
                        processed_data['request_time']
                    )
                    
                    wave_bytes_list.append(flames_bytes)

                table.title = f'A batch of data to be processed [Size:{table.row_count}]'
                console(table)
                
                asr_res_batch = asr.decode_batch(wave_bytes_list)

                for processed_data,asr_res in zip(data_to_client_batch,asr_res_batch):
                    aed_probability = aed(processed_data['data']['bytes'],processed_data['data']['sample_rate'],processed_data['data']['channels'],processed_data['data']['width']) # 声学检测概率
                    kw_probability,keywords = eva(asr_res) # 关键字检测概率
                    probability = weight_aed * aed_probability + weight_asr * kw_probability # 概率加权求和
                
                    result = 1 if probability >= score_threshold else 0
                    
                    aed_probability = round(aed_probability,2)
                    kw_probability = round(kw_probability,2)
                    probability = round(probability,2)
                    
                    processed_data['asr_result'] = asr_res
                    processed_data['probability_aed'] = aed_probability
                    processed_data['probability_asr'] = kw_probability
                    processed_data['keywords'] = keywords
                    processed_data['score'] = probability
                    processed_data['result'] = result
                    processed_data['completion_time'] = get_full_datetime()
                    
                    if result == 1:
                        valid_entry_count += 1
                    elif drop_data_in_advance and result == 0:
                        continue
                        
                    queue_to_client.put(processed_data)
                    queue_to_downstream_server.put(processed_data)
                    
                if debug_mode:
                    data_batch = len(data_to_client_batch)
                    process_time = time.time() - time_start
                    console.log_success(f"Process a batch of data successfully.Size:[{data_batch}] TimeCost:[{process_time}s]")
                    
                    res_table = Table(header_style="bold cyan",title="Result",title_style="bold cyan")
                    res_table.add_column('timestamp')
                    res_table.add_column('device')
                    res_table.add_column('text')
                    res_table.add_column('keywords')
                    res_table.add_column('aed_score')
                    res_table.add_column('asr_score')
                    res_table.add_column('score')
                    res_table.add_column('result')
                    res_table.add_column('request_time')
                    res_table.add_column("completion_time")
                    
                    for data in data_to_client_batch:
                        res_table.add_row(
                            str(data['timestamp']),
                            clients[data['mac']]['device_name'],
                            data['asr_result'],
                            ','.join(data['keywords']),
                            str(data['probability_aed']),
                            str(data['probability_asr']),
                            str(data['score']),
                            str(data['result']),
                            data['request_time'],
                            data['completion_time']
                        )
                    
                    console(res_table)
                
                if drop_data_in_advance and valid_entry_count == 0:
                    continue
                    
                if not client_communication_available.is_set():
                    client_communication_available.set()
                if not downstream_server_communication_available.is_set():
                    downstream_server_communication_available.set()

                time_cost = time.time() - time_start
                
            except Exception as e:
                console.log_error(f'Exception(data_processing_thread): {e}')

        console.log('Data processing thread is now inactive.')
        asr_workflow_available.clear()
    
def client_communication_thread():
    global exit_flag
    global debug_mode
    
    while not exit_flag:
        client_communication_available.wait()
        if debug_mode:
            console.log_success('Client communication thread is now active.')
        
        while True:     
            while not queue_to_client.empty():
                try:
                    raw_data_to_client = queue_to_client.get()
                    # 提取必要信息
                    mac_address = raw_data_to_client.get('mac', 'Unknown')  # 从 raw_data_to_client 中获取 MAC 地址
                    device_id = clients.get(mac_address, {}).get('device_name', 'Unknown')  # 从 clients 中获取设备名称
                    timestamp = datetime.now()
                    result = raw_data_to_client.get('result', 'Unknown')  #
                    print("\n","\n","\n","\n",)
                    print(f"Device ID: {device_id}")
                    print(f"MAC Address: {mac_address}")
                    print(f"Timestamp: {timestamp}")
                    print(f"Result: {result}")
                    # TODO 
                    # 仅返回判断结果
                    data_to_client = {}
                    if debug_mode:
                        data_to_client['timestamp'] = raw_data_to_client['timestamp']
                        data_to_client['request_time'] = raw_data_to_client['request_time']
                        data_to_client['completion_time'] = raw_data_to_client['completion_time']
                        data_to_client['probability_aed'] = raw_data_to_client['probability_aed']
                        data_to_client['probability_asr'] = raw_data_to_client['probability_asr']
                        data_to_client['asr_result'] = raw_data_to_client['asr_result']
                        data_to_client['score'] = raw_data_to_client['score']
                        data_to_client['keywords'] = raw_data_to_client['keywords']
                    data_to_client['result'] = raw_data_to_client['result']
                    
                    socketio.emit('receive_res',data_to_client,to=raw_data_to_client['sid'])
                    # 判断是否为暴力事件并插入数据库
                    # print(clients[raw_data_to_downstream_server['mac']]['device_name'])未定义 
                    if result == 1:  # 假设 'bullying' 表示暴力事件
                        insert_event(device_id, mac_address, timestamp)#插入信息后
                    # 提取音频数据
                        audio_data = raw_data_to_client.get('data', {}).get('bytes', None)
                        if audio_data:
                            save_audio_to_local(audio_data, mac_address, device_id)
                        #并保存暴力事件音频
                except Exception as e:
                    console.log_error(f'Exception(client_communication_thread): {e}')                    
            time.sleep(1)
            if queue_to_client.empty():
                break
        
        client_communication_available.clear()
        if debug_mode:
            console.log('Client communication thread is now inactive.')

# 负责预警和保存数据到本地的线程
def downstream_server_communication_thread():
    global exit_flag
    global downstream_sever_url
    global clients
    global debug_mode
    global drop_data_in_advance
    
    while not exit_flag:
        downstream_server_communication_available.wait()
        if debug_mode:            
            console.log_success('Downstream server communication thread is now active.')
        
        while True:
            while not queue_to_downstream_server.empty():
                now = datetime.now()
                formatted_time = now.strftime("%Y-%m-%d %H:%M:%S")  # 格式化为年-月-日 时:分:秒
                raw_data_to_downstream_server = queue_to_downstream_server.get()      
                if not drop_data_in_advance:
                    is_not_bully = raw_data_to_downstream_server['result'] == 0
                    do_not_containt_keywords = len(raw_data_to_downstream_server['keywords']) == 0                 
                    if is_not_bully and do_not_containt_keywords:
                        console.log(f'Drop data "{raw_data_to_downstream_server["timestamp"]}"',False)
                        continue
                target_data = {}
                wav_bytes = audio_data_to_wav_bytes(
                    raw_data_to_downstream_server['data']['bytes'],
                    raw_data_to_downstream_server['data']['sample_rate'],
                    raw_data_to_downstream_server['data']['channels'],
                    raw_data_to_downstream_server['data']['width']
                )
                
                try:
                    files = {'file': (f'{raw_data_to_downstream_server["timestamp"]}.wav', io.BytesIO(wav_bytes), 'audio/wav')}
                    target_data['device_ccid'] = clients[raw_data_to_downstream_server['mac']]['device_name']
                    target_data['fql_alarm_type'] = str(raw_data_to_downstream_server['result'])
                    target_data['fql_alarm_text'] = ','.join(raw_data_to_downstream_server['keywords'])
                    
                    start_sending_time = get_full_datetime()
                    request = requests.post(downstream_sever_url, data=target_data,files=files)
                    request.raise_for_status()
                    sending_time = get_full_datetime()
                    
                    console.log_success(f'Send data [{raw_data_to_downstream_server["timestamp"]}] to Downstream Server successfully."{queue_to_downstream_server.qsize()} Left"\nRequest Time[{raw_data_to_downstream_server["request_time"]}]\nCompletion Time[{raw_data_to_downstream_server["completion_time"]}]\nStart sending Time[{start_sending_time}] \nSending Time[{sending_time}]')
                    
                    # ↓↓↓↓↓↓  数据写到本地 （只记录暴力数据，如果需要全存那就把下面这段移到暴力判断前面去）
                    result_to_local = { 'asr_res':raw_data_to_downstream_server['asr_result'],
                                        'probability_aed':raw_data_to_downstream_server['probability_aed'],
                                        'probability_asr':raw_data_to_downstream_server['probability_asr'],
                                        'keywords':raw_data_to_downstream_server['keywords'],
                                        'score':raw_data_to_downstream_server['score'],
                                        'result':raw_data_to_downstream_server['result']
                                        }

                    
                    if debug_mode:
                        console.log(request.text,False)
                        
                        result_to_local['request_time'] = raw_data_to_downstream_server['request_time']
                        result_to_local['completion_time'] = raw_data_to_downstream_server['completion_time']
                        result_to_local['start_sending_time'] = start_sending_time
                        result_to_local['sending_time'] = sending_time
 
                    asyncio.run(console.write_wav_to_local_async(raw_data_to_downstream_server["timestamp"],wav_bytes))
                    asyncio.run(console.write_res_to_local_async(raw_data_to_downstream_server["timestamp"],result_to_local))
                    # ↑↑↑↑↑↑
                
                except ConnectionError as ce:
                    console.log_error(f'Connection Exception(target_server_communication_thread): {ce}')
                except requests.exceptions.RequestException as re:
                    console.log_error(f'Request Exception(target_server_communication_thread): {re}')
                except KeyError as ke:
                    console.log_error(f'KeyError Exception(target_server_communication_thread): {ke}')
                except Exception as e:
                    console.log_error(f'Exception(target_server_communication_thread): {e}')
                finally:
                    if 'request' in locals():
                        request.close()
                
            time.sleep(1)
            if queue_to_downstream_server.empty():
                break
        
        downstream_server_communication_available.clear()
        if debug_mode:
            console.log('Downstream server communication thread is now inactive.')

# endregion

# region SocketEvent
@app.route('/info/clients',methods = ['GET','POST'])
def handle_query_clients_info():
    return query_clients_info()

@app.route('/devices/update_name',methods = ['POST'])
def handle_update_device_name():
    return update_device_name_event_handler()

@app.route('/devices/query_name',methods = ['GET'])
def handle_query_device_name():
    return query_device_name_event_handler()

@socketio.on('connect')
def handle_connect():
    connect_event_handler()
    
@socketio.on('disconnect')
def handle_disconnect():  
    disconnect_event_handler()
    
@socketio.on('message')
def handle_message(data):
    message_event_handler(data)

@socketio.on('receive_audio_data')
def receive_audio_data(raw_data):
    receive_audio_data_event_handler(raw_data)
# endregion

# region Legacy
@app.route('/',methods = ['GET',"POST"])
def handler():
    if request.method == 'GET':
        example_info = json.dumps({
            'identifier':1,
            'token':"4s8b3d2z5x",
            'channels': 1,
            'sample_rate': 16000,
            'width': 2,
            'bytes_base64': "[wav bytes]"   
        },indent=4)
        response = "<h1>[System] You need to Post data as json with channels,sample_rate,width,bytes_base64.</h1>"
        response += '<p>Example :<p>'
        response += f'<p>{example_info}<p>'
        return response
    
    elif request.method == 'POST':
        data = request.get_json()
        response = {}
        response['status_code'] = STATUS_CODE_UNPROCESSED
        try:
            request_time = get_full_datetime()
            request_date = get_date()
            timestamp = get_timestamp_13()
            
            t1 = time.time()
            identifier = data["identifier"]
            token = data["token"]
            channels = data["channels"]
            sample_rate = data["sample_rate"]
            width = data["width"]
            bytes = base64.urlsafe_b64decode(data["bytes_base64"]) # 解码为字节
            
            print()
            
            table = Table(header_style="bold cyan",title="Wav Details",title_style="bold cyan")
            table.add_column("device")
            table.add_column("channels")
            table.add_column("sample_rate")
            table.add_column("width")
            table.add_column("request_time")
            
            table.add_row(str(identifier),str(channels),str(sample_rate),str(width),request_time)
            
            console.log(f"Trying resolving data from device[{identifier}]:timestamp[{timestamp}]")
            console(table)
            
            res = asr.decode_single_bytes(bytes,sample_rate)
            resp = None
            
            aed_probability = aed(bytes,sample_rate,channels,width) # 声学检测概率
            kw_probability = eva(res) # 关键字检测概率
            probability = 0.5 * aed_probability + 0.5 * kw_probability # 概率加权求和
            
            aed_probability = round(aed_probability,2)
            kw_probability = round(kw_probability,2)
            probability = round(probability,2)
            
            response['status_code'] = STATUS_CODE_SUCCESS
            response['res'] = res
            response['resp'] = resp
            
            response["aed_probability"] = aed_probability
            response["kw_probability"] = kw_probability
            response['probability'] = probability
            
            table = Table(header_style="bold cyan",title="Result",title_style="bold cyan")
            table.add_column("Result")
            table.add_column("Result With Punctuation")
            table.add_column("AED_Probability")
            table.add_column("KW_Probability")
            table.add_column("Probability")
            table.add_row(res,resp,str(aed_probability),str(kw_probability),str(probability))
            
            console.log_success(f"Resolved data[{identifier}]:[{timestamp}] successfully!")
            console(table)
            console.log(f"Time Cost:{(time.time() - t1)}s")
            
            with open(f"./logs/{request_date}.txt","+a",encoding="utf-8") as logger:
                logger.write(f"Deviced:[{identifier}]\n"+
                             f"Channels:[{channels}]\n"+
                             f"SampleRate:[{sample_rate}]\n"+
                             f"Width:[{width}]\n"+
                             f"RequestTime:[{request_time}]\n"+
                             f"Res:[{res}]\n"+
                             f"Resp:[{resp}]\n\n")
                logger.close()
                console.log_success("Saved!")
            
            print()##输出的

            return Response(to_json(response),mimetype="mimetype='application/json'")
        except IOError as msg:
            console.log_error(f"IO Error Msg:{msg}")
            response['status_code'] = STATUS_CODE_ERROR_IO
            return Response(to_json(response),mimetype="mimetype='application/json'")
        except Exception as msg:
            console.log_error(f"Error Msg:{msg}")
            response['status_code'] = STATUS_CODE_ERROR_RUNTIME
            return Response(to_json(response),mimetype="mimetype='application/json'")
# endregion

if __name__ == "__main__":
    port = config.raw['port']
    if len(sys.argv)>1:
        port = int(sys.argv[1])   
    processing_thread = threading.Thread(target=data_processing_thread)
    client_thread = threading.Thread(target=client_communication_thread)
    target_server_thread = threading.Thread(target=downstream_server_communication_thread)
    
    processing_thread.setDaemon(True)
    client_thread.setDaemon(True)
    target_server_thread.setDaemon(True)
    
    processing_thread.start()
    client_thread.start()
    target_server_thread.start()
    
    # TODO
    # Deploy with WSGI
    console.log_highlight(f"Listenning port at {port}")
    socketio.run(app, port=port,host='0.0.0.0',allow_unsafe_werkzeug=True)
    
    console.log(f'{"*"*10} The server has been shut down. {"*"*10}')
