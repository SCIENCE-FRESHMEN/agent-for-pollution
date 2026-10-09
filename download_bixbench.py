import os
from huggingface_hub import snapshot_download

# ========== 国内镜像配置（核心，放在最前面） ==========
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

# 数据集仓库ID
repo_id = "futurehouse/BixBench"
# 本地保存目录，可自行修改
local_dir = "./BixBench"

print(f"开始使用hf-mirror镜像下载数据集：{repo_id}")
print(f"文件将保存到：{os.path.abspath(local_dir)}")

# 下载整个仓库，断点续传，不生成软链接
snapshot_download(
    repo_id=repo_id,
    repo_type="dataset",  # 指定是数据集仓库，不是模型
    local_dir=local_dir,
    local_dir_use_symlinks=False,  # 直接下载实体文件，不使用软链接
    resume_download=True,  # ✅ 断点续传，中断后再次运行脚本继续下载
    max_workers=8, # 并发下载线程，可根据网络调整
)

print("✅ 数据集下载完成！")
