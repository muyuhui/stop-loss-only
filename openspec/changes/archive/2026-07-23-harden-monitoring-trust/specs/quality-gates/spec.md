## ADDED Requirements

### Requirement: Block all network access in mandatory tests
必选测试 SHALL 安装网络哨兵，任何 DNS、socket 或真实 provider 调用 MUST 立即失败并指出调用点；真实行情测试只能显式选择运行。

#### Scenario: Provider accidentally calls the network
- **WHEN** 必选测试路径尝试访问真实网络
- **THEN** 测试立即失败而不是等待超时

### Requirement: Test concurrent monitoring outcomes
测试套件 SHALL 覆盖并发触发胜出/失败、唯一约束冲突、单标的失败、部分提交和数据库 busy，并验证响应等于已提交事实。

#### Scenario: Two cycles trigger one holding
- **WHEN** 两个周期并发触发同一持仓
- **THEN** 最终只有一个告警且两个响应都不包含虚构触发

## MODIFIED Requirements

### Requirement: 本地端到端冒烟测试
项目 SHALL 提供可复现的完全离线冒烟测试，使用隔离数据库、fixture provider 和 fixture calendar 启动后端与前端并验证核心 API 和触发流程。

#### Scenario: 完全离线冒烟成功
- **WHEN** 网络被阻断且项目依赖已安装
- **THEN** 冒烟测试在有界时间内完成并验证没有外部网络访问

#### Scenario: 冒烟启动或请求失败
- **WHEN** 服务启动、请求、触发或清理任一步失败
- **THEN** 命令返回非零退出码并输出可定位阶段
