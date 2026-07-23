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
告警 SHALL 分别记录阅读状态和处置状态，并关联触发事件、规则快照、仓位快照及后续确认、重新布防或平仓事件。

#### Scenario: Alert is read without disposition
- **WHEN** 用户只标记告警已读
- **THEN** 阅读状态改变，但处置状态和仓位风险状态不变

#### Scenario: Position is rearmed
- **WHEN** 用户成功重新布防
- **THEN** 原告警处置状态关联为 `rearmed`，原快照保持不可变

### Requirement: Provide paginated actionable alert views
告警页面 SHALL 支持阅读状态、处置状态、日期、标的和类型筛选、稳定分页与 URL 上下文，并默认按未处理优先和时间倒序排列。

#### Scenario: More than one page of alerts
- **WHEN** 匹配告警超过一页
- **THEN** 用户可以访问后续页且筛选、总数和排序保持稳定

#### Scenario: No unresolved alerts
- **WHEN** “待处理”筛选没有匹配记录但历史告警存在
- **THEN** 页面显示筛选空状态而不是“从无告警”状态

### Requirement: Separate reading and disposition actions in UI
告警界面 SHALL 把标记已读、确认风险、重新布防和平仓显示为不同操作，并链接到对应仓位事件。

#### Scenario: Mark all read
- **WHEN** 用户执行全部已读
- **THEN** 页面只更新阅读计数，不把待处理告警标记为已处置

