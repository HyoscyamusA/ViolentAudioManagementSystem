import tensorflow as tf
import vggish_input
import vggish_params
import vggish_postprocess
import vggish_slim
import joblib
import wave
tf.compat.v1.disable_eager_execution()
import os
import base64
import json
import sys
import datetime
sys.path.append('...')
from flask import Flask, request, flash, Response,make_response
import math
def IsViloent(audio_file:str):

# 加载VGGish模型和预训练的权重
    tf.compat.v1.reset_default_graph()
    sess = tf.compat.v1.Session()
    vggish_slim.define_vggish_slim(training=False)
    vggish_slim.load_vggish_slim_checkpoint(sess, "vggish_model.ckpt")


    # 设置音频特征提取参数
    params = vggish_params.EXAMPLE_HOP_SECONDS
    input_tensor = sess.graph.get_tensor_by_name(vggish_params.INPUT_TENSOR_NAME)
    output_tensor = sess.graph.get_tensor_by_name(vggish_params.OUTPUT_TENSOR_NAME)


    # 读取音频文件并进行特征提取
    examples_batch = vggish_input.wavfile_to_examples(audio_file)
    features_tensor = sess.run(output_tensor, feed_dict={input_tensor: examples_batch})


    # 后处理提取的特征
    pproc = vggish_postprocess.Postprocessor("vggish_pca_params.npz")
    postprocessed_batch = pproc.postprocess(features_tensor)


    # 打印特征数组的形状和值
    print("特征数组形状:", postprocessed_batch.shape)
    print("特征数组值:")
    print(postprocessed_batch)



    bad = ['Speech', 'Male speech, man speaking', 'Female speech, woman speaking', 'Child speech, kid speaking', 'Conversation', 'Narration, monologue', 'Babbling', 'Whispering', 'Laughter', 'Baby laughter', 'Giggle', 'Snicker', 'Belly laugh', 'Chuckle, chortle', 'Baby cry, infant cry', 'Singing', 'Choir', 'Yodeling', 'Chant', 'Mantra', 'Male singing', 'Female singing', 'Child singing', 'Synthetic singing', 'Rapping', 'Whistling', 'Breathing', 'Wheeze', 'Snoring', 'Gasp', 'Pant', 'Snort', 'Cough', 'Throat clearing', 'Sneeze', 'Sniff', 'Run', 'Walk, footsteps', 'Chewing, mastication', 'Gargling', 'Burping, eructation', 'Hiccup', 'Fart', 'Hands', 'Finger snapping', 'Clapping', 'Cheering', 'Applause', 'Chatter', 'Crowd', 'Hubbub, speech noise, speech babble', 'Children playing']
    good = ['Crying, sobbing', 'Shout', 'Bellow', 'Whoop', 'Yell', 'Battle cry', 'Children shouting', 'Screaming', 'Whimper', 'Wail, moan', 'Sigh', 'Groan', 'Squeal']

    data = postprocessed_batch
    gmm1 = joblib.load(os.path.join('Model/zhenglei.model'))
    gmm2 = joblib.load(os.path.join('Model/fulei.model'))

    b = gmm2.score(data)
    a = gmm1.score(data)
    max_val=max(a,b)
    sma = (math.exp(a-max_val)) / ((math.exp(a-max_val) + math.exp(b-max_val)))# 暴力概率
    # sma = math.exp(a) / (math.exp(a) + math.exp(b)) 因为a和b负的太大了 会报除零错误，但是我这个好像也不是很准
    return sma

#filename = deque([])
output_filename ="output"
def save_wav_from_base64(base64_data: str, filename: str,channels,sampwidth,framerate):
    wav_bytes = base64.urlsafe_b64decode(base64_data.encode('utf-8'))
    with wave.open(filename, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sampwidth)
        wav_file.setframerate(framerate)
        wav_file.writeframes(wav_bytes)
# 示例用法

app = Flask("First Web")


@app.route('/', methods=['GET', "POST"])
def handler():
    if request.method == 'GET':

        example_info = json.dumps({
            'channels': 1,
            'sample_rate': 16000,
            'width': 2,
            'bytes_base64': "[wav bytes]"
        }, indent=4)
        msg = "[System]You need to Post data as json with channels,sample_rate,width,bytes_base64."
        msg += '\nExample :\n'
        msg += example_info
        return msg

    elif request.method == 'POST':
        # msg ="ok"
        # return msg
        rawData = request.get_json()
        channels = rawData["channels"]
        sample_rate = rawData["sample_rate"]
        width = rawData["width"]
        wav_bytes=rawData["bytes_base64"]
        file_name = f"C:/Users/周佳/Desktop/Audio_Data/{output_filename}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.wav"
        save_wav_from_base64(wav_bytes,file_name,channels,width,sample_rate)
        mac=rawData["identifier"]
        print(f"the score is {IsViloent(file_name)}")
        return str(IsViloent(file_name))



if __name__ == "__main__":
    import waitress  # 构建Web服务器
    #app.run(host='0.0.0.0')
    waitress.serve(app, port="5000")


#
