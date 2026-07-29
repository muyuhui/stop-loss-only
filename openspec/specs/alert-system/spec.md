# Alert System

## Purpose

Automatically generate alerts when stop-loss triggers, notify via browser popup, and manage read status.
## Requirements
### Requirement: Create alert on stop-loss trigger
系统 SHALL 对每个持仓触发生命周期原子地创建至多一个告警，并保存持仓代码、名称、触发价、现价、行情时间、来源、未读状态和创建时间快照。

#### Scenario: 首次触发创建告警
- **WHEN** 新鲜有效行情首次使持仓从 `holding` 变为 `triggered`
- **THEN** 系统创建一个未读告警，并保存后续可独立解释该告警所需的持仓与行情快照

#### Scenario: 重复判断同一触发
- **WHEN** 调度器重试或并发刷新再次处理已触发持仓
- **THEN** 服务层和数据库幂等约束共同阻止重复告警

#### Scenario: 后续删除持仓
- **WHEN** 告警产生后源持仓被删除
- **THEN** 告警仍保留持仓名称、代码、价格和行情元数据

### Requirement: List alerts
系统 SHALL 按创建时间倒序返回分页告警列表，并使用告警自身快照，不依赖仍然存在的持仓记录。

#### Scenario: 查询全部告警
- **WHEN** 用户请求 `GET /api/alerts`
- **THEN** 系统按创建时间倒序返回告警快照及分页元数据

#### Scenario: 筛选未读告警
- **WHEN** 用户请求 `GET /api/alerts?unread=true`
- **THEN** 系统只返回未读状态为真的告警

### Requirement: Mark alert as read
The system SHALL allow users to mark an alert as read.

#### Scenario: Mark single alert as read
- **WHEN** user requests PUT /api/alerts/{id}/read
- **THEN** the alert's read field SHALL be set to true

#### Scenario: Mark all alerts as read
- **WHEN** user requests PUT /api/alerts/read-all
- **THEN** all alerts with read=false SHALL be set to read=true

### Requirement: Count unread alerts
The system SHALL provide the count of unread alerts for the dashboard and browser notification badge.

#### Scenario: Get unread count
- **WHEN** user requests GET /api/alerts/count
- **THEN** system returns the number of alerts with read=false

### Requirement: Browser notification for new alert
The frontend SHALL poll for unread alerts at a configurable interval and display a browser notification when new alerts are detected.

#### Scenario: New alert detected via polling
- **WHEN** the frontend polls GET /api/alerts/count and the count increases
- **THEN** a notification popup displays the alert details (holding name, trigger price, current price)

#### Scenario: No new alerts
- **WHEN** the frontend polls and no new alerts are found
- **THEN** no notification is shown

### Requirement: 清晰且响应式的告警历史
前端 SHALL 以未读优先且适合当前视口的结构展示告警快照，明确区分未读、已读和空状态，并保证单条及批量已读操作的可用性。

#### Scenario: 桌面端存在告警
- **WHEN** 用户在至少 768px 宽的视口打开包含已读和未读记录的告警历史
- **THEN** 页面使用易扫描列表展示持仓、触发价、当前价、时间和阅读状态，未读含义不只依赖背景颜色

#### Scenario: 手机端存在告警
- **WHEN** 用户在 360px 到 767px 宽的视口打开告警历史
- **THEN** 每条告警以纵向摘要完整展示持仓、价格、时间和状态，不要求横向滚动

#### Scenario: 没有告警
- **WHEN** 告警请求成功但 items 为空
- **THEN** 页面显示紧凑的“暂无告警”状态，并禁用或隐藏无意义的全部已读操作

#### Scenario: 标记全部已读
- **WHEN** 页面存在未读告警且用户激活全部已读
- **THEN** 操作期间阻止重复提交，成功后同步更新列表和全局未读数量

### Requirement: Track alert disposition separately from read state
告警 SHALL 分别记录阅读状态和处置状态，并关联可用的触发事件、规则快照、持仓快照及后续处置事实。在 legacy 稳定运行面，新触发告警 SHALL 记录 `triggered` 处置状态，手动关闭相关持仓 SHALL 在同一业务事务中将仍待处理的关联告警更新为 `closed`。

#### Scenario: 阅读告警不改变处置状态
- **WHEN** 用户只标记告警已读
- **THEN** 阅读状态改变，但处置状态和持仓风险状态不变

#### Scenario: 手动关闭 legacy 持仓
- **WHEN** 用户成功手动关闭一个已经触发告警的 legacy 持仓
- **THEN** 持仓关闭和相关待处理告警的 `closed` 处置状态一起提交，告警价格与触发快照保持不变

#### Scenario: 历史告警没有处置状态
- **WHEN** 稳定 API 读取迁移前处置状态为 `null` 的 legacy 告警
- **THEN** 列表和 `triggered` 筛选将其一致解释为待处理的 `triggered`，且不修改阅读状态

#### Scenario: Position 被重新布防
- **WHEN** 后续受支持运行面成功重新布防 Position
- **THEN** 原告警处置状态关联为 `rearmed`，原快照保持不可变

### Requirement: Provide paginated actionable alert views
告警页面 SHALL 支持基于告警快照名称或代码的服务端搜索、已读/未读状态筛选、稳定处置状态筛选、稳定分页与 URL 上下文，并按创建时间及 ID 倒序排列。稳定 UI MUST NOT 显示未被查询契约执行的生命周期、风险或排序控件。

#### Scenario: 告警超过一页
- **WHEN** 匹配告警超过一页
- **THEN** 用户可以访问后续页且搜索、筛选、总数和倒序排列保持稳定

#### Scenario: 搜索告警快照
- **WHEN** 用户按持仓名称片段或代码搜索告警
- **THEN** 服务端在分页前筛选不可变告警快照并返回匹配总数

#### Scenario: 明确筛选已读告警
- **WHEN** 用户选择已读状态
- **THEN** 请求明确提交 `unread=false` 且只返回已读告警

#### Scenario: 筛选待处理的 legacy 告警
- **WHEN** 用户选择待处理处置状态
- **THEN** 系统返回处置状态为 `triggered` 或历史兼容空值的告警

#### Scenario: 没有待处理告警
- **WHEN** 待处理筛选没有匹配记录但历史告警存在
- **THEN** 页面显示筛选空状态而不是“从无告警”状态

#### Scenario: 移动端告警筛选
- **WHEN** 用户在 390px 宽视口打开告警页面
- **THEN** 页面只显示搜索、阅读状态和处置状态控件，使用中文当前值且不产生横向滚动

### Requirement: Separate reading and disposition actions in UI
告警界面 SHALL 将标记已读与持仓处置清楚分开。在本 legacy 稳定版本中，告警的处置入口 SHALL 指向已注册的 `/holdings/:holding_id` 详情，由该页面提供受支持的手动平仓操作；界面 MUST NOT 导航到未注册的 position 路由或显示未支持的确认、重新布防和部分平仓命令。

#### Scenario: 查看带 shadow Position 元数据的告警
- **WHEN** 告警同时包含 `holding_id` 和 shadow `position_id`
- **THEN** 稳定界面的处置入口使用 `holding_id` 打开可达的持仓详情

#### Scenario: 将告警标记为已读
- **WHEN** 用户把告警标记为已读
- **THEN** 系统只更新阅读状态，不关闭持仓或改变触发事实

