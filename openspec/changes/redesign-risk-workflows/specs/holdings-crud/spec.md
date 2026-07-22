## ADDED Requirements

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
