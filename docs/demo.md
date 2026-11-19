# Record the workbench demo · 自己录制操作指南

## 打开界面（Open the workbench）

打开 [本地 Streamlit 工作台](http://127.0.0.1:8501)。左侧的 **Predict、Review、Monitoring、Models** 分别是预测、审核、监控和模型版本。如果当前服务仍在运行，可以直接开始。正常的首次录制从空白数据和版本 1 开始。仅使用内置合成样例或随仓库提供的 [合成示例文件](../data/example_panel.csv)。

如果页面打不开，从仓库根目录运行以下命令。本机已有的验证环境位于临时目录时，可以直接用它启动。

```bash
WORKBENCH_PYTHON=/private/tmp/lab-workbench-dev/venv/bin/python bash scripts/record-demo.sh
```

换机器时，先按 [README 的 Python 安装步骤](../README.md#run-locally)创建并激活 Python 3.11 环境，然后运行 `bash scripts/record-demo.sh`。每次启动都会创建一份新的录制数据库（recording database）。练习结束准备正式重录时，在启动终端按 `Control+C` 停止服务，再运行同一命令。保持启动终端打开，浏览器中访问同一个本地地址。

## 录屏方式（Screen capture）

在 Mac 上按 `Shift–Command–5`，选 **Record Selected Portion（录制选定部分）**，只框住工作台。点 **Options（选项）**选择麦克风，然后点 **Record（录制）**。录完在菜单栏点停止按钮。先试录十秒，检查声音和画面大小，再开始正式录制。[Apple 录屏说明](https://support.apple.com/en-ca/102618)

## 五分钟逐屏操作（Five-minute walkthrough）

| 时间 | 实际点击 | 要看到的结果和可直接说的英文 |
| --- | --- | --- |
| 0:00–0:20 | 打开 **Predict**。保持 **Synthetic example** 和 **Baseline panel**。 | “This workbench uses synthetic lab results to demonstrate deployment, human review, and model operations.” |
| 0:20–0:55 | 点 **Submit panel**。在同一个请求编号下再点一次。 | 页面第一次显示 **Prediction saved**，第二次显示 **Existing prediction returned**。“The service stores the score with its model version. A repeat submission with the same request identifier and inputs returns the saved result.” |
| 0:55–1:15 | 把 **Example** 切换成 **Out-of-range white blood cells**，点 **Submit panel**。 | 出现 **HTTP 422**，即超文本传输协议（Hypertext Transfer Protocol，HTTP）的输入校验错误状态。“The service rejects the negative value before the model runs.” |
| 1:15–1:55 | 打开 **Review**，选择第一条病例。选 **flagged**，填写 `Verify the source value.`，点 **Save review**。 | 在 **Review history** 看见审核者、时间和意见。“The reviewer can see the original panel and version. The audit trail records what they did and when.” |
| 1:55–2:40 | 打开 **Monitoring**，点 **Send 30 synthetic shifted panels**。向下滚到 **Input distribution**，选择 **White blood cells**。 | 看到 **Shift signal** 和分布柱状图。“We can see an input shift. To assess a change in accuracy, we need independently sourced labels.” |
| 2:40–3:35 | 打开 **Models**，向下找到 **Offline replay**，点 **Run offline replay**。先讲 **Reference-like** 结果表，再看分流数量。 | 指给观众看：同一批病例，独立标签下版本 2 为 72.1%、版本 1 为 70.0%，模型影响过的标签下排名反转。“The predictions stay fixed. Changing the source of the comparison labels can change the release decision.” |
| 3:35–4:45 | 在 **Version to activate** 选 `v2`，填 `Recording: evaluate version 2`，点 **Activate version**。回 **Predict** 选 **Baseline panel**，点 **New request ID** 再提交。回 **Models** 选 `v1`，填写 `Recording: restore baseline` 并激活。 | 新预测显示 **v2**。回滚后活动版本为 **v1**，切换原因保存在 **Activation history**。“New requests use the active release. An older prediction retains the version that originally scored it.” |
| 4:45–5:00 | 在 **Activation history** 停一下。 | “I verified the path from a running service to traceable review, monitoring, and rollback.” |

如果想展示文件导入，把开头的 **Synthetic example** 换成 **CSV**，上传 `data/example_panel.csv` 并选择第 1 行。CSV 是逗号分隔值（Comma-Separated Values）文件。正式录制建议先用内置的 **Baseline panel** 走通一遍，时间更稳定。

## 交流前准备（Interview preparation）

先展示部署图（deployment diagram）。Streamlit 审核界面和未来的定制网页前端（custom web frontend）可以调用同一个 FastAPI 服务，由服务统一处理输入校验、审计和版本切换。离线比较（offline replay）时，也可查看分流策略把多少病例送往第二阶段模型。

### 常见追问（Likely follow-up questions）

- **Why SQLite?** It keeps the local system small and gives atomic prediction and audit writes. Serialization bounds throughput and is an explicit demo tradeoff.
- **How would you validate a real use case?** Define the decision and time of use with users first. Verify feature availability, label provenance and review workload before designing a cohort and prospective evaluation.
- **How much work did it save?** No time study was performed. The concrete behavior shown is avoiding repeated scoring and duplicate prediction records on retries and consolidating the case details and feedback in the review view.
- **How does this build on your prelim?** Progressive Neural Networks (PNN) preserve old columns while adding capacity for new tasks. Here I keep the incumbent release fixed and compare policies on reference-like and shifted cohorts. The cascade addresses a separate question about routing at prediction time.
- **Why consider a custom front end?** The deployment diagram shows it calling the same service. I would start with a case queue and review pane and verify that the interaction reduces work before migrating more screens.
