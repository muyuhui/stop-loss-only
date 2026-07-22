## ADDED Requirements

### Requirement: Use SQLite settings suitable for monitored local writes
默认 SQLite 引擎 SHALL 启用外键、WAL 和有界 busy timeout，并在备份、恢复和并发测试中验证这些设置不会破坏一致性。

#### Scenario: Manual refresh overlaps a read
- **WHEN** 监控事务写入时仪表盘同时读取
- **THEN** WAL 允许读取最近已提交快照且请求不会读取部分事务

#### Scenario: Write lock exceeds busy timeout
- **WHEN** 写锁在超时内无法取得
- **THEN** 系统返回稳定 `database_busy` 诊断而不是无限等待

### Requirement: Export privacy-aware diagnostics
系统 SHALL 提供诊断导出命令，默认包含版本、schema、配置掩码、监控聚合和日志摘要，不包含数据库、完整持仓或通知密钥，并允许用户预览内容清单。

#### Scenario: Create default diagnostic package
- **WHEN** 用户执行诊断导出且未选择数据库
- **THEN** 包中不包含价格、数量、成本、完整标的名称或密钥

## MODIFIED Requirements

### Requirement: 显式数据库迁移
系统 SHALL 使用有序、不可跳号、可验证升级和降级的迁移更新 schema，每个迁移具有独立版本和事务边界，不得在模块导入时创建或修改正式数据表。

#### Scenario: 数据库版本符合预期
- **WHEN** 后端执行 readiness 检查
- **THEN** schema 兼容检查成功且检查过程不修改数据库结构

#### Scenario: 存在待执行或未知 revision
- **WHEN** 启动时发现 schema 落后、超前或包含未知版本
- **THEN** readiness 失败并给出可执行迁移提示，监控任务不得启动

#### Scenario: 验证逐版本升级和降级
- **WHEN** 自动化测试从代表性 schema v2 数据库升级至最新版再降级
- **THEN** 每个声明可逆的迁移依次执行且无关记录、Decimal 精度和告警快照保持完整

#### Scenario: 迁移到影子领域模型
- **WHEN** 旧 holding 被迁移为标的、仓位、批次和规则
- **THEN** 迁移前后数量、成本、状态、止损价、告警数和组合汇总通过自动对账

### Requirement: 可验证的备份与恢复
系统 SHALL 使用一致性 SQLite 快照、唯一文件名、checksum manifest、schema revision、WAL 感知完整性和兼容范围校验提供备份恢复，并在替换活动数据库前创建恢复点。

#### Scenario: 创建连续备份
- **WHEN** 用户在同一秒内创建两次备份
- **THEN** 系统生成两个不互相覆盖的快照和 manifest

#### Scenario: 恢复有效兼容备份
- **WHEN** 服务已停止且快照 checksum、完整性和 schema 均在支持范围
- **THEN** 系统先备份当前数据库，再原子替换并执行 readiness 校验

#### Scenario: manifest schema 不兼容
- **WHEN** 备份 schema 高于当前程序支持版本或低于最低可迁移版本
- **THEN** 恢复中止且活动数据库不被替换

#### Scenario: 替换后 readiness 失败
- **WHEN** 新数据库替换后本地 readiness 校验失败
- **THEN** 系统自动恢复替换前恢复点并报告稳定错误
