## ADDED Requirements

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
