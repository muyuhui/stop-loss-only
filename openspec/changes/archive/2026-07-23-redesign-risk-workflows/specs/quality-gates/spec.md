## ADDED Requirements

### Requirement: Mount real frontend components
前端测试 SHALL 真实挂载页面与 store，覆盖首次加载、后台失败、筛选恢复、表单校验、权限降级和单资源单计时器行为。

#### Scenario: Background request fails
- **WHEN** 已有成功数据后的轮询请求失败
- **THEN** 组件保留成功数据并显示数据年龄与错误状态

### Requirement: Validate core journeys in target viewports
浏览器 E2E SHALL 在 390x844、768x1024 和 1440x900 覆盖创建、刷新、触发、确认、重新布防、部分平仓和关闭，并检测横向溢出、遮挡和文本截断。

#### Scenario: Mobile core journey
- **WHEN** 用户在 390x844 完成触发后的确认与重新布防
- **THEN** 所有控件可见可操作且固定导航不遮挡提交结果
