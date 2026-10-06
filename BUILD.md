# 生成、维护与传播

## 普通读者

下载 `index.html`，用浏览器打开。所有正文、样式和脚本已内嵌；不需要启动服务器、安装软件或联网加载内容。手机需先下载，再选择支持 JavaScript 的浏览器打开。聊天软件及文件管理器的预览可能限制脚本，浏览器中的文件阅读不依赖这些预览能力。

复制摘要会保留条目编号、限定条件、核验日期与署名。离线文件没有公共网页地址；分享时请同时发送 HTML，接收者可以搜索条目编号。剪贴板权限不可用时会打开手动复制文本框。

## 维护者

要求 Python 3.10 或更新版本，仅使用标准库。

```sh
python scripts/build.py
python scripts/build.py --check
python -m unittest discover -s tests -v
```

`data/handbook.json` 是统一内容源。修改它后执行生成脚本，将生成的 HTML、CSV、分章正文、README、摘要及复核记录一起提交。`src/handbook.html` 是页面模板。`data/review-scope.json` 记录升级开始时固定的重点复核候选与纳入理由；后续新一轮复核应创建新的日期版本清单，避免静默改变本轮统计范围。

每条使用 `c01-i001` 格式编号，由章节和原建议编号构成，不能按排序位置重新编号。保留 CSV 原有 11 个字段，网页使用独立的六类 `status`；历史 `source_status`、`last_verified` 不代表本次核验。`revised_conclusion` 是展示结论，`conditions` 是适用条件；`summary` 保留旧摘要，`sources` 收录本次查读的一手材料与支持范围。

`review_outcome` 为 `legacy`（未新核验）、`unresolved`（证据缺口）、`verified`（本次取得支持）或 `contradicted`（原说法被否定）。`checked_at` 记录检查日期；检查来源结构并不等于已读完证据。只有证据足以支持修订结论时才设置 `verified_at`，并写清 `change_reason`、来源及适用条件。不得因重新生成页面刷新历史日期。

`scripts/import_legacy.py` 是本轮迁移工具，读取升级前 CSV 与固定旧提交 `dd169a86770f77fd96aa8008b4dc24eb5466902b` 的分章表格；已有新复核记录时禁止覆盖。它不是日常维护入口，生成后的章节文件也不再使用旧表格格式。

本轮已查读的证据与有限修订记录在 `data/review-updates.json`，`scripts/apply_reviews.py` 用于重放本轮迁移后的修订。日常维护直接修改统一数据源。`data/upstream-links.json` 是上游快照引用结构，包含提交号；引用入口并不等于本次已核实。其可选提取命令为 `python scripts/extract_upstream_links.py --upstream /path/to/upstream-checkout`，日常生成不需要上游仓库。

## 浏览器验收

通过 gstack `/browse` 验证本地文件：手机与电脑宽度、搜索、所有状态组合、空结果、目录跳转、被筛选隐藏条目的定位、详情展开、复制权限降级和打印。打印会暂时展开整本内容，结束后恢复筛选及展开状态。检查阅读及搜索没有运行时网络请求；不依赖外部服务器或 CDN。脚本读取来源数据时对 `<` 等字符做转义，正文用 `textContent` 渲染。

传播文件是 `index.html` 的字节一致副本，可以改名为 `更好生活离线手册-2026-10-07.html`。生成后用 `--check` 和测试验证一致性。本版本不加入账号、收藏、在线部署或统计追踪。
