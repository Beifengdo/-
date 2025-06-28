# Hugging Face 批量下载软件

### 前言

由于Hugging Face的下载方式过于独特，和GitHub相比来说不支持批量下载。作者尝试搜索国内外相关如何批量下载，这里的实现竟然没有比较美观和合理的设计、于是我做了一个版本，希望能够帮助大家。

### 实现说明

1. 前端

   - **下载路径输入框**：在“仓库管理”部分添加了下载路径输入框，允许用户指定下载目录，默认值从后端配置加载。
   - **真实API调用**：调用后端的/api/tasks接口创建下载任务，并通过轮询/api/tasks/<task_id>获取任务状态。
   - **任务状态轮询**：通过pollTaskStatus函数定期查询任务状态，更新日志和UI状态。
   - **停止下载**：实现停止功能，通过调用/api/tasks/<task_id>/cancel终止下载任务。
   - **配置加载**：在初始化时通过/api/config获取默认下载路径，显示在输入框中。

2. 后端改进

   - **任务状态管理**：后端使用app.config['TASKS']存储任务状态，确保前端可以通过API查询到最新的任务进度和日志。
   - **日志系统**：优化了日志记录，确保每次任务状态更新都会记录到TASKS中，供前端轮询获取。
   - **并发控制**：通过MAX_CONCURRENT_DOWNLOADS限制并发下载数量（当前代码中为顺序下载，实际可通过线程池进一步优化）。
   - **错误处理**：完善了错误处理机制，确保仓库不存在或下载失败时返回清晰的错误信息。

3. 运行环境

   - 依赖安装

     ```cmd
     pip install flask huggingface_hub
     ```

   - 文件结构

     ```
     project/
     |
     ├── templates/
     |   |
     │   └── index.html // 前端界面可视化的部分
     |
     ├── static/
     |   |
     │   └── (静态文件，如CSS/JS，若需要)
     |
     ├── huggingface_downloader.py   //后端支持
     |
     └── huggingface_downloader.log  //过程日志
     ```

   - 运行方式★★★★★

     1. 将index.html保存到templates/目录。

     2. 将huggingface_downloader.py保存到项目根目录。

     3. 运行后端： 

        ```cmd
        python huggingface_downloader.py
        ```

     4. 访问http://localhost:5000查看前端界面。

4. 使用说明

   - 输入Hugging Face仓库ID（格式：用户名/仓库名），如bert-base-uncased。
   - 指定下载路径（默认：./huggingface_downloads）。
   - 点击“添加”将仓库加入列表，支持导入/导出仓库列表。
   - 点击“开始下载”启动下载任务，日志区域实时显示进度。
   - 可随时点击“停止”终止下载任务。

5. 注意事项

   - **Hugging Face API限制**：部分仓库可能需要登录认证，可在后端添加HfApi(token="your_token")支持认证。此处功能会在后续的更新中实现
   - **下载进度**：当前huggingface_hub的snapshot_download不支持原生进度回调，可通过自定义实现（如监控文件大小）增强进度显示。当前暂时不支持前端进度条反馈
   - **并发优化**：当前为顺序下载，若需并发，可使用concurrent.futures.ThreadPoolExecutor重构process_batch_download。

------

### 测试与验证

1. 测试步骤
   - 添加测试仓库，如bert-base-uncased或bigscience/bloom-560m。
   - 启动下载，观察日志输出和状态更新。
   - 验证下载文件是否正确保存到指定目录（如huggingface_downloads/bert-base-uncased）。
   - 测试停止功能，确保任务能正确取消。
   - 测试导入/导出功能，确保仓库列表正确处理。
2. 预期结果
   - 有效仓库成功下载，日志显示“成功下载”。
   - 无效仓库显示“仓库不存在”错误。
   - 下载路径正确创建，文件保存完整。
   - 停止操作后，任务状态更新为“已取消”。

------

### 后续优化计划

1. 前端 
   - 添加进度条显示下载百分比（需后端支持）。
   - 支持批量开始下载（当前为逐个处理）。
   - 添加文件浏览功能，方便选择下载路径。
2. 后端
   - 实现并发下载，使用线程池或异步IO。
   - 添加下载进度回调，监控文件下载大小。
   - 支持Hugging Face API认证，处理私有仓库。
3. 安全性
   - 验证用户输入的下载路径，防止路径穿越攻击。
   - 添加API认证，限制未授权访问。