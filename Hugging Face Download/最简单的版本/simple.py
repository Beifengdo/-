from huggingface_hub import snapshot_download
import os

# 数据集的 repo_id 列表，按需调整格式（用户名/仓库名）
repos = [
    "Ichont/saunfasheji",
    "Ichont/AIGer_Dataset",
    "Ichont/shujujiegou",
    "Ichont/shudian",
    "Ichont/modian",
    "Ichont/caozuoxitong",
    "Ichont/shujuku",
    "Ichont/jisuanjiwangluo"
]  

for repo in repos:
    try:
        snapshot_download(
            repo_id=repo,
            cache_dir="./huggingface_datasets",
            repo_type="dataset",  # 指定为数据集类型
            ignore_patterns=["*.bin", "*.ckpt"]  # 可选：忽略大文件
        )
        print(f"✅ 成功下载: {repo}")
    except Exception as e:
        print(f"❌ 下载失败: {repo} - 错误: {str(e)}")
