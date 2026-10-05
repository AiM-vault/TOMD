# TOMD — Academic PDF/DOCX → AI-Friendly Markdown

批量预处理学术文献（论文/报告），输出干净、降噪的 Markdown，用于投喂大模型做文献综述、信息抽取、知识整理。**目标不是还原排版，而是提升文本质量、减少 AI 被噪声干扰。**

> 需求基线见 [claude/CONTEXT.md](claude/CONTEXT.md)；关键取舍与决策见 [claude/DECISIONS.md](claude/DECISIONS.md)；待用户拍板项见 [claude/PENDING_FOR_USER.md](claude/PENDING_FOR_USER.md)；进度见 [claude/TASKS.md](claude/TASKS.md)。

---

## 1. 需求分析

**业务问题**：研究者手上有成批 PDF/DOCX 学术论文，直接交给 LLM 前需要干净的文本——去掉分离的页眉页脚页码、修复被行断连字符的单词、标识章节结构、可选剔除参考文献以省 token。

**核心需求（六大模块）**
1. **文件扫描**：递归扫 `--source`，收集 `.pdf/.docx`，记录相对路径，向 `--dest` 镜像目录结构；`--overwrite` 控制是否覆盖已存在 `.md`。
2. **DOCX 解析**：标题样式→`#/##/###`；表格→markdown 表格（合并单元格降级拼贴）；图片→占位；重复页眉页脚页码天然排除。
3. **PDF 解析（重点）**：pdfplumber 提文字；多栏检测（按 x0 密度找 gutter，逐词切分）；行重排成段；跨页重复页眉页脚/页码剔除（第 1 页保护）；表格转 markdown；图片占位；扫描版（无文本层）→`【SCANNED DOCUMENT】`；公式→`<!-- FORMULA -->` 标记。
4. **AI 清洗（最关键）**：空白清理、跨段断字合并、存疑行（孤儿页码/装饰符）筛除、章节标记 `<!-- SECTION: X -->`、可选 `--strip-reference` 剔除参考文献（切前校验避免误伤正文）。
5. **输出**：UTF-8 `.md`，镜像目录；`--skip-scanned/--no-table/--no-columns` 等可选参数。
6. **日志与报告**：进度日志；结束生成 `conversion_report.md`（成功/失败+原因/扫描清单/计数自洽）。

**约束与边界**：不引入 OCR（扫描件仅标记）；单文件失败不中断批处理；保留原文语义、仅做格式清洗；依赖仅 `pdfplumber/python-docx/typer/logging`。

---

## 2. 系统设计

### 模块拆分
| 模块 | 职责 | 关键文件 |
|---|---|---|
| `scanner` | 递归发现 + 目录镜像 + 跳过已处理 | `tomd/scanner.py` |
| `parsers` | 源文档 → markdown 脚手架（标题/表格/占位） | `tomd/parsers/{pdf,docx}_parser.py` |
| `cleaner` | 空白/断字/存疑行清洗 + 可测计数器 | `tomd/cleaner.py` |
| `section` | 章节识别 + 参考文献切割 | `tomd/section.py` |
| `pipeline` | 编排 扫描→解析→清洗→写出→报告，逐文件 try/except | `tomd/pipeline.py` |
| `report` | 统计与 `conversion_report.md` | `tomd/report.py` |
| `cli` | Typer 入口 | `cli.py` |

### 依赖选型
- `pdfplumber`：PDF 文字 + 布局（多栏 x0、表格、图片）感知。
- `python-docx`：仅遍历正文本体，页眉页脚天然排除，标题样式映射。
- `typer`：CLI 类型与帮助。
- `logging`（标准库）：进度与错误分级输出到 stderr。

### 数据结构
- `Options`：CLI 全部旗标解析后的唯一配置容器。
- `FileRecord(source_path, relative_path, kind)`：扫描结果。
- `ParseResult(relative_path, source_kind, body, is_scanned, warnings)`：解析结果（body 为清洗前脚手架）。
- `_Line/_Block`：PDF 解析内部——视觉行 / 版块（段落/表格/表格占位/图）。
- `CleanStats`：验收计数器（孤儿页码行、过度粘连行、章节数、参考文献是否剥除）。
- `Section(name, start)`：章节锚点（字符偏移）。

### 关键算法取舍
- **多栏切分在“词级”进行**：按 x0 中心直方图在中带找低密度 gutter；先切词再组行，避免左右栏同基线时被熔成一行（已修复的核心 bug，见 DECISIONS）。
- **段落重排保守优先**：仅在“行首缩进 / 上一行偏短 / 该行像标题”时开新段，其余黏连成段（见 PENDING #1）。
- **页眉页脚仅剔跨页重复行，且保护第 1 页**。

---

## 3. 项目目录结构

```
TOMD/                     # D:\AgentVault\TOMD
├── cli.py                # Typer 命令行入口
├── requirements.txt      # 运行时依赖
├── pyproject.toml        # 打包配置
├── README.md             # 本文档
├── .gitignore
├── tomd/                 # 核心包
│   ├── __init__.py
│   ├── config.py         # Options + 日志 + UTF-8 stdout
│   ├── models.py         # ParseResult / Section / FileRecord
│   ├── scanner.py
│   ├── cleaner.py
│   ├── section.py
│   ├── pipeline.py
│   ├── report.py
│   └── parsers/
│       ├── __init__.py
│       ├── base.py
│       ├── pdf_parser.py
│       └── docx_parser.py
├── tests/                # 单元测试（unittest，34 例）
│   ├── __init__.py
│   └── test_{scanner,cleaner,section,pdf_parser,docx_parser}.py
├── samplepapers/         # 8 篇真实样例（单栏、带文本层）
└── claude/               # 项目协作文档
    ├── CONTEXT.md / TASKS.md / DECISIONS.md / PENDING_FOR_USER.md
```

---

## 4. 全部源代码

源码位于上表所列各文件，均含类型注解、异常捕获、清晰注释：

- CLI 入口：[cli.py](cli.py)
- 包初始化：[tomd/__init__.py](tomd/__init__.py)
- 配置：[tomd/config.py](tomd/config.py)
- 数据结构：[tomd/models.py](tomd/models.py)
- 扫描：[tomd/scanner.py](tomd/scanner.py)
- 清洗：[tomd/cleaner.py](tomd/cleaner.py)
- 章节/参考文献：[tomd/section.py](tomd/section.py)
- 编排：[tomd/pipeline.py](tomd/pipeline.py)
- 报告：[tomd/report.py](tomd/report.py)
- 解析基类/文档：[tomd/parsers/base.py](tomd/parsers/base.py)、[docx_parser.py](tomd/parsers/docx_parser.py)、[pdf_parser.py](tomd/parsers/pdf_parser.py)

---

## 5. 单元测试代码

标准库 `unittest`，共 37 例，覆盖：扫描发现/镜像/跳过、三档输出位置 `--out-mode`、命名 `tomd_<名>_<ext>.md`、断字合并、空白清理、存疑行筛除、章节识别、参考文献切割（含“不误切”反例）、多栏词级切分（合成双栏页断言无交错）、标题识别、DOCX 标题层级/表格端到端。

```bash
python -m unittest discover -s tests -p "test_*.py"
# Ran 37 tests  ...  OK
```

---

## 6. 安装、运行示例

### 安装依赖
```bash
pip install -r requirements.txt
# 或 python -m pip install pdfplumber python-docx typer
```

### 基本用法
**`python cli.py -s <论文所在文件夹> -d <输出文件夹>`**，再加你要的开关。

```bash
python cli.py --source samplepapers --dest out        # 默认镜像：out/<相对目录>/tomd_<名>_pdf.md
```
输出默认命名 `tomd_<源文件名>_<pdf|docx>.md`，加报告 `out/conversion_report.md`。

### 输出位置参数化（--out-mode）
```bash
# 1 = 输出到每篇源文件同目录
python cli.py -s samplepapers --out-mode 1
# 2 = 全部拍平进一个 --dest 目录
python cli.py -s samplepapers -d all_md --out-mode 2
# 3 = 输出进 --dest，镜像源子目录结构（默认）
python cli.py -s samplepapers -d out --out-mode 3
```

### 速度提升：并行 + 解析缓存
```bash
# 并行：--workers N（0=自动按 CPU）
python cli.py -s big_lib -d out --workers 8
# 解析缓存：--cache 目录，重跑时命中则跳过昂贵提取（~20× 提速）
python cli.py -s big_lib -d out --workers 8 --cache .cache
```
缓存 key 含 `--no-table/--no-columns`：改这两个布局旗标会重新解析；改 `--strip-reference`/清洗相关旗标不触发重解析。

### 其它常用参数
```bash
# 精读模式：剥除参考文献、跳过扫描件
python cli.py -s samplepapers -d out --strip-reference --skip-scanned
# 覆盖已生成文件
python cli.py -s samplepapers -d out --overwrite
# 不转表格、关闭多栏切分
python cli.py -s samplepapers -d out --no-table --no-columns
# 详细日志
python cli.py -s samplepapers -d out -v
```

### 三个典型使用示例（命令行）

**示例 1 —— 默认模式：镜像结构输出（最常用）**
```bash
python cli.py -s E:\papers -d E:\papers_md
```
- 扫描 `E:\papers`（含里面所有嵌套子文件夹）
- 输出到 `E:\papers_md\`，**子目录结构一并镜像**；每个源文件→`tomd_<文件名>_pdf.md`（或 `_docx.md`）
- 报告 `E:\papers_md\conversion_report.md`
- **不改动原始论文文件**

**示例 2 —— 全部拍平到一个文件夹**
```bash
python cli.py -s E:\papers -d E:\papers_md --out-mode 2
```
- 同上，但**不保留子目录**，所有 `.md` 平铺在 `E:\papers_md\` 里
- 报告仍在 `E:\papers_md\`

**示例 3 —— 输出到每篇论文自己旁边**
```bash
python cli.py -s E:\papers --out-mode 1
```
- `.md` 直接生成在**每篇 PDF/DOCX 的同一文件夹里**（和源文件挨着）
- **不用 `-d`**；报告写到 `E:\papers\conversion_report.md`（源文件夹根）
- 适合"就地归档"：转完的 .md 就躺在 PDF 旁边

**进阶 —— 精读模式 + 并行 + 缓存**
```bash
python cli.py -s E:\papers -d E:\papers_md --strip-reference --skip-scanned --workers 8 --cache E:\cache
```
- 8 核并行；重跑因缓存快约 20 倍；`--overwrite` 重跑时覆盖旧 .md（不加则自动跳过）

### 对样例全量跑通
```
9 个文件：全部成功，0 失败，0 扫描，0 残留页码行；并行 4 worker + 缓存重跑仅 0.6s
```
各文档章节标记 1–6 个；含表格文献（Liebman 32、Heese 14 等）表格已转 markdown；图片占位正常生成。DOCX（含标题层级/表格/章节标记）已在构造样本上端到端验证。

---

## 7. 已知局限、后续迭代方向

### 已知局限（诚实声明）
1. **无词典断字歧义**：行尾连字符一律按“软断字”合并（`meth-⏎od→method`），偶尔会把恰好在连字符处折行的合法复合词（`self-⏎referential→selfreferential`）也归一化。频次低，且需词典才能完全规避。
2. **多栏检测是启发式**：基于 x0 密度 gutter；极端排版（跨栏标题、复杂浮动图注）可能判不准，可 `--no-columns` 关闭。
3. **段落重排保守**：正文中依赖“首行缩进/短行”信号开新段，无缩进的紧排期刊可能被过度黏连成少数长段（可读但不如分人眼细）。
4. **公式仅占位**：`<!-- FORMULA -->` 保原文、不保证符号可读；页脚脚注可能与正文交错（信息保留但顺序偶乱）。
5. **表格降级**：无完整框线的复杂/合并表退化为文本拼贴，非高保真表格。
6. **扫描版 PDF 不做 OCR**：无文本层仅标记或 `--skip-scanned` 跳过。
7. **语料单一领域**：当前以公共采购/财政文献（单栏）验证，页眉页脚模式会随期刊而异，新期刊需验证。

### 后续迭代方向
- 引入轻量断字词典（如 hunspell 词形）区分软断字与真连字符。
- 基于字体大小/字重的标题层级识别（更准的 `#/##/###`）。
- 页眉页脚匹配改为“跨页相同短语 + 位置 + 频率”的更强模型；支持多页脚注与页眉白名单。
- 3+ 栏与含浮动图表的复杂版面专门处理。
- 可选：文首 YAML 元数据块（标题/DOI/作者）供 LLM 引用。
- 表格合并单元格推断（colspan/rowspan 还原）。
- 增量/缓存：记录已完成文件的哈希，避免重复解析未改事件。

---

*Generated 2026-10-04 by Claude Code, following claude/CONTEXT.md. Tracking: claude/TASKS.md.*