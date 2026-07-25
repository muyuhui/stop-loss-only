## MODIFIED Requirements

### Requirement: Separate reading and disposition actions in UI
告警界面 SHALL 将标记已读与持仓处置清楚分开。在本 legacy 稳定版本中，告警的处置入口 SHALL 指向已注册的 `/holdings/:holding_id` 详情，由该页面提供受支持的手动平仓操作；界面 MUST NOT 导航到未注册的 position 路由或显示未支持的确认、重新布防和部分平仓命令。

#### Scenario: 查看带 shadow Position 元数据的告警
- **WHEN** 告警同时包含 `holding_id` 和 shadow `position_id`
- **THEN** 稳定界面的处置入口使用 `holding_id` 打开可达的持仓详情

#### Scenario: 将告警标记为已读
- **WHEN** 用户把告警标记为已读
- **THEN** 系统只更新阅读状态，不关闭持仓或改变触发事实
