from flask import Flask, request, jsonify
import os
from flask_cors import CORS
from inference_demo import IsViolent  # 引用你的GMM模型预测函数

app = Flask(__name__)
CORS(app)  # 启用跨域支持，以允许不同域的前端请求访问

# 配置上传文件夹
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')  # 设置上传文件夹的路径
if not os.path.exists(UPLOAD_FOLDER):  # 如果文件夹不存在，则创建该文件夹
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER  # 将上传文件夹路径存储在应用配置中


@app.route('/upload', methods=['POST'])
def upload_file():
    # 检查请求中是否包含文件
    if 'file' not in request.files:
        return jsonify({'message': '未检测到文件'}), 400  # 如果没有文件，返回错误信息

    file = request.files['file']  # 获取上传的文件

    # 检查文件名是否为空
    if file.filename == '':
        return jsonify({'message': '未选择任何文件'}), 400  # 如果文件名为空，返回错误信息

    # 检查文件格式是否为.wav
    if not file.filename.endswith('.wav'):
        return jsonify({'message': '仅支持WAV格式文件'}), 400  # 如果文件不是.wav格式，返回错误信息

    try:
        # 保存上传的音频文件到指定文件夹
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)  # 设置文件保存路径
        file.save(filepath)  # 保存文件

        # 使用 IsViolent 函数处理文件并预测
        # 这里的 IsViolent 函数应该返回暴力和非暴力事件的概率
        violent_probability, non_violent_probability = IsViolent(filepath)

        # 在服务器日志中打印预测结果以供调试
        print(f"暴力概率：{violent_probability}, 非暴力概率：{non_violent_probability}")

        # 返回预测结果
        return jsonify({
            'violent_probability': violent_probability,  # 返回暴力事件的概率
            'non_violent_probability': non_violent_probability  # 返回非暴力事件的概率
        }), 200  # 返回200表示请求成功，并附带预测结果

    except Exception as e:
        # 如果发生任何异常，捕获并返回错误信息
        print(f"发生错误：{str(e)}")  # 打印错误信息
        return jsonify({'message': f'服务器内部错误：{str(e)}'}), 500  # 返回500表示服务器错误，并附带异常信息


# 启动Flask应用
if __name__ == '__main__':
    app.run(debug=True)  # 启动Flask服务器，开启调试模式
