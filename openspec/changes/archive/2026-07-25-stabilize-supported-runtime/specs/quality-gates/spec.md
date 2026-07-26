## MODIFIED Requirements

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

### Requirement: 本地端到端冒烟测试
项目 SHALL 提供可复现的完全离线 API 与进程冒烟测试，使用隔离数据库、fixture provider 和 fixture calendar 启动后端与构建后的前端静态服务，验证核心 legacy API、触发流程、服务清理和构建产物可服务。该测试 MUST 明确报告为 API/进程 smoke，而不是浏览器交互 E2E。

#### Scenario: 完全离线冒烟成功
- **WHEN** 网络被阻断且项目依赖已安装
- **THEN** 冒烟测试在有界时间内完成 legacy 创建、刷新、触发、告警、关闭和进程清理

#### Scenario: 冒烟启动或请求失败
- **WHEN** 服务启动、请求、触发或清理任一步失败
- **THEN** 命令返回非零退出码并输出可定位阶段

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
