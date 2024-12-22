from numbers import Number

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
from dotenv import load_dotenv
import sqlite3
import json
import base64
import hmac
import hashlib
import time


# 加载环境变量文件（如果有）
load_dotenv()

try:
    OSS_ACCESS_KEY_ID = os.environ['OSS_ACCESS_KEY_ID']
    OSS_ACCESS_KEY_SECRET = os.environ['OSS_ACCESS_KEY_SECRET']
    OSS_BUCKET_NAME = os.environ.get('OSS_BUCKET_NAME')
    OSS_ENDPOINT = os.environ.get('OSS_ENDPOINT')
    DATABASE = os.environ.get('DATABASE')
except KeyError as e:
    raise EnvironmentError(f"Environment variable {e.args[0]} is not set.")


# Create application
app = Flask(__name__)
CORS(app)

# Helper functions

def init_db():
    with sqlite3.connect(DATABASE) as conn:
        with open('assignment_upload_db.sql', 'r') as f:
            conn.executescript(f.read())


# Routes
# Routes
@app.route('/upload', methods=['POST'])
def upload_assignment():
    data = request.form


    group_id = data.get('group_id')
    video_title = data.get('video_title')
    video = data.getlist('video')
    report = data.getlist('report')
    script=data.getlist('script')
    screenshot=data.getlist('screenshot')
    recording=data.getlist('recording')


    # Validate group ID and video title
    if not group_id or not video_title:
        return jsonify({'data': 'Group ID and video title are required','success':False}), 200

    # Save to database
    with sqlite3.connect(DATABASE) as conn:
        try:
            conn.execute(
                """INSERT INTO Assignments (group_id, video_title, video_file, project_report, script_file, screenshots, recording_file)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    group_id, video_title,
                    ', '.join(video),
                    ', '.join(report),
                    ', '.join(script),
                    ', '.join(screenshot),
                    ', '.join(recording)
                )
            )
            conn.commit()
        except sqlite3.IntegrityError:
            return jsonify({'data': 'This group has already uploaded an assignment','success':False}), 200

    return jsonify({'data': 'Upload successful','success':True}), 200


@app.route('/assignments/<int:class_id>', methods=['GET'])
def list_assignments(class_id):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT a.id, group_id, video_title,video_file,g.name as group_name,c.name as class_name FROM Assignments AS a JOIN (SELECT id,name,class_id FROM `Groups`) AS g JOIN (SELECT * FROM Classes) AS c ON a.group_id=g.id AND g.class_id=c.id WHERE c.id=?", (class_id,))
        assignments = cursor.fetchall()

    # 将结果转换为字典列表
    assignment_list = [{"id": row[0], "group_id": row[1], "video_title": row[2],"video_file": row[3],"group_name":row[4],"class_name":row[5]} for row in assignments]

    return jsonify(assignment_list), 200


@app.route('/classes', methods=['GET'])
def list_classes():
    try:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name FROM Classes")
            classes = cursor.fetchall()

        # 将结果转换为字典列表
        class_list = [{"id": row[0], "name": row[1]} for row in classes]

        return jsonify(class_list), 200

    except sqlite3.Error as e:
        # 处理数据库相关异常
        return jsonify({"error": "Database error", "data": str(e),'success':False}), 200
    except Exception as e:
        # 处理其他异常
        return jsonify({"error": "An unexpected error occurred", "data": str(e),'success':False}), 200


@app.route('/groups/<int:class_id>', methods=['GET'])
def list_groups(class_id):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM Groups WHERE class_id = ?", (class_id,))
        groups = cursor.fetchall()

    # 将结果转换为字典列表
    group_list = [{"id": row[0], "name": row[1]} for row in groups]

    return jsonify(group_list), 200

@app.route('/is_uploaded/<int:group_id>', methods=['GET'])
def is_uploaded(group_id):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count(1) FROM Assignments WHERE group_id = ?", (group_id,))
        record_count = cursor.fetchone()
        if record_count[0] > 0:
            return jsonify({'data': 'Group has already uploaded an assignment','success':False}), 200
        else:
            return jsonify({'data': 'Group has not uploaded an assignment','success':True}), 200



@app.route('/grade', methods=['POST'])
def grade_assignment():
    data = request.form
    assignment_id = data.get('assignment_id')
    language_score = data.get('languageScore')
    technical_score = data.get('technicalScore')
    creativity_score = data.get('creativityScore')
    teamwork_score = data.get('teamworkScore')

    if not assignment_id or not language_score or not teamwork_score or not technical_score or not creativity_score:
        return jsonify({'data': 'Invalid data provided','success':False}), 200
    language_score = float(language_score)
    teamwork_score = float(teamwork_score)
    creativity_score = float(creativity_score)
    technical_score = float(technical_score)

    if language_score < 0 or language_score > 30:
        return jsonify({'data': 'Invalid language score provided','success':False}), 200
    if technical_score < 0 or technical_score > 30:
        return jsonify({'data': 'Invalid technical score provided','success':False}), 200
    if creativity_score < 0 or creativity_score > 20:
        return jsonify({'data': 'Invalid creativity score provided','success':False}), 200
    if teamwork_score < 0 or teamwork_score > 20:
        return jsonify({'data': 'Invalid teamwork score provided','success':False}), 200

    with sqlite3.connect(DATABASE) as conn:
        conn.execute(
            """INSERT INTO Grades (assignment_id, language_score, technical_score, creativity_score, teamwork_score)
            VALUES (?, ?, ?, ?, ?)""",
            (
                assignment_id,
                language_score,
                technical_score,
                creativity_score,
                teamwork_score
            )
        )
        conn.commit()

    return jsonify({'data': 'Grade submitted successfully','success':True}), 200

@app.route('/get_current_avg_score/<int:assignment_id>', methods=['GET'])
def get_current_avg_score(assignment_id):
    #get all score records from database by assignment_id
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT language_score, technical_score, creativity_score, teamwork_score FROM Grades WHERE assignment_id = ?", (assignment_id,))
        scores = cursor.fetchall()
        # iterate all records,calculate total_score by add language_score,technical_score,creativity_score,teamwork_score.then calculate the average for total_score
        total_score = sum([sum(score) for score in scores])
        avg_score = total_score / len(scores)
        return str(avg_score)


# 生成上传签名
def generate_oss_signature():
    expiration_time = 1200  # 签名过期时间，单位秒
    expiration = int(time.time()) + expiration_time  # 设置过期时间
    expiration = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(expiration))

    # 定义上传策略
    policy = {
        "expiration": expiration,
        "conditions": [
            {"bucket": OSS_BUCKET_NAME},
            ["content-length-range", 0, 10485760000],  # 设置文件大小限制，最大 10 GB
            ["in", "$Content-Type", ["application/pdf","image/jpeg","image/png","application/msword","application/vnd.openxmlformats-officedocument.wordprocessingml.document","video/mp4"]],
        ]
    }

    # 将 policy 转换为 Base64 编码
    policy_str = json.dumps(policy)
    policy_base64 = base64.b64encode(policy_str.encode('utf-8')).decode('utf-8')

    # 使用阿里云的 AccessKeySecret 对 policy 进行签名
    signature = base64.b64encode(hmac.new(
        OSS_ACCESS_KEY_SECRET.encode('utf-8'),
        policy_base64.encode('utf-8'),
        hashlib.sha1
    ).digest()).decode('utf-8')

    return {
        "accessKeyId": OSS_ACCESS_KEY_ID,
        "policy": policy_base64,
        "signature": signature,
        "expiration": expiration
    }

@app.route('/generate-oss-signature', methods=['GET'])
def get_oss_signature():
    signature = generate_oss_signature()
    return jsonify(signature)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
