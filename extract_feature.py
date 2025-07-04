import os
import numpy as np
import tensorflow as tf
import vggish_input
import vggish_params
import vggish_postprocess
import vggish_slim
import librosa

# 禁用即时执行（eager execution）
tf.compat.v1.disable_eager_execution()

# 重置默认图
tf.compat.v1.reset_default_graph()

# 创建会话
sess = tf.compat.v1.Session()

# 加载VGGish模型和预训练的权重
vggish_slim.define_vggish_slim(training=False)
vggish_slim.load_vggish_slim_checkpoint(sess, "vggish_model.ckpt")

# 设置音频特征提取参数
params = vggish_params.EXAMPLE_HOP_SECONDS
input_tensor = sess.graph.get_tensor_by_name(vggish_params.INPUT_TENSOR_NAME)
output_tensor = sess.graph.get_tensor_by_name(vggish_params.OUTPUT_TENSOR_NAME)

# 后处理提取的特征
pproc = vggish_postprocess.Postprocessor("vggish_pca_params.npz") 
# 该目录下的所有文件夹里文件都会被提取，且保留该目录下的文件夹名
main_audio_folder = r"D:\ESC数据集\ESC-US-04\ESC-US"

# 保存在该目录下,不需要手动创建标签文件夹，直接自动建立
feature_folder = r"D:\ESC数据集\Feature\ECS-US-Feature"

# 遍历文件夹中的音频数据
for root, dirs, files in os.walk(main_audio_folder):
    for sub_dir in dirs:
        sub_audio_folder = os.path.join(root, sub_dir)  # 子文件夹路径
        feature_sub_folder = os.path.join(feature_folder, sub_dir)  # 对应的特征保存文件夹路径
        if not os.path.exists(feature_sub_folder):
            os.makedirs(feature_sub_folder)  # 如果文件夹不存在，则创建文件夹

        # 遍历子文件夹中的音频数据
        for audio_file in os.listdir(sub_audio_folder):
            if audio_file.endswith(".ogg"):  # 确保是.ogg文件
                audio_path = os.path.join(sub_audio_folder, audio_file)

                # 读取音频文件并进行特征提取
                y, sr = librosa.load(audio_path, sr=44100)  # 以44.1k采样率读取音频文件
                examples_batch = vggish_input.waveform_to_examples(y, sr)  # 提取音频特征
                features_tensor = sess.run(output_tensor, feed_dict={input_tensor: examples_batch})

                # 后处理提取的特征
                postprocessed_batch = pproc.postprocess(features_tensor)

                # 保存特征为npy文件，使用原文件名作为特征文件名
                feature_file_name = os.path.splitext(audio_file)[0] + ".npy"
                feature_file_path = os.path.join(feature_sub_folder, feature_file_name)  # 保存特征的文件路径
                np.save(feature_file_path, postprocessed_batch)