import logging

logging.basicConfig(level=logging.ERROR)
import tensorflow as tf
import vggish_input
import vggish_params
import vggish_postprocess
import vggish_slim
import joblib

tf.compat.v1.disable_eager_execution()
import os
import math
import warnings

warnings.filterwarnings("ignore")

# 加载VGGish模型和预训练的权重
tf.compat.v1.reset_default_graph()
sess = tf.compat.v1.Session()
vggish_slim.define_vggish_slim(training=False)
vggish_slim.load_vggish_slim_checkpoint(sess, "vggish_model.ckpt")

# 设置音频特征提取参数
params = vggish_params.EXAMPLE_HOP_SECONDS
input_tensor = sess.graph.get_tensor_by_name(vggish_params.INPUT_TENSOR_NAME)
output_tensor = sess.graph.get_tensor_by_name(vggish_params.OUTPUT_TENSOR_NAME)


def IsViolent(audio_file):
    """
    使用GMM模型预测音频文件是否为暴力事件，返回暴力和非暴力事件的概率。
    """
    # 读取音频文件并进行特征提取
    examples_batch = vggish_input.wavfile_to_examples(audio_file)
    features_tensor = sess.run(output_tensor, feed_dict={input_tensor: examples_batch})

    # 后处理提取的特征
    pproc = vggish_postprocess.Postprocessor("vggish_pca_params.npz")
    postprocessed_batch = pproc.postprocess(features_tensor)

    # 提取处理后的特征数据
    data = postprocessed_batch

    # 加载两个GMM模型（暴力和非暴力事件的模型）
    gmm1 = joblib.load(os.path.join('Model/fulei.model'))  # 暴力事件的GMM模型
    gmm2 = joblib.load(os.path.join('Model/zhenglei.model'))  # 非暴力事件的GMM模型

    # 使用GMM模型计算得分
    score_violent = gmm1.score(data)  # 暴力事件的得分
    score_non_violent = gmm2.score(data)  # 非暴力事件的得分

    # 计算softmax以归一化两者的得分为概率
    max_val = max(score_violent, score_non_violent)
    prob_violent = (math.exp(score_violent - max_val)) / (
                math.exp(score_violent - max_val) + math.exp(score_non_violent - max_val))
    prob_non_violent = (math.exp(score_non_violent - max_val)) / (
                math.exp(score_violent - max_val) + math.exp(score_non_violent - max_val))

    # 返回暴力和非暴力事件的概率
    return prob_violent, prob_non_violent


# 测试函数
violent_prob, non_violent_prob = IsViolent('test.wav')
print(f'暴力事件概率是 {violent_prob}')
print(f'非暴力事件概率是 {non_violent_prob}')
