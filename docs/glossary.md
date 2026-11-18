# English–Chinese project glossary 项目中英术语表

## Project scope and interview context 项目与面试背景

| Term | Full name | 在本项目中的意思 |
| --- | --- | --- |
| MVP | Minimum Viable Product | 最小可行产品。用尽量少的功能把最重要的流程跑通。这个项目的一版 MVP 能导入合成数据、校验输入、调用模型、保存预测、人工审核、查看监控并回滚模型。 |
| Lab | Laboratory | 实验室。项目名中的 Lab 指实验室检验这一演示场景。 |
| AI | Artificial Intelligence | 人工智能。本项目展示的是一个表格预测模型的服务和审核流程。 |
| ML | Machine Learning | 机器学习。本项目用合成样本训练模型识别模拟的复核标签。 |
| MLOps | Machine Learning Operations | 机器学习运维。让模型能稳定上线、被监控，并在必要时回滚。在这个项目里，可以用同一套训练产物部署模型，还能查到每条结果的模型版本。 |
| DLMP | Department of Laboratory Medicine and Pathology | 实验室医学与病理学部门。用于理解岗位背景，本项目仅作独立演示。 |
| CARE | Clinical AI Readiness Evaluator | 临床人工智能就绪度评估框架。公开论文为展示数据、模型服务和用户体验之间的衔接提供参考。 |
| UCI | University of California, Irvine | 加州大学尔湾分校。其机器学习资料库托管了早期考虑过的慢性肾病数据集。 |
| CKD | Chronic Kidney Disease | 慢性肾病。这里用于指背景文献中的公开数据集。演示数据由本项目的模拟器生成。 |

## Inputs, service and review 输入、服务与审核

| Term | Full name | 在本项目中的意思 |
| --- | --- | --- |
| CSV | Comma-Separated Values | 逗号分隔值文件。演示用它导入检验面板，每一行是一条合成记录。 |
| UI | User Interface | 用户界面。这里指 Streamlit 中的预测、人工审核、监控和模型管理页面。 |
| API | Application Programming Interface | 应用程序编程接口。这里指 Streamlit 用来提交检验数据、取回预测、保存审核和读取监控的接口。 |
| HTTP | Hypertext Transfer Protocol | 超文本传输协议。界面通过它调用预测服务。项目中 GET 用于读取，POST 用于提交数据或执行操作。常见状态码有 200（成功）、404（找不到资源）、409（请求标识与已有记录冲突）、422（输入校验失败）和 500（服务内部错误）。 |
| JSON | JavaScript Object Notation | 一种结构化文本数据格式。界面以这种格式发送字段，服务以这种格式返回预测或错误详情。 |
| ID | Identifier | 标识符。这里对应请求或审核事件的编号。 |
| UUID | Universally Unique Identifier | 通用唯一标识符。项目用它作为请求编号和审核编号。重试时复用原编号，服务才能识别这是不是同一次提交。 |
| UTC | Coordinated Universal Time | 协调世界时。服务用统一时区记录预测、审核和模型切换时间。 |
| SHA-256 | Secure Hash Algorithm, 256-bit | 256 位安全哈希算法。项目用它生成模型文件的校验值并记录到预测中，便于确认用的是哪一份模型文件。 |
| WAL | Write-Ahead Logging | 预写日志。这里是 SQLite 的一种写入模式，让写入发生时读请求仍可读取已有快照。 |
| SQL | Structured Query Language | 结构化查询语言。服务用它从 SQLite 数据库读写预测、审核和模型版本记录。 |
| KB / MB | Kilobytes / Megabytes | 字节容量单位，用于文件大小提示。当前演示只接受 64,000 字节以内的 CSV 文件。 |

## Metrics and releases 指标与版本

| Term | Full name | 在本项目中的意思 |
| --- | --- | --- |
| ROC AUC | Area Under the Receiver Operating Characteristic Curve | 受试者工作特征曲线下面积。这里衡量模型能否在同一组合成留出样本中把正例排在负例前面，可以按“随机抽一条正例和一条负例，正例排得更靠前的概率”来理解，并列按一半计。 |
| p95 | 95th percentile | 第 95 百分位。比如 p95 延迟是 20 毫秒，表示大约 95% 的请求耗时在 20 毫秒以内。 |
| ms | Milliseconds | 毫秒。1 毫秒等于千分之一秒。 |
| CI | Continuous Integration | 持续集成。这里指 GitHub Actions 在提交后自动运行测试，并检查容器中的服务能否启动。 |
| v1 / v2 | Version 1 / Version 2 | 第一个和第二个模型版本。这里分别是逻辑回归和随机森林。切换版本只影响新的预测请求。 |

界面单位中，`g/dL` 指克每分升，`10⁹/L` 指每升十亿个细胞，`fL` 指飞升，也就是 10⁻¹⁵ 升。模型字段名中的 `WBC` 指 *white blood cells*（白细胞），`MCV` 指 *mean corpuscular volume*（平均红细胞体积）。

## Model adaptation and routing 模型适应与请求分流

| Term | Full name | 在本项目中的意思 |
| --- | --- | --- |
| PNN | Progressive Neural Networks | 渐进式神经网络。训练新任务时保留旧网络列的参数，并增加新列。它为保留现行模型、同时验证新数据上的表现提供了设计参考。 |
| Cascade | Two-stage model cascade | 两阶段模型级联。第一阶段先评分，部分记录按规则进入第二阶段。本项目在离线回放中统计分流量和标签一致率。 |
| Label feedback loop | Model-influenced label feedback loop | 标签反馈循环。现行模型的建议可能影响以后用来评估或训练的标签，从而改变版本比较结论。 |
| Offline replay | Offline replay evaluation | 离线回放评估。对同一批合成输入重放固定模型的预测，再用不同来源的标签比较结果。 |
