## ADDED Requirements

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
