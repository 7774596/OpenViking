# OpenViking 系统设计分析

- [系统设计与整体流程分析（PDF）](OpenViking系统设计与整体流程分析.pdf)：16 页中文报告，覆盖系统边界、上下文模型、主要数据流、集成、权限、一致性和设计取舍。
- 分析日期：2026-10-08。
- 代码基线：[`55c34934e7b61a8755303e0df1da7a4d4cffcc53`](https://github.com/7774596/OpenViking/commit/55c34934e7b61a8755303e0df1da7a4d4cffcc53)。核对时目标仓库与上游 `main` 一致。
- 文档只分析系统设计，不涵盖性能调优或部署环境验证。引用固定到上述提交。

## 一个需要注意的代码与文档差异

该提交的升级文档写明 Working Memory 默认关闭，但服务端 `openviking/session/memory_policy.py` 中的 `working_memory_enabled` 以及缺省解析仍为 `True`。Codex 插件的 `resumeArchiveInject` 默认值则已是 `false`。报告区分这两个层面，不将插件停止注入历史等同于服务端停止生成摘要。

## 可编辑源文件与重新生成

- `source/report.json`：中文正文、流程图结构与源码引用。
- `source/build_pdf.py`：ReportLab 排版与矢量图生成器。

依赖 Python 3 和 ReportLab；中文字体默认使用 Droid Sans Fallback，西文字体默认使用 DejaVu Sans。可通过 `OV_CJK_FONT`、`OV_LATIN_FONT` 指定其他兼容 TrueType 字体路径。

在本目录执行：

```bash
python3 source/build_pdf.py
```

生成器会检查每一页是否溢出，并输出 PDF 页数、文件大小及 SHA-256。图形与中文文字直接写入 PDF，文字可以检索和复制，引用可以点击。
