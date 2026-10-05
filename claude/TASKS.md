# TASKS.md — 进度跟踪

> CLI 批量文献预处理工具（PDF/DOCX → AI 友好 Markdown）
> 每项工作完成后同步勾选；关键取舍写入 DECISIONS.md。

## 状态约定
- [x] 完成 · [ ] 待办 · [~] 进行中 · [!] 阻塞/风险

---

## 阶段 0：上下文与初始化
- [x] 阅读并理解 claude/CONTEXT.md
- [x] 初始化 TASKS.md / DECISIONS.md
- [x] 确认 samplepapers 样例特性（8 篇全部单栏、带文本层学术 PDF，含期刊页眉/DOI/页码）

## 阶段 1：需求分析（交付节 1）
- [x] 复核 6 大模块、逐项确认边界与验收标准（修订 CONTEXT.md）
- [x] 锁定 CLI 参数集（--source/--dest/--overwrite/--strip-reference/--skip-scanned/--no-table/--no-columns）
- [x] 文档化：README 需求分析节

## 阶段 2：系统设计（交付节 2–3）
- [x] 模块拆分（scanner/parsers/cleaner/section/pipeline/report/cli）与依赖选型
- [x] 数据结构（Options/FileRecord/ParseResult/_Line/_Block/CleanStats/Section）
- [x] 项目目录结构；README 设计节

## 阶段 3：编码（交付节 4）
- [x] 文件扫描模块
- [x] DOCX 解析模块
- [x] PDF 解析模块（多栏词级切分 / 段落重排 / 页眉页脚 / 表格 / 图片 / SCANNED / FORMULA）
- [x] AI 清洗模块（空白/断字/存疑行/章节标记/strip-reference）
- [x] 输出写入模块（镜像目录 + 全部 CLI 参数逻辑）
- [x] 日志与报告模块
- [x] 捕获所有异常、单文件失败不中断批处理

## 阶段 4：测试（交付节 5）
- [x] 单元测试 34 例：scanner/cleaner/section/pdf_parser/docx_parser
- [x] 边界：双栏合成断言不交错、扫描/损坏/空表/DOCX 标题表格端到端
- [x] 全量跑通过：`python -m unittest discover -s tests -p "test_*.py"` → OK

## 阶段 5：安装与运行（交付节 6）
- [x] requirements.txt / pyproject.toml（含 `tomd` 脚本入口）
- [x] README 安装/运行示例
- [x] 对 samplepapers 全量实跑：9/9 成功、0 失败、0 扫描、0 残留页码行，生成出 out/ 与 conversion_report.md
- [x] 追加验证：嵌套目录 DOCX 镜像、覆盖跳过、表格转 md

## 阶段 6：文档收尾（交付节 7）
- [x] README「已知局限、后续迭代方向」
- [x] PENDING_FOR_USER.md 记录待拍板项
- [x] DECISIONS.md 补录 D9/D10

---

## 日志
- 2026-10-04：初始化 → 需求细化 → 设计与编码 → 修复（多栏同基线熔行 bug、断字空格 bug、CleanStats 共享字段 bug、is_junk 空行误计、Discussion 正则缺 re.I）→ 34 测试全绿 → 全量跑通 → 文档收尾。**任务完成待你明日复核。**
- 2026-10-05：按反馈升级——并行 `--workers`（ProcessPoolExecutor）+ 解析缓存 `--cache`（同旗标重跑约 20× 提速）；输出位置参数化 `--out-mode 1(就近)/2(拍平)/3(镜像)` + 命名 `tomd_<名>_<ext>.md`；DOCX 构造样本端到端复验；测试增至 37 例全绿。