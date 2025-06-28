from flask import Flask, request, jsonify, render_template
from huggingface_hub import snapshot_download, HfApi
from threading import Thread
import os
import time
import json
import uuid
import logging

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['DOWNLOAD_DIR'] = os.path.join(os.getcwd(), 'huggingface_downloads')
app.config['TASKS'] = {}  # 存储任务状态
app.config['MAX_CONCURRENT_DOWNLOADS'] = 3  # 最大并发下载数

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("huggingface_downloader.log"), logging.StreamHandler()]
)
logger = logging.getLogger("HuggingFaceDownloader")

def detect_repo_type(repo_id):
    """检测仓库类型（dataset或model）"""
    api = HfApi()
    try:
        api.dataset_info(repo_id)
        return "dataset"
    except:
        try:
            api.model_info(repo_id)
            return "model"
        except:
            return None

def download_repo(task_id, repo_id, download_dir, progress_callback):
    """下载单个仓库"""
    try:
        progress_callback(task_id, "detecting", f"检测仓库类型: {repo_id}")
        repo_type = detect_repo_type(repo_id)
        if not repo_type:
            progress_callback(task_id, "failed", f"仓库不存在: {repo_id}")
            return False, f"仓库不存在或无法访问: {repo_id}"
        
        progress_callback(task_id, "downloading", f"开始下载 {repo_id} ({repo_type})")
        logger.info(f"开始下载 {repo_id} ({repo_type})")
        
        repo_download_dir = os.path.join(download_dir, repo_id.replace('/', '_'))
        os.makedirs(repo_download_dir, exist_ok=True)
        
        snapshot_download(
            repo_id=repo_id,
            cache_dir=repo_download_dir,
            repo_type=repo_type,
            resume_download=True
        )
        
        progress_callback(task_id, "completed", f"成功下载: {repo_id}")
        logger.info(f"成功下载: {repo_id}")
        return True, f"成功下载: {repo_id}"
    except Exception as e:
        error_msg = f"下载失败: {str(e)}"
        progress_callback(task_id, "failed", error_msg)
        logger.error(error_msg)
        return False, error_msg

def process_batch_download(task_id, repos, download_dir):
    """批量处理下载任务"""
    app.config['TASKS'][task_id] = {
        "status": "processing",
        "total": len(repos),
        "completed": 0,
        "failed": 0,
        "repos": repos,
        "start_time": time.time(),
        "logs": []
    }
    
    task = app.config['TASKS'][task_id]
    
    for i, repo in enumerate(repos):
        if task["status"] == "cancelled":
            task["status"] = "cancelled"
            break
            
        task["current_repo"] = repo
        task["current_index"] = i
        
        success, message = download_repo(
            task_id, 
            repo, 
            download_dir, 
            lambda t_id, status, msg: update_task_status(t_id, status, msg)
        )
        
        if success:
            task["completed"] += 1
        else:
            task["failed"] += 1
            
        task["logs"].append({
            "time": time.strftime("%H:%M:%S"),
            "repo": repo,
            "status": "success" if success else "failed",
            "message": message
        })
        
        update_task_status(task_id, task["status"], f"处理进度: {i+1}/{len(repos)}")
        time.sleep(0.5)
    
    task["status"] = "completed"
    task["end_time"] = time.time()
    task["elapsed_time"] = task["end_time"] - task["start_time"]

def update_task_status(task_id, status, message):
    """更新任务状态"""
    if task_id in app.config['TASKS']:
        app.config['TASKS'][task_id]["status"] = status
        app.config['TASKS'][task_id]["current_message"] = message
        app.config['TASKS'][task_id]["logs"].append({
            "time": time.strftime("%H:%M:%S"),
            "status": status,
            "message": message
        })

@app.route('/')
def index():
    """渲染前端界面"""
    return render_template('index.html')

@app.route('/api/tasks', methods=['POST'])
def create_task():
    """创建新的下载任务"""
    data = request.json
    repos = data.get('repos', [])
    download_dir = data.get('download_dir', app.config['DOWNLOAD_DIR'])
    
    if not repos:
        return jsonify({"error": "没有提供仓库列表"}), 400
    
    task_id = str(uuid.uuid4())
    os.makedirs(download_dir, exist_ok=True)
    
    thread = Thread(
        target=process_batch_download,
        args=(task_id, repos, download_dir)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({
        "task_id": task_id,
        "status": "pending",
        "message": "任务已创建，正在准备下载"
    })

@app.route('/api/tasks/<task_id>', methods=['GET'])
def get_task(task_id):
    """获取任务状态"""
    task = app.config['TASKS'].get(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    
    return jsonify(task)

@app.route('/api/tasks/<task_id>/cancel', methods=['POST'])
def cancel_task(task_id):
    """取消任务"""
    task = app.config['TASKS'].get(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    
    task["status"] = "cancelled"
    return jsonify({"status": "cancelled", "message": "任务已取消"})

@app.route('/api/config', methods=['GET'])
def get_config():
    """获取配置信息"""
    return jsonify({
        "download_dir": app.config['DOWNLOAD_DIR'],
        "max_concurrent_downloads": app.config['MAX_CONCURRENT_DOWNLOADS']
    })

@app.route('/api/config', methods=['POST'])
def update_config():
    """更新配置信息"""
    data = request.json
    download_dir = data.get('download_dir')
    
    if download_dir:
        app.config['DOWNLOAD_DIR'] = download_dir
        os.makedirs(download_dir, exist_ok=True)
    
    return jsonify({
        "download_dir": app.config['DOWNLOAD_DIR'],
        "message": "配置已更新"
    })

if __name__ == '__main__':
    os.makedirs(os.path.join(os.getcwd(), 'templates'), exist_ok=True)
    os.makedirs(os.path.join(os.getcwd(), 'static'), exist_ok=True)
    
    logger.info("Hugging Face 下载服务启动")
    app.run(host='0.0.0.0', port=5000, debug=True)