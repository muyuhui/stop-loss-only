# Quality Gates

## Purpose

为项目建立可复现、默认离线且能够阻止回归进入发布状态的质量门禁，统一后端、前端、数据库迁移、端到端冒烟和生产包体的验证标准，并明确真实行情测试与必选确定性测试之间的边界。
## Requirements
### Requirement: 可复现的验证命令
项目 SHALL 提供非交互验证命令，在依赖已经按 lockfile 准备好的干净环境中执行后端测试、前端行为测试、生产构建、API/进程冒烟、真实浏览器 E2E、备份恢复检查和全部当前 OpenSpec 严格校验。命令 SHALL 使用本次运行独立的临时目录，任一依赖缺失或门禁失败都必须非零退出并标明阶段。

#### Scenario: 所有门禁连续通过
- **WHEN** 在准备好的干净环境连续运行两次验证命令
- **THEN** 两次均成功退出且不受上次 pytest、构建、端口或临时目录状态影响

#### Scenario: 前端直接依赖缺失
- **WHEN** lockfile 声明的直接依赖未完整安装
- **THEN** 验证在运行测试前或对应前端阶段非零退出并提示重新执行 setup

#### Scenario: 主规格无 active change
- **WHEN** 当前不存在其他 active change
- **THEN** 验证仍严格校验全部主规格而不是成功验证零个项目

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
项目 SHALL 提供可复现的完全离线 API 与进程冒烟测试，使用隔离数据库、fixture provider 和 fixture calendar 启动后端与构建后的前端静态服务，验证核心 legacy API、触发流程、服务清理和构建产物可服务。该测试 MUST 明确报告为 API/进程 smoke，而不是浏览器交互 E2E。

#### Scenario: 完全离线冒烟成功
- **WHEN** 网络被阻断且项目依赖已安装
- **THEN** 冒烟测试在有界时间内完成 legacy 创建、刷新、触发、告警、关闭和进程清理

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
前端测试 SHALL 真实挂载 Dashboard、Holdings、HoldingDetail、Alerts 和 Settings 及其实际 store/router 集成，覆盖首次加载、后台失败、URL 恢复、表单、稳定导航和单资源单计时器行为。源码字符串断言 MUST NOT 作为这些行为的唯一证据。

#### Scenario: 告警包含 shadow Position ID
- **WHEN** 真实挂载的告警页面收到同时含 holding 和 shadow position 标识的响应
- **THEN** 点击处置入口进入已注册 holding 路由

#### Scenario: 后台请求失败
- **WHEN** 已有成功数据后的轮询请求失败
- **THEN** 组件保留成功数据并显示数据年龄与错误状态

### Requirement: Validate core journeys in target viewports
浏览器 E2E SHALL 在 `390x844`、`768x1024` 和 `1440x900` 使用构建后的前端与 fixture 后端覆盖 legacy 创建、刷新、触发、告警查看、持仓详情和手动关闭，并检测未匹配路由、横向溢出、固定导航遮挡、关键文本截断和未捕获浏览器错误。

#### Scenario: 移动端 legacy 流程
- **WHEN** 用户在 `390x844` 完成创建、触发、从告警进入持仓详情并关闭
- **THEN** 所有控件可见可操作、底部导航不遮挡结果且最终关闭状态可确认

#### Scenario: 未支持控件保持隐藏
- **WHEN** 浏览器遍历三个目标视口的稳定页面
- **THEN** 页面不显示 position-only、CSV、Webhook、retention 或浏览器系统通知命令

### Requirement: Test extension isolation and security
测试套件 SHALL 验证已推迟扩展在 UI、HTTP 和后台任务层均 fail closed，同时证明站内告警、核心持仓和备份恢复不依赖这些扩展。直接调用禁用入口 MUST 不写入 Position、DeliveryAttempt、ImportAudit、密钥或配置状态。

#### Scenario: 直接请求已停用扩展
- **WHEN** 测试直接调用 CSV 提交或 Webhook 启用入口
- **THEN** 系统返回稳定拒绝且数据库敏感表和核心事实不变

### Requirement: Test import export and recovery boundaries
测试套件 SHALL 证明 CSV 导入导出在本稳定版本不可达，并覆盖同秒多次备份、不兼容 manifest、损坏数据库、恢复点和 readiness 自动回滚。禁用的 CSV 请求不得产生预览令牌、审计或业务记录。

#### Scenario: 恢复校验失败
- **WHEN** checksum、schema 或 SQLite 完整性校验失败
- **THEN** 恢复非零退出、活动数据库保持不变且恢复点仍可验证

#### Scenario: 直接调用 CSV 接口
- **WHEN** 客户端绕过前端调用禁用的 CSV 入口
- **THEN** 请求稳定失败且不创建任何预览、审计、Holding 或 Position

### Requirement: 验证能力感知的运行时边界
强制测试 SHALL 在真实集成边界上验证运行时能力、应用就绪状态、前端降级、休市监控语义和恢复清理，而不是只在隔离的路由测试中证明互相矛盾的行为。

#### Scenario: 稳定的旧版应用
- **WHEN** 真实应用使用 `legacy` 数据库启动
- **THEN** 就绪检查成功，能力只声明受支持的工作流，稳定界面不请求不可用的风险接口，也不产生通用能力错误提示

#### Scenario: 不受支持的新权威应用
- **WHEN** 真实应用使用 `new-authoritative` 数据库启动
- **THEN** 存活检查成功，就绪检查以稳定的权威阶段原因失败，能力发现不会将未完成的运行时声明为受支持

#### Scenario: 休市诊断
- **WHEN** 权威交易日历测试数据在较早的成功行情周期之后报告休市
- **THEN** 后端和前端测试验证中性的休市状态，以及相互独立的可操作覆盖率和估值覆盖率

#### Scenario: 恢复流程不遗留工作数据库
- **WHEN** 恢复测试覆盖成功路径和注入故障路径
- **THEN** 每条路径都验证活动数据库、恢复点以及恢复工作副本不存在

#### Scenario: 完整质量门禁可重复运行
- **WHEN** 本变更完成后连续两次运行完整验证命令
- **THEN** 两次运行均通过，且残留端口、浏览器进程、测试数据库或恢复工作文件不会影响第二次运行

