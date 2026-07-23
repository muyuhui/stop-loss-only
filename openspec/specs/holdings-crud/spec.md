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

### Requirement: 响应式持仓价格与止损图表
前端 SHALL 在持仓详情风险摘要之后展示日级价格走势、买入基准、按当前规则计算的止损线和触发标记，并在不同视口中保持内容可读、操作简单且风险含义不只依赖颜色。

#### Scenario: 默认查看价格走势
- **WHEN** 用户打开存在历史行情的持仓详情
- **THEN** 页面默认展示近 3 个月价格折线、买入价虚线、止损线、最新价格以及包含数据来源和最后交易日期的文字摘要

#### Scenario: 切换时间范围
- **WHEN** 用户在 1 月、3 月、6 月和 1 年之间切换
- **THEN** 图表加载对应受支持范围，保留持仓主体内容，并明确反馈加载或失败状态

#### Scenario: 查看移动止损
- **WHEN** 当前持仓使用移动止损
- **THEN** 止损线以阶梯形式只向上移动，图表说明其为按当前止损规则计算的序列

#### Scenario: 查看固定或百分比止损
- **WHEN** 当前持仓使用固定价格或百分比止损
- **THEN** 图表显示水平止损线并在其下方使用低干扰风险区域，同时以文字标明止损价格

#### Scenario: 手机端查看图表
- **WHEN** 用户在 360px 到 767px 宽的视口查看持仓详情
- **THEN** 图表和范围控件不产生页面级横向滚动，触控提示可读取日期、价格和止损价，且文字摘要完整可见

#### Scenario: 历史行情刷新失败
- **WHEN** 页面已有历史数据但后续更新失败
- **THEN** 页面保留已有图表并显示缓存或过期提示及重试入口，不将持仓详情误显示为空

#### Scenario: 暂无历史行情
- **WHEN** 历史接口成功但没有可展示的价格点
- **THEN** 图表区域显示紧凑空状态和重试操作，不影响用户修改止损、刷新当前价格或平仓

### Requirement: Keep lifecycle risk and quantity facts orthogonal
系统 SHALL 分别记录 `lifecycle_status`、`risk_status` 和剩余数量；部分平仓 MUST 由平仓分配与剩余数量推导，不得作为覆盖风险状态的单一组合状态。

#### Scenario: Triggered position is partially closed
- **WHEN** 已触发仓位只关闭部分数量且用户尚未重新布防
- **THEN** 仓位仍为 `lifecycle_status=open` 和 `risk_status=triggered`，同时保存部分平仓事实

### Requirement: Add lots and close positions
系统 SHALL 允许向开放仓位添加有效批次，并允许以有效数量、价格、时间、费用和税费部分或全部平仓；所有财务变更必须原子且创建事件。

#### Scenario: Add lot to closed position
- **WHEN** 用户尝试向已关闭仓位增加批次
- **THEN** 系统拒绝请求且不修改任何财务事实

#### Scenario: Close more than remaining quantity
- **WHEN** 平仓数量大于总剩余数量
- **THEN** 系统返回稳定校验错误且不创建 allocation

### Requirement: Present closed positions as realized outcomes
系统 SHALL 为关闭仓位返回净已实现收益、费用税费、持有期和历史事件，并停止返回可编辑的活动止损控件语义。

#### Scenario: View closed position detail
- **WHEN** 用户查询已关闭仓位
- **THEN** 响应以已实现结果为主且不使用最新行情计算未实现盈亏

### Requirement: Provide stable position list context
仓位页面 SHALL 使用新版 positions API 提供搜索、生命周期、风险、资产类型和行情状态筛选、排序与分页，并将列表上下文同步到 URL query。

#### Scenario: Return from position detail
- **WHEN** 用户从详情返回仓位列表
- **THEN** 搜索、筛选、排序和页码恢复到离开前状态

### Requirement: Provide complete position disposition workflows
仓位详情 SHALL 展示可行动行情、核算摘要、批次、规则和事件，并为触发仓位提供风险确认、重新布防和记录平仓的独立流程。

#### Scenario: Triggered position on mobile
- **WHEN** 用户在移动端打开已触发仓位
- **THEN** 固定处置区可达且三个动作不与“标记已读”混淆

#### Scenario: Closed position review
- **WHEN** 用户打开已关闭仓位
- **THEN** 页面进入复盘模式，隐藏刷新和止损编辑并展示已实现结果与时间线

