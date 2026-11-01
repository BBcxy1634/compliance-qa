# D12 复现与环境说明

## 环境要求

- Windows PowerShell
- Python 3.12 或更高版本，推荐 Python 3.13
- 克隆后的 `compliance-qa` 项目根目录
- DeepSeek API Key
- CPU 模式建议至少 8 GB 可用内存
- B3 GPU 模式建议至少 8 GB 显存

## 首次配置

在克隆后的项目根目录执行：

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

在 `.env` 中填写真实的 `DEEPSEEK_API_KEY`。不要提交 `.env`。

## 默认 B1 Fast 复现

```powershell
python scripts/bootstrap.py
python scripts/check_environment.py --require-data
python -m src.rag "eBay 是否允许销售假冒商品？" --mode deepseek --no-thinking --max-tokens 600
```

`bootstrap.py` 会：

1. 检查官方 HTML/PDF，缺失时重新抓取。
2. 生成语义切分和 B0 固定切分。
3. 检查 271 条语义向量库，不存在或数量不符时重建。
4. 运行来源与评测集结构校验。
5. 运行环境自检。

## 完整 B0-B3 复现

```powershell
python scripts/bootstrap.py --full --with-reranker
```

该命令额外建立 334 条 B0 向量库，并下载 B3 reranker。随后可以运行：

```powershell
python evaluate.py --config eval/configs/b0_deepseek.yaml --chunks data/processed/chunks_b0.jsonl
python evaluate.py --config eval/configs/b1_deepseek.yaml --chunks data/processed/chunks.jsonl
python evaluate.py --config eval/configs/b2_deepseek.yaml --chunks data/processed/chunks.jsonl
python evaluate.py --config eval/configs/b3_deepseek.yaml --chunks data/processed/chunks.jsonl
```

更新汇总表：

```powershell
python scripts/build_baseline_table.py `
  --run "B0=eval/results/b0_deepseek/summary.json" `
  --run "B1=eval/results/b1_deepseek/summary.json" `
  --run "B2=eval/results/b2_deepseek/summary.json" `
  --run "B3=eval/results/b3_deepseek/summary.json"

python scripts/analyze_ablation.py
```

## CPU 模式

`.env`：

```dotenv
TORCH_DEVICE=auto
```

没有 CUDA 时会自动回退 CPU。也可以显式设置：

```dotenv
TORCH_DEVICE=cpu
```

## GPU 模式

当前依赖中的 PyTorch 是 CPU 版。GPU 机器需要安装匹配驱动的 CUDA 版 PyTorch，具体命令以 PyTorch 官方安装选择器为准。

`.env`：

```dotenv
TORCH_DEVICE=auto
```

或强制使用 CUDA：

```dotenv
TORCH_DEVICE=cuda
```

验证：

```powershell
python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
python scripts/check_environment.py --require-data
```

显存建议：

- 8 GB：B1 Fast 足够，B3 可能较紧。
- 12 GB 及以上：适合同时加载 BGE-M3 和 reranker。
- 如果显存不足，可以把 embedding 与 reranker 分开运行，或使用更小的 reranker。

GPU 只加速本地向量模型和 CrossEncoder，不加速 DeepSeek 网络调用。B3 的 DeepSeek 生成仍受网络和模型服务影响。

## 100 次压测复现

```powershell
python bench.py --config eval/configs/b1_deepseek.yaml --samples 100 --warmup 3
python bench.py --config eval/configs/b3_deepseek.yaml --samples 100 --warmup 3 --run-name b3_gpu_bench100
```

GPU 上的 B3 结果应使用新 run name 保存，不能覆盖 CPU 结果。压测不调用判题，只统计检索、生成、token 和成本。

## 可复现性边界

- API 模型和价格会变化。
- DeepSeek 服务端延迟受网络、峰谷时段和缓存命中率影响。
- GPU 性能取决于显卡型号、显存、CUDA、PyTorch 和模型精度。
- 检索和确定性评测允许 ±2% 指标波动；网络延迟不适用严格复现。
