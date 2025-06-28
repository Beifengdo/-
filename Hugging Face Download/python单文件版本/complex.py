import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from huggingface_hub import snapshot_download, HfApi
import asyncio
import threading
import os
from queue import Queue
import logging
from datetime import datetime
import sys
import io
import re

# 配置日志，强制使用 UTF-8 编码
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class StreamToText(io.StringIO):
    """将标准输出重定向到 tkinter 文本框"""
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def write(self, message):
        self.text_widget.config(state='normal')
        self.text_widget.insert(tk.END, message)
        self.text_widget.see(tk.END)
        self.text_widget.config(state='disabled')

    def flush(self):
        pass

class HuggingFaceDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Hugging Face 批量下载工具")
        self.root.geometry("1000x600")
        self.api = HfApi()
        self.download_queue = Queue()
        self.is_downloading = False
        self.stop_download = False
        
        self.setup_ui()
        self.setup_logging()

    def setup_logging(self):
        """配置日志，使用 UTF-8 编码"""
        self.log_file = f"download_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)

    def setup_ui(self):
        """设置用户界面，添加侧栏显示下载过程"""
        main_frame = tk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 左侧控制面板
        control_frame = tk.Frame(main_frame)
        main_frame.add(control_frame, minsize=300)

        tk.Label(control_frame, text="仓库列表 (每行一个, 格式: 用户名/仓库名):").pack(pady=5)
        self.repo_text = tk.Text(control_frame, height=5, width=40)
        self.repo_text.pack(pady=5)

        # 目录选择
        dir_frame = tk.Frame(control_frame)
        dir_frame.pack(fill=tk.X, padx=5)
        tk.Label(dir_frame, text="下载目录:").pack(side=tk.LEFT)
        self.dir_entry = tk.Entry(dir_frame)
        self.dir_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        self.dir_entry.insert(0, os.path.abspath("./huggingface_data"))
        tk.Button(dir_frame, text="浏览", command=self.choose_directory).pack(side=tk.RIGHT)

        # 控制按钮
        button_frame = tk.Frame(control_frame)
        button_frame.pack(pady=10)
        tk.Button(button_frame, text="开始下载", command=self.start_download).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="暂停下载", command=self.pause_download).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="清空列表", command=self.clear_list).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="查看日志", command=self.view_log).pack(side=tk.LEFT, padx=5)

        # 进度条
        self.progress = ttk.Progressbar(control_frame, length=250, mode='determinate')
        self.progress.pack(pady=10)

        # 右侧日志显示
        log_frame = tk.Frame(main_frame)
        main_frame.add(log_frame, minsize=400)
        tk.Label(log_frame, text="下载日志:").pack(pady=5)
        self.status_text = tk.Text(log_frame, height=20, width=60)
        self.status_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.status_text.config(state='disabled')

        # 重定向标准输出到日志显示
        sys.stdout = StreamToText(self.status_text)

    def choose_directory(self):
        """选择下载目录"""
        directory = filedialog.askdirectory()
        if directory:
            self.dir_entry.delete(0, tk.END)
            self.dir_entry.insert(0, directory)

    def clear_list(self):
        """清空仓库列表"""
        self.repo_text.delete(1.0, tk.END)
        self.update_status("已清空仓库列表\n")

    def view_log(self):
        """查看日志文件"""
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                messagebox.showinfo("下载日志", f.read())
        except Exception as e:
            messagebox.showerror("错误", f"无法打开日志文件: {str(e)}")

    def pause_download(self):
        """暂停或恢复下载"""
        if self.is_downloading:
            self.stop_download = True
            self.update_status("暂停下载任务...\n")
            self.is_downloading = False

    def update_status(self, message):
        """更新状态显示"""
        self.status_text.config(state='normal')
        self.status_text.insert(tk.END, message)
        self.status_text.see(tk.END)
        self.status_text.config(state='disabled')
        logger.info(message.strip().replace('✅', '成功').replace('❌', '失败'))

    async def detect_repo_type(self, repo_id):
        """异步检测仓库类型"""
        try:
            await asyncio.to_thread(self.api.dataset_info, repo_id)
            return "dataset"
        except Exception:
            try:
                await asyncio.to_thread(self.api.model_info, repo_id)
                return "model"
            except Exception:
                return None

    async def download_repo(self, repo_id, cache_dir):
        """异步下载单个仓库"""
        repo_type = await self.detect_repo_type(repo_id)
        
        if repo_type is None:
            return False, f"仓库 {repo_id} 不存在或无法访问"

        try:
            self.update_status(f"开始下载 {repo_id} ({repo_type})...\n")
            await asyncio.to_thread(
                snapshot_download,
                repo_id=repo_id,
                cache_dir=cache_dir,
                repo_type=repo_type,
                resume_download=True,
                local_dir_use_symlinks=False
            )
            return True, f"成功下载 {repo_id} ({repo_type})"
        except Exception as e:
            return False, f"仓库 {repo_id} 下载失败: {str(e)}"

    async def batch_download(self, repos, cache_dir):
        """异步批量下载"""
        os.makedirs(cache_dir, exist_ok=True)
        successes = []
        failures = []
        total = len(repos)
        
        self.progress['maximum'] = total
        self.progress['value'] = 0

        for i, repo_id in enumerate(repos):
            if self.stop_download:
                self.update_status("下载任务已暂停\n")
                break
                
            self.update_status(f"\n处理仓库 {i+1}/{total}: {repo_id}\n")
            success, message = await self.download_repo(repo_id, cache_dir)
            
            if success:
                successes.append(message)
                self.update_status(f"成功 {message}\n")
            else:
                failures.append(message)
                self.update_status(f"失败 {message}\n")
            
            self.progress['value'] = i + 1
            self.root.update()
            await asyncio.sleep(0.5)  # 避免 API 请求过快

        # 显示总结
        summary = f"\n===== 下载结果汇总 =====\n"
        summary += f"成功: {len(successes)}\n"
        for msg in successes:
            summary += f"  - {msg}\n"
        summary += f"\n失败: {len(failures)}\n"
        for msg in failures:
            summary += f"  - {msg}\n"
        
        self.update_status(summary)
        self.is_downloading = False
        self.stop_download = False

    def start_download(self):
        """开始下载任务"""
        if self.is_downloading:
            messagebox.showinfo("提示", "下载任务正在进行中！")
            return

        repos = [r.strip() for r in self.repo_text.get(1.0, tk.END).split('\n') if r.strip()]
        if not repos:
            messagebox.showerror("错误", "请至少输入一个仓库 ID！")
            return

        # 验证仓库 ID 格式
        valid_repos = []
        for repo in repos:
            if not re.match(r'^[\w-]+/[\w-]+$', repo):
                self.update_status(f"无效的仓库 ID 格式: {repo}，应为 用户名/仓库名\n")
            else:
                valid_repos.append(repo)
        
        if not valid_repos:
            messagebox.showerror("错误", "没有有效的仓库 ID！")
            return

        cache_dir = self.dir_entry.get()
        if not cache_dir:
            messagebox.showerror("错误", "请选择下载目录！")
            return

        self.is_downloading = True
        self.stop_download = False
        self.update_status(f"目标目录: {os.path.abspath(cache_dir)}\n待下载仓库: {len(valid_repos)}\n\n")

        # 在新线程中运行异步下载
        def run_async_download():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.batch_download(valid_repos, cache_dir))
            loop.close()

        threading.Thread(target=run_async_download, daemon=True).start()

    def run(self):
        """运行应用"""
        self.root.mainloop()

if __name__ == "__main__":
    # 设置环境变量以禁用符号链接警告
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "true"
    root = tk.Tk()
    app = HuggingFaceDownloaderApp(root)
    app.run()