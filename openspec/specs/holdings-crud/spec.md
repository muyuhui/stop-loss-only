# Holdings CRUD

## Purpose

Manage investment holdings (A-share stocks and funds) with create, read, update, delete, and manual close operations.
## Requirements
### Requirement: Create a holding
系统 SHALL 使用经过校验的资产和止损数据新建持仓，初始状态为 `holding`，在首次行情到达前把现价和最高价设为买入价，并计算、保存、返回止损价。

#### Scenario: 新建固定止损股票
- **WHEN** 用户提交代码 `000001`、买入价 `10.00`、固定止损值 `9.00`
- **THEN** 数据库和响应中的状态为 `holding`、最高价为 `10.00`、止损价为 `9.00`

#### Scenario: 新建百分比止损基金
- **WHEN** 用户提交买入价 `2.50`、百分比止损值 `10`
- **THEN** 数据库和响应中的止损价为 `2.25`

#### Scenario: Create holding with trailing stop-loss
- **WHEN** user submits {type: "stock", stop_loss_method: "trailing", stop_loss_value: 8}
- **THEN** a new holding is created with stop_loss_method "trailing" and stop_loss_value 8

#### Scenario: 新建数据非法
- **WHEN** 缺少必填字段或止损校验失败
- **THEN** 系统返回 422，且不创建持仓

### Requirement: List all holdings
系统 SHALL 按创建时间和 ID 倒序返回稳定分页结果，支持经过校验的生命周期状态筛选，并返回一致的派生字段。

#### Scenario: 使用默认分页
- **WHEN** 用户不带分页参数请求 `GET /api/holdings`
- **THEN** 响应包含首页以及 `items`、`total`、`page`、`size`

#### Scenario: 请求后续页
- **WHEN** 用户提交有效 page 和 size
- **THEN** items 只包含对应切片，total 表示全部匹配记录数

#### Scenario: 按状态筛选
- **WHEN** 用户提交已识别的生命周期状态
- **THEN** 只统计并返回该状态持仓

#### Scenario: 分页或状态非法
- **WHEN** page、size 或 status 超出约定范围
- **THEN** 系统返回 422

### Requirement: Get holding detail
系统 SHALL 返回单笔持仓的完整持久化详情，包括止损价、行情元数据、生命周期状态、收益率和止损距离。

#### Scenario: 查询存在的持仓
- **WHEN** 用户查询已存在的 ID
- **THEN** 详情中的止损价和派生字段与列表、仪表盘中的同一快照一致

#### Scenario: 查询不存在的持仓
- **WHEN** 用户查询未知 ID
- **THEN** 系统返回 404

### Requirement: Update holding
系统 SHALL 校验允许修改的元数据和止损参数，原子地重新计算并保存派生止损价，并按生命周期限制修改。

#### Scenario: 修改止损方式
- **WHEN** 用户把活动持仓从固定止损改为有效的移动止损
- **THEN** 系统保存并返回新方式、参数和重算后的止损价

#### Scenario: 修改已触发或已关闭持仓
- **WHEN** 用户修改 `triggered` 或 `closed` 持仓的止损设置
- **THEN** 系统返回 400，持仓不变化

#### Scenario: 修改校验失败
- **WHEN** 现有字段与提交字段组合后无效
- **THEN** 系统返回 422，所有提交字段均不保存

### Requirement: Delete a holding
系统 SHALL 删除生命周期规则允许删除的持仓，保留独立告警快照，并返回无响应体的 HTTP 204。

#### Scenario: 成功删除持仓
- **WHEN** 用户删除允许删除的持仓
- **THEN** 持仓被移除、历史告警仍可读取，响应为无正文 204

#### Scenario: 删除不存在的持仓
- **WHEN** 用户删除未知 ID
- **THEN** 系统返回 404

### Requirement: Manually close a holding
系统 SHALL 允许用户以有效平仓价确认关闭 `holding` 或 `triggered` 持仓，且不额外创建止损告警。

#### Scenario: 手动关闭活动持仓
- **WHEN** 用户为 `holding` 提交有效平仓价
- **THEN** 状态变为 `closed`，保存平仓价，且不创建触发告警

#### Scenario: 触发后确认关闭
- **WHEN** 用户为 `triggered` 提交有效平仓价
- **THEN** 状态变为 `closed`，已有触发告警保持不变

#### Scenario: 重复关闭
- **WHEN** 用户尝试关闭 `closed` 持仓
- **THEN** 系统返回 400，持仓不变化

### Requirement: 响应式持仓列表
前端 SHALL 根据可用宽度展示易扫描的持仓列表，组合相关字段并完整保留持仓状态、当前价格、盈亏、止损价和止损距离等核心信息。

#### Scenario: 桌面端查看持仓
- **WHEN** 用户在至少 768px 宽的视口打开持仓管理页
- **THEN** 页面使用精简表格组合名称与代码、当前价与盈亏、止损价与距离，并提供明确的详情入口

#### Scenario: 手机端查看持仓
- **WHEN** 用户在 360px 到 767px 宽的视口打开持仓管理页
- **THEN** 页面使用纵向持仓卡片展示全部核心信息，不要求用户横向滚动表格才能查看状态或进入详情

#### Scenario: 持仓列表为空
- **WHEN** 持仓列表请求成功但 items 为空
- **THEN** 页面显示紧凑空状态和“新增持仓”操作

### Requirement: 精简的持仓详情
前端 SHALL 在详情页集中展示当前价、盈亏、止损价、止损距离和生命周期状态，并避免在多个只读面板重复展示同一止损方式与参数。

#### Scenario: 查看活动持仓详情
- **WHEN** 用户打开状态为 `holding` 的持仓
- **THEN** 首屏可见风险和收益摘要，止损配置只在一个主要区域展示并可进入编辑

#### Scenario: 刷新单笔持仓价格
- **WHEN** 用户激活详情页中命名为刷新价格的操作
- **THEN** 前端在当前上下文调用实际价格刷新能力并反馈结果，不以刷新名义仅跳转到设置页面

#### Scenario: 手机端查看详情
- **WHEN** 用户在 360px 到 767px 宽的视口查看持仓详情
- **THEN** 摘要、止损设置和平仓区域使用单列布局，主要信息和操作无需横向滚动

### Requirement: 清晰的持仓操作层级
前端 SHALL 将编辑、价格刷新、手动平仓和删除按照风险等级分组，删除操作必须位于独立危险区域并继续要求确认。

#### Scenario: 手动平仓
- **WHEN** 用户为活动持仓输入有效平仓价
- **THEN** 页面将手动平仓作为明确业务操作，提交期间阻止重复请求，并在成功后刷新生命周期状态

#### Scenario: 删除持仓
- **WHEN** 用户进入删除操作
- **THEN** 删除与常规操作视觉隔离，确认内容明确说明不可撤销，取消确认不会改变持仓

### Requirement: 响应式持仓表单
新增和编辑持仓表单 SHALL 在桌面端高效分组，在窄屏下改为单列，并为止损参数提供随方式变化的单位、示例、校验和提交状态。

#### Scenario: 手机端新增持仓
- **WHEN** 用户在 360px 到 767px 宽的视口打开新增持仓表单
- **THEN** 对话框不超出视口，字段按单列排列，保存和取消操作可见且可触控

#### Scenario: 切换止损方式
- **WHEN** 用户在固定价格、百分比和移动止损之间切换
- **THEN** 参数单位、帮助文本和精度规则同步变化，且不会让旧方式的解释继续显示

#### Scenario: 提交处理中
- **WHEN** 新增、编辑或平仓请求尚未完成
- **THEN** 对应提交按钮显示加载状态并阻止重复提交

