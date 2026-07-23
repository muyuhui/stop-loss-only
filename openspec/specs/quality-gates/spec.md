# Quality Gates

## Purpose

为项目建立可复现、默认离线且能够阻止回归进入发布状态的质量门禁，统一后端、前端、数据库迁移、端到端冒烟和生产包体的验证标准，并明确真实行情测试与必选确定性测试之间的边界。
## Requirements
### Requirement: 可复现的验证命令
项目 SHALL 提供非交互命令，将开发依赖安装与运行启动分离，并执行所有必选后端、前端、迁移和构建门禁；任一必选项失败都必须返回非零。

#### Scenario: 所有门禁通过
- **WHEN** 在准备好的干净环境运行验证命令
- **THEN** 命令成功退出，并报告每项必选测试结果

#### Scenario: 任一门禁失败
- **WHEN** 测试、迁移检查或包体预算失败
- **THEN** 验证命令非零退出，并标明失败门禁

### Requirement: 后端分层测试
必选后端测试 SHALL 覆盖纯领域规则、API/数据库集成、迁移升级/降级、调度器时间与生命周期，以及使用隔离 fixture 的行情适配器契约。

#### Scenario: 离线运行后端测试
- **WHEN** 以默认模式运行必选后端测试
- **THEN** 测试使用临时数据库、注入时钟和行情 fixture，不访问真实行情网络

#### Scenario: 核心流程回归
- **WHEN** 新建、刷新、触发、告警、确认平仓、仪表盘或设置违反规格
- **THEN** 至少一项必选自动化测试失败

#### Scenario: 可选真实行情冒烟测试
- **WHEN** 显式开启真实行情测试
- **THEN** 结果与离线必选门禁分开标记，并输出可操作的适配器诊断

### Requirement: 前端行为测试
必选前端测试 SHALL 覆盖 API 响应处理、生命周期展示、轮询间隔变化、计时器清理、部分刷新错误，以及使用确定性 mock 服务的关键用户流程。

#### Scenario: 轮询组件卸载
- **WHEN** 被测轮询视图卸载
- **THEN** fake timer 断言证明没有活动轮询计时器残留

#### Scenario: 刷新部分成功
- **WHEN** 前端收到成功和失败混合结果
- **THEN** 测试验证成功标的与失败标的被明确区分

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

### Requirement: 本地端到端冒烟测试
项目 SHALL 提供可复现的完全离线冒烟测试，使用隔离数据库、fixture provider 和 fixture calendar 启动后端与前端并验证核心 API 和触发流程。

#### Scenario: 完全离线冒烟成功
- **WHEN** 网络被阻断且项目依赖已安装
- **THEN** 冒烟测试在有界时间内完成并验证没有外部网络访问

#### Scenario: 冒烟启动或请求失败
- **WHEN** 服务启动、请求、触发或清理任一步失败
- **THEN** 命令返回非零退出码并输出可定位阶段

### Requirement: 前端生产包体预算
生产构建 SHALL 使用路由懒加载和 UI 按需导入，并对入口及路由产物执行文档化包体预算。

#### Scenario: 包体符合预算
- **WHEN** 所有构建产物均在配置阈值内
- **THEN** 包体门禁通过并报告产物大小

#### Scenario: 包体超出预算
- **WHEN** 任一入口或路由产物超过阈值
- **THEN** 包体门禁失败，除非以书面理由显式调整预算

### Requirement: Mount real frontend components
前端测试 SHALL 真实挂载页面与 store，覆盖首次加载、后台失败、筛选恢复、表单校验、权限降级和单资源单计时器行为。

#### Scenario: Background request fails
- **WHEN** 已有成功数据后的轮询请求失败
- **THEN** 组件保留成功数据并显示数据年龄与错误状态

### Requirement: Validate core journeys in target viewports
浏览器 E2E SHALL 在 390x844、768x1024 和 1440x900 覆盖创建、刷新、触发、确认、重新布防、部分平仓和关闭，并检测横向溢出、遮挡和文本截断。

#### Scenario: Mobile core journey
- **WHEN** 用户在 390x844 完成触发后的确认与重新布防
- **THEN** 所有控件可见可操作且固定导航不遮挡提交结果

### Requirement: Test extension isolation and security
测试套件 SHALL 验证投递失败不回滚核心事实、重复任务幂等、SSRF 目标被拒绝、密钥不出现在响应或日志，以及系统通知权限降级。

#### Scenario: Delivery fails after trigger
- **WHEN** Webhook 超时或返回失败
- **THEN** 测试证明触发、事件和站内告警仍已提交且没有敏感日志

### Requirement: Test import export and recovery boundaries
测试套件 SHALL 覆盖非法/超大 CSV、过期预览、公式注入、Decimal 往返、同秒多次备份、不兼容 manifest、损坏数据库和 readiness 自动恢复。

#### Scenario: Import commit partially fails
- **WHEN** 一个已预览批次在提交时违反领域约束
- **THEN** 整个导入事务回滚且返回稳定逐行错误

