## MODIFIED Requirements

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
