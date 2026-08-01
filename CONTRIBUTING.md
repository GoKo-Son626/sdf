# 参与贡献

感谢你愿意改进 SDF Translator。项目目前优先保证 Arch Linux、Wayland 和 niri 上的核心体验，同时欢迎为其他 Linux 发行版和桌面环境补充适配。

## 开始之前

- 功能建议和缺陷请先搜索现有 Issue，避免重复。
- 安全漏洞不要公开提交完整利用细节，请按照 [SECURITY.md](SECURITY.md) 报告。
- 不要提交 API Key、代理凭据、个人翻译记录、剪贴板内容或包含隐私的日志。
- 新功能应保持依赖精简；如果确实需要新增依赖，请在 PR 中说明原因和替代方案。

## 本地开发

```bash
git clone https://github.com/GoKo-Son626/sdf.git
cd sdf
PYTHONPATH=src python -m unittest discover -s tests -v
python scripts/check_repository.py
```

安装到当前 Arch 用户环境进行手工测试：

```bash
./install.sh --yes
```

## 提交要求

- 一个提交尽量只处理一个完整目的，使用简洁的英文提交信息。
- 修复缺陷时补充能覆盖旧问题的测试。
- 改变命令、配置、安装方式或用户界面时同步更新 README。
- 提交前运行全部测试和隐私检查，确认 `git status` 中没有个人文件。
- PR 中说明测试平台；桌面集成改动至少注明 Wayland 合成器和编辑器/阅读器。
