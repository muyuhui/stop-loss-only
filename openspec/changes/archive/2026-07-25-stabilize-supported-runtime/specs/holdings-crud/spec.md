## ADDED Requirements

### Requirement: 使用 legacy 持仓工作流作为稳定版本运行面
本稳定版本 SHALL 使用 `/api/holdings` 支持创建、列表、详情、止损修改、手动平仓和允许的删除操作，并保证每个成功创建的活动持仓都能出现在列表、仪表盘和行情监控范围中。前端 MUST NOT 把未完成的 position-only 操作显示为稳定能力。

#### Scenario: 创建受支持持仓
- **WHEN** 用户通过稳定持仓表单创建有效持仓
- **THEN** 记录由 `Holding` 权威模型保存，并可立即通过列表、详情和监控查询

#### Scenario: 尝试未支持的 Position 写入
- **WHEN** 客户端在本稳定版本直接调用 position-only 创建、加仓、部分平仓、确认或重新布防操作
- **THEN** 系统拒绝写入并返回稳定的 `feature_not_supported` 错误

## REMOVED Requirements

### Requirement: Keep lifecycle risk and quantity facts orthogonal
**Reason**: 该要求属于已推迟的 Position 权威领域，不是 legacy 版本面向用户的稳定契约。

**Migration**: 保留 shadow 表和领域代码，等待未来 Position 切换 change 使用。

### Requirement: Add lots and close positions
**Reason**: Position 批次和部分平仓写入会在受支持监控权威模型之外创建事实。

**Migration**: 在 Position 监控和前端流程共同完成前，继续使用 legacy 整笔持仓关闭流程。

### Requirement: Present closed positions as realized outcomes
**Reason**: 当前稳定 UI 展示已关闭的 legacy 持仓，而不是 Position 分配与事件。

**Migration**: 继续使用冻结的持仓关闭事实；在未来切换 change 中恢复 Position 结果要求。

### Requirement: Provide stable position list context
**Reason**: Position 列表路由及其筛选工作流不属于当前受支持版本。

**Migration**: 使用稳定持仓列表，并将未来 Position 工作流保留在路线图中。

### Requirement: Provide complete position disposition workflows
**Reason**: 风险确认、重新布防、批次和部分平仓工作流尚未与当前监控权威模型集成。

**Migration**: 在完整 Position 工作流重新引入前，使用告警查看、legacy 持仓详情和手动关闭。
