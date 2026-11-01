# D15 最终交付说明

## 交付信息

| 项目 | 内容 |
|---|---|
| 版本 | `v1.0.0` |
| 发布日期 | 2026-11-01 |
| GitHub 仓库 | https://github.com/BBcxy1634/compliance-qa |
| Release | https://github.com/BBcxy1634/compliance-qa/releases/tag/v1.0.0 |
| 默认问答模式 | B1 Fast |
| 可选高质量模式 | B3 |
| Python | 3.12+，推荐 3.13 |

## 交付内容

- 完整的 ingest、切分、向量检索、混合检索、重排和生成代码。
- 7 份项目 PPT 和官方来源清单。
- 60 题冻结评测集及 B0-B3 实验结果。
- B1 Fast 延迟、成本与 Badcase 分析。
- Gradio Demo、演示脚本和四张界面截图。
- 数据准备、评测、压测、环境检查和复现脚本。
- 自动化测试、MIT License 和数据权利说明。

官方网页、监管 PDF、向量库、切分结果、`.env` 和模型缓存不进入交付仓库。首次复现时由脚本重新获取和构建。

## 最终验收

验收环境：

```text
Windows PowerShell
Python 3.13.2
CPU 模式
```

执行结果：

```powershell
python -m pytest -q
python scripts/check_environment.py --require-data
```

- 自动化测试：33 项通过。
- DeepSeek Key：已配置。
- CUDA：当前机器不可用，自动回退 CPU。
- BGE-M3 语义向量：271 条。
- B0 向量：334 条。
- 60 题状态：全部 `approved`。

## 核心指标

| 配置 | 答案正确率 | 事实题 | 多跳题 | 拒答准确率 |
|---|---:|---:|---:|---:|
| B0 | 0.82 | 0.85 | 0.70 | 1.00 |
| B1 | 0.90 | 0.925 | 0.80 | 1.00 |
| B2 | 0.90 | 0.95 | 0.70 | 1.00 |
| B3 | 0.94 | 0.95 | 0.90 | 1.00 |
| B1 Fast | 0.92 | 0.95 | 0.80 | 1.00 |

B1 Fast 的 100 次压测平均延迟为 1.92 秒，P95 为 3.31 秒，平均成本约人民币 0.0010 元/次。

## 使用方式

在解压后的项目根目录执行：

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

在 `.env` 中填写 `DEEPSEEK_API_KEY`，然后运行：

```powershell
python scripts/bootstrap.py
python scripts/check_environment.py --require-data
.\.venv\Scripts\python.exe app.py --port 7860
```

浏览器打开 `http://127.0.0.1:7860`。

## 已知限制

- B1 Fast 的 P95 为 3.31 秒，尚未完全达到 3 秒目标。
- B3 在 CPU 上首次加载和单题响应较慢，适合按需启用。
- 自动判题尚未完成独立人工复核。
- Demo 是单轮问答，不保存会话历史。
- 当前版本是本地可运行和可公网发布的软件交付，不等同于带账号、限流和监控的生产 SaaS。

## 数据权利

代码和原创文档采用 MIT License。项目 PPT 和官方来源材料的权利范围见 [NOTICE.md](../NOTICE.md)。
