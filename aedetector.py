import numpy as np
import tensorflow as tf
import os
import joblib
import math
import warnings

from aed import vggish_input
from aed import vggish_params
from aed import vggish_postprocess
from aed import vggish_slim

from utils.console import Console
from utils.common import decode_wav_bytes,read_wav_bytes

warnings.filterwarnings("ignore", category=UserWarning)
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
tf.compat.v1.disable_eager_execution()


MODEL_PATH = "./aed"

class Aed:
    def __init__(self) -> None:
        # 加载VGGish模型和预训练的权重
        console = Console()
        console.log_highlight("Start initializing aed model.")
        tf.compat.v1.reset_default_graph()
        self.sess = tf.compat.v1.Session()
        vggish_slim.define_vggish_slim(training=False)
        
        #vggish_slim.load_vggish_slim_checkpoint(self.sess, os.path.join(MODEL_PATH,"/root/bullyingdectection/aed/vggish_model.ckpt"))
        vggish_slim.load_vggish_slim_checkpoint(self.sess, os.path.join(MODEL_PATH,"vggish_model.ckpt"))


        # 设置音频特征提取参数
        self.params = vggish_params.EXAMPLE_HOP_SECONDS
        self.input_tensor = self.sess.graph.get_tensor_by_name(vggish_params.INPUT_TENSOR_NAME)
        self.output_tensor = self.sess.graph.get_tensor_by_name(vggish_params.OUTPUT_TENSOR_NAME)
        console.log_success("Initialized aed model successfully.")
    
    def __call__(self,wav_bytes:bytes,sample_rate:int,channels:int,width:int) -> float:
        return self.decode(wav_bytes,sample_rate,channels,width)
    
    def  decode(self,wav_bytes:bytes,sample_rate:int,channels:int,width:int) -> float:
        # 读取音频文件并进行特征提取
        wav_data_nd = decode_wav_bytes(wav_bytes,channels,width)
        wav_data_nd = wav_data_nd.T # 转置 适配VGG
        
        wav_data_nd = wav_data_nd / 32768.0

        examples_batch = vggish_input.waveform_to_examples(wav_data_nd,sample_rate)
        features_tensor = self.sess.run(self.output_tensor, feed_dict={self.input_tensor: examples_batch})

        # 后处理提取的特征
        pproc = vggish_postprocess.Postprocessor(os.path.join(MODEL_PATH,"vggish_pca_params.npz"))
        postprocessed_batch = pproc.postprocess(features_tensor)
        
        data = postprocessed_batch
        np.set_printoptions(threshold=1e6)

        gmm1 = joblib.load(os.path.join(MODEL_PATH,'zhenglei.model'))
        gmm2 = joblib.load(os.path.join(MODEL_PATH,'fulei.model'))

        a = gmm1.score(data)
        b = gmm2.score(data)
        
        max_val = max(a,b)

        sma = (math.exp(a-max_val)) / ((math.exp(a-max_val) + math.exp(b-max_val)))# 暴力概率
        return sma
    
if __name__ == '__main__':
    # 测试的时候修改数据所在文件夹
    TEST_DATA_PATH = "./testSoundClips"

    aed = Aed()
    for file_name in os.listdir(TEST_DATA_PATH):
        if file_name.endswith(("mp3","wav","aac")) == False:
            continue
        
        audio_path = os.path.join(TEST_DATA_PATH,file_name)
        str_data, framerate, num_channel, num_sample_width = read_wav_bytes(audio_path)
        res = aed.decode(str_data,framerate,num_channel,num_sample_width)
        print(f"data:{file_name}\nscore:{res}")