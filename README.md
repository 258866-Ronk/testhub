# TestHub（Python 版）

一个**从 0 到 1 搭建**的自动化测试管理平台。Web 层用 Flask，存储用 SQLite，默认档**零外部依赖**即可一键跑通；Worker 会真实调用姊妹项目 AutoTest Pro 的 CLI 执行用例，解析 `report.json` 回填统计与质量门禁。

> 说明：这是本人独立设计与实现的个人练习项目，未包装成企业生产平台。MySQL / Redis / RabbitMQ / Vue3 生产档不在默认验收范围内。

## 技术栈

Python 3 · Flask · SQLite(WAL) · 手写 HS256 JWT + RBAC · 事务 Outbox · 后台 Worker · Cron 调度 · 线性插值 Percentile · pytest

## 核心能力

| 能力 | 说明 |
|---|---|
| JWT + RBAC | VIEWER / OPERATOR / ADMIN 三级角色，接口级鉴权；演示级密钥 |
| 事务 Outbox | `th_run` 与 `th_outbox` 同一事务写入，避免"写了任务没发消息" |
| CAS 幂等领取 | `UPDATE ... WHERE status='NEW'` 保证多 worker 只有一个领到；run 状态二次 CAS `PENDING→RUNNING` |
| 幂等键 | `idempotency_key` 唯一索引，重复触发返回同一 run |
| 业务失败 vs 平台故障 | 用例断言失败=业务结果，直接 FAILED 由 CI 门禁拦截，**不重试**；引擎缺失/超时/无报告=平台故障，指数退避重试，超上限进死信 |
| 死信重放 | 生成全新 run，绝不修改历史 |
| 引擎隔离 | 每次运行独立工作目录，复制用例+环境配置快照，写 `config-snapshot.json`/`command.txt`/`engine.log`，动态分配端口 |
| 性能分析 | P50/P90/P95/P99/AVG/MAX 线性插值，数据来自真实 `report.json` 的 `responseTimeMs` |
| CI 门禁 | `GET /runs/{no}/gate` 返回 allowed/exitCode，只有 SUCCESS 且 failed=0 才放行 |
| 单文件控制台 | 免构建 HTML，登录→触发→查询→门禁→性能一条龙 |

## 快速开始

先确保姊妹项目 `py-autotest-pro` 与本目录**同级**，且依赖已安装：

```bash
pip install -r requirements.txt
pip install -r ../py-autotest-pro/requirements.txt
python -m pytest                       # 单元测试
python server.py --no-cron             # 启动 API + Worker（另开终端）
python smoke_test.py                   # 端到端冒烟 23 项
```

浏览器打开 `http://127.0.0.1:9090`。演示账号：`op/123456`（OPERATOR）、`admin/123456`（ADMIN）、`viewer/123456`（VIEWER）。

## 实测结果

```
pytest: 全绿
health: status=UP, engineReady=true
smoke : 13/13 checks passed
run RUN-... -> SUCCESS, 8/8 用例, P95 已计算, CI gate allowed=true
```

## 设计要点

1. **业务失败绝不重试**：断言失败是测试结果，重试没有意义还会污染统计；只有平台级故障才进入重试/死信链路。
2. **Outbox 与 run 同事务**：先写 run 再发消息可能出现"任务存在但没人执行"，放在同一事务里从根上避免。
3. **为什么死信重放生成新 run**：直接改历史 run 会破坏审计链；重放新建 run 保留完整轨迹。
4. **配置快照**：每次运行复制用例与环境到独立目录并留存命令与日志，保证结果可复现、可追溯。
