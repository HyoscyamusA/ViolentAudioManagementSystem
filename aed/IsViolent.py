import numpy as np
import tensorflow as tf
import os
import joblib

from . import vggish_input
from . import vggish_params
from . import vggish_postprocess
from . import vggish_slim

tf.compat.v1.disable_eager_execution()

# 定义输入音频文件路径
audio_file = "...."

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


# ubm = joblib.load(os.path.join(path_model, 'ubm.model'))

bad = ['Speech', 'Male speech, man speaking', 'Female speech, woman speaking', 'Child speech, kid speaking', 'Conversation', 'Narration, monologue', 'Babbling', 'Whispering', 'Laughter', 'Baby laughter', 'Giggle', 'Snicker', 'Belly laugh', 'Chuckle, chortle', 'Baby cry, infant cry', 'Singing', 'Choir', 'Yodeling', 'Chant', 'Mantra', 'Male singing', 'Female singing', 'Child singing', 'Synthetic singing', 'Rapping', 'Whistling', 'Breathing', 'Wheeze', 'Snoring', 'Gasp', 'Pant', 'Snort', 'Cough', 'Throat clearing', 'Sneeze', 'Sniff', 'Run', 'Walk, footsteps', 'Chewing, mastication', 'Gargling', 'Burping, eructation', 'Hiccup', 'Fart', 'Hands', 'Finger snapping', 'Clapping', 'Cheering', 'Applause', 'Chatter', 'Crowd', 'Hubbub, speech noise, speech babble', 'Children playing']
good = ['Crying, sobbing', 'Shout', 'Bellow', 'Whoop', 'Yell', 'Battle cry', 'Children shouting', 'Screaming', 'Whimper', 'Wail, moan', 'Sigh', 'Groan', 'Squeal']

data = postprocessed_batch
np.set_printoptions(threshold=1e6)
print(data)
# gmm1 = joblib.load(os.path.join(path_model, 'good1024.model'))
# gmm2 = joblib.load(os.path.join(path_model, 'bad1024.model'))
gmm1 = joblib.load(os.path.join('zhenglei.model'))
gmm2 = joblib.load(os.path.join('fulei.model'))
# score = getscore(ubm, gmm, data)
# print(list(data))
b = gmm2.score(data)
a = gmm1.score(data)
print(a, b)
if a>b:
    print('暴力')
else:
    print('非暴力')