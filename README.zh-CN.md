# OpsResolve

接口报错了，找出有问题的配置，审阅具体改动，再确认业务请求恢复。

[English](README.md) · [接入方法](docs/usage.md) · [v0.2.1 预发布](https://github.com/crown-sports/opsresolve/releases/tag/v0.2.1)

![商城演示修复两处配置后，接口返回 HTTP 200，十次恢复检查全部通过](docs/assets/workbench.zh.jpg)

*本地商城演示：修复两处配置，五个服务各检查两次。图中使用演示数据。*

一个商城接口返回 503，存活检查却都是绿的。网关的上游地址写错了，后面的目录服务
又指向了错误的数据库。OpsResolve 会继续查出被第一个故障掩盖的问题，列出字段修改，
把检查过程和恢复结果留在一份事件报告里。

## 先跑一次恢复

需要 Linux 或 macOS、Python 3.11 以上，不用接服务账号或模型。

```sh
git clone --branch v0.2.1 https://github.com/crown-sports/opsresolve.git
cd opsresolve
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[web]'
opsresolve serve --demo
```

打开 **http://127.0.0.1:8765**，点击 **开始诊断 → 具体改动 → 应用方案并验证恢复**。
结果应为 **HTTP 200、10/10 检查通过**。演示会启动真实的本地 HTTP 进程，执行 SQLite 查询。

也可以运行 `opsresolve demo --report recovery.md`，终端会显示
`Recovery: verified (10 business checks)`，结束后停止临时服务。

## 换成自己的服务或追踪文件

| 手里有什么 | 怎么运行 | 得到什么 |
| --- | --- | --- |
| 一个 HTTP 地址 | `opsresolve init --url http://127.0.0.1:3000/ --output target.json`，再运行 `opsresolve diagnose target.json --report incident.md` | HTTP 观测和端点排查 |
| 服务和依赖清单 | `opsresolve serve --target target.json` | 候选原因、检查过程和报告 |
| OTLP JSON 导出 | `opsresolve trace traces.json --output trace-report.md` | 已记录的错误起点、传播关系和耗时 |

建议先接开发服务或已保存的导出。单个 URL 无法推断内部依赖，需要时在
[服务清单](docs/usage.md)中补充。修复必须主动启用，目前只支持已声明、可热加载的已有
JSON 字段。执行前检查原值和文件散列，保留备份，恢复检查失败就回滚。

## 比较一次变更前后的请求

```sh
opsresolve trace-compare examples/trace-regression/before.json examples/trace-regression/after.json --check
```

这个样例会故意退出 **1**：p95 从 **100 ms 升到 180 ms**，错误率从 **0% 升到 10%**。
把路径换成自己的两份导出；加上 `--format json --output comparison.json` 可保存 JSON 报告。
按服务名和操作名比较，缺少操作或样本不足也会阻止门禁通过。

默认两边各至少 5 个 span；延迟同时超过 20% 和 10 ms，或错误率增加，就标记回归。
[阈值与结果解读](docs/product.md)。

## 使用范围

这是给一个可信操作者使用的本地工具。诊断依赖你声明的关系和故障类型，未覆盖的问题
可能留下多个候选原因。追踪比较需要相近的采样和负载；通过已声明的业务请求不等于
验证了整个应用。修复不执行任意代码、Shell 命令、YAML 或 Kubernetes 变更。

[算法](docs/algorithms.md) · [实验数据与失败记录](docs/results.md) · [设计](docs/design.md) · [参与开发](CONTRIBUTING.md)

MIT 许可证。核心使用标准库，网页和模型依赖按需安装。
