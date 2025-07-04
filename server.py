from flask import Flask, request, jsonify
import os
import numpy as np
import tensorflow.compat.v1 as tf
import vggish_input
import vggish_params
import vggish_postprocess
import vggish_slim
import resampy
import joblib

app = Flask(__name__)

def IsViolent(audio_file):
    # 加载VGGish模型和预训练的权重
    tf.compat.v1.reset_default_graph()
    sess = tf.compat.v1.Session()
    vggish_slim.define_vggish_slim(training=False)
    vggish_slim.load_vggish_slim_checkpoint(sess, "vggish_model.ckpt")

    # 设置音频特征提取参数
    input_tensor = sess.graph.get_tensor_by_name(vggish_params.INPUT_TENSOR_NAME)
    output_tensor = sess.graph.get_tensor_by_name(vggish_params.OUTPUT_TENSOR_NAME)

    # 读取音频文件并进行特征提取
    examples_batch = vggish_input.wavfile_to_examples(audio_file)
    features_tensor = sess.run(output_tensor, feed_dict={input_tensor: examples_batch})

    # 后处理提取的特征
    pproc = vggish_postprocess.Postprocessor("vggish_pca_params.npz")
    postprocessed_batch = pproc.postprocess(features_tensor)

    # 加载GMM模型
    gmm1 = joblib.load('Model/fulei.model')
    gmm2 = joblib.load('Model/zhenglei.model')

    b = gmm2.score(postprocessed_batch)
    a = gmm1.score(postprocessed_batch)
    max_val = max(a, b)
    sma = (np.exp(a - max_val)) / ((np.exp(a - max_val) + np.exp(b - max_val)))  # 暴力概率
    return sma

@app.route('/process', methods=['POST'])
def process_audio():
    if 'audio' not in request.files:
        return jsonify({'message': 'No audio file provided'}), 400

    audio_file = request.files['audio']
    audio_path = os.path.join('/tmp', audio_file.filename)
    audio_file.save(audio_path)  # 保存临时音频文件

    # 处理音频文件
    probability = IsViolent(audio_path)
    os.remove(audio_path)  # 删除临时文件

    return jsonify({'message': f'暴力概率是 {probability:.4f}'})

if __name__ == '__main__':
    app.run(debug=True)