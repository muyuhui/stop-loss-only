## MODIFIED Requirements

### Requirement: Create a holding
系统 SHALL 使用经过校验的资产和止损数据新建持仓，初始生命周期状态为 `holding`、行情状态为 `unpriced`，在首次可估值行情到达前将当前价及依赖当前价的收益率和止损距离返回为不可用，同时将最高价初始化为买入价并计算、保存、返回止损价。

#### Scenario: 新建固定止损股票
- **WHEN** 用户提交代码 `000001`、买入价 `10.00`、固定止损值 `9.00`
- **THEN** 数据库和响应中的状态为 `holding`、行情状态为 `unpriced`、最高价为 `10.00`、止损价为 `9.00`，当前价、收益率和止损距离为不可用

#### Scenario: 新建百分比止损基金
- **WHEN** 用户提交买入价 `2.50`、百分比止损值 `10`
- **THEN** 数据库和响应中的止损价为 `2.25`，且买入成本不被表示为当前行情

#### Scenario: 新建移动止损持仓
- **WHEN** 用户提交 `{type: "stock", stop_loss_method: "trailing", stop_loss_value: 8}`
- **THEN** 系统创建新持仓，其 `stop_loss_method` 为 `trailing`、`stop_loss_value` 为 `8`，行情状态为 `unpriced`

#### Scenario: 新建数据非法
- **WHEN** 缺少必填字段或止损校验失败
- **THEN** 系统返回 422，且不创建持仓

### Requirement: Get holding detail
系统 SHALL 返回单笔持仓的完整持久化详情，包括止损价、行情元数据、生命周期状态以及在可计算时返回的收益率和止损距离；依赖缺失行情的派生值 MUST 返回不可用而非数字零。

#### Scenario: 查询存在的已定价持仓
- **WHEN** 用户查询已存在且拥有可估值行情的 ID
- **THEN** 详情中的止损价和派生字段与列表、仪表盘中的同一快照一致

#### Scenario: 查询未定价持仓
- **WHEN** 用户查询尚未取得可估值行情的持仓
- **THEN** 当前价、收益率和止损距离返回 `null`，同时保留买入成本、止损价和 `unpriced` 行情状态

#### Scenario: 查询不存在的持仓
- **WHEN** 用户查询未知 ID
- **THEN** 系统返回 404

## ADDED Requirements

### Requirement: 显示未知的行情派生指标
持仓列表、详情和仪表盘 SHALL 对不可用的当前价、收益率和止损距离使用明确中文未知状态，MUST NOT 将 `null` 经数值转换显示为 `0.00%`、临近止损或安全距离。已触发生命周期仍 SHALL 优先显示已触发事实。

#### Scenario: 列表展示未定价持仓
- **WHEN** 持仓响应中的收益率和止损距离为 `null`
- **THEN** 桌面表格和移动卡片显示“未定价”及“风险未知”，该持仓不参与已知止损距离排序

#### Scenario: 详情展示未定价持仓
- **WHEN** 用户打开尚未取得可估值行情的持仓详情
- **THEN** 风险摘要显示不可用百分比和“风险未知”，且不会使用危险或安全文案表达虚构距离
