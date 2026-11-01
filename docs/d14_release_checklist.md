# D14 GitHub 发布清单

## 发布前状态

- Python 最低版本统一为 3.12，推荐 3.13。
- 文档中的个人绝对路径已改为通用项目根目录说明。
- 源代码和原创文档采用 MIT License。
- 项目 PPT 和外部官方资料的数据权利已在 `NOTICE.md` 中单独说明。
- `.env`、官方 HTML/PDF、向量库和运行缓存均由 `.gitignore` 排除。
- 当前代码和 Git 历史未发现 API Key 或私钥。
- `python -m pytest -q` 与 `scripts/check_environment.py --require-data` 已通过。

## 创建 GitHub 仓库

在 GitHub 网页创建仓库后，将下面的 `<OWNER>` 和 `<REPOSITORY>` 替换为实际值：

```powershell
Set-Location '<克隆后的 compliance-qa 项目根目录>'
git remote add origin https://github.com/<OWNER>/<REPOSITORY>.git
git push -u origin master
```

如果使用 GitHub CLI，也可以在完成 `gh auth login` 后执行：

```powershell
gh repo create <REPOSITORY> --private --source . --remote origin --push
```

只有确认 PPT 和评测结果均可公开后，才应把仓库改为 public。

## 推送前复查

```powershell
git status --short
git remote -v
git grep -l -E 'sk-[A-Za-z0-9_-]{20,}'
python -m pytest -q
python scripts/check_environment.py --require-data
```

确认 `.env` 不在 Git 跟踪列表中：

```powershell
git ls-files .env
```

该命令应没有输出。

## GitHub 仓库设置

- 仓库描述：`可追溯的跨境卖家合规 RAG 问答助手`
- Topic：`rag`、`compliance`、`gradio`、`deepseek`、`bge-m3`
- 默认分支：`master`，也可以按团队习惯改为 `main`
- 公开发布前确认 `LICENSE` 和 `NOTICE.md` 可见
- 不要上传 `.env`、模型缓存、原始官方 PDF/HTML 或 `chroma_db`
