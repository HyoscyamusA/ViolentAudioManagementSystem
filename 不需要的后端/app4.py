from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from datetime import datetime
from inference_demo import IsViolent
from database import init_db, insert_record, get_daily_records, get_heatmap_data

app = Flask(__name__)
CORS(app)  # 启用跨域支持

# 配置上传文件夹
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 初始化数据库
init_db()

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'message': '未检测到文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'message': '未选择任何文件'}), 400

    if not file.filename.endswith('.wav'):
        return jsonify({'message': '仅支持WAV格式文件'}), 400

    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)

        violent_probability, non_violent_probability = IsViolent(filepath)
        device_id = request.form.get('device_id', 'default_device')

        # 将数据插入数据库
        insert_record(file.filename, violent_probability, non_violent_probability, device_id)

        return jsonify({
            'violent_probability': violent_probability,
            'non_violent_probability': non_violent_probability
        }), 200

    except Exception as e:
        return jsonify({'message': f'服务器错误: {str(e)}'}), 500

@app.route('/api/records', methods=['GET'])
def get_records():
    records = get_daily_records()
    return jsonify(records)

@app.route('/api/heatmap', methods=['GET'])
def get_heatmap():
    data = get_heatmap_data()
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True)
