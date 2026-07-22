## ADDED Requirements

### Requirement: Use a risk-and-trust information hierarchy
前端 SHALL 在所有业务页面优先表达数据可信度和待处理风险，再展示收益和次要详情；监控健康与投资风险必须使用不同标签和文案语义。

#### Scenario: Monitoring is degraded but no stop is triggered
- **WHEN** 最近监控周期失败但没有已触发仓位
- **THEN** 页面显示“监控降级”而不是“组合风险危险”，并提供诊断入口

#### Scenario: Stop is triggered with healthy monitoring
- **WHEN** 行情可信且一个仓位已经触发
- **THEN** 页面分别显示监控健康和业务风险触发，不把两者合并成模糊红色状态

### Requirement: Provide consistent filter and density behavior
列表页面 SHALL 使用一致的搜索、筛选、排序、分页和空筛选结果模式，筛选状态 SHALL 写入 URL query，桌面端和移动端 SHALL 分别使用适合其密度的表格和卡片。

#### Scenario: Return to a filtered list
- **WHEN** 用户从筛选后的持仓列表进入详情再返回
- **THEN** 搜索、筛选、排序和页码从 URL 恢复

#### Scenario: Filter returns no records
- **WHEN** 数据存在但当前筛选无匹配结果
- **THEN** 页面显示“没有符合条件的结果”和清除筛选操作，而不是显示首次使用空状态

#### Scenario: Desktop dense table
- **WHEN** 用户在至少 1024px 视口查看包含多条数据的列表
- **THEN** 页面使用稳定行高和可隐藏次要列，不把每条记录渲染为大型装饰卡片

### Requirement: Format financial values consistently
前端 SHALL 对金额使用千分位，对盈亏使用显式正负号和中国市场颜色习惯，对行情与风险状态同时使用文本或图标，并使用稳定的数字宽度。

#### Scenario: Display positive profit
- **WHEN** 已实现或未实现收益为正
- **THEN** 页面显示红色、`+` 号和盈利语义，不只依赖颜色

#### Scenario: Display dangerous stop state
- **WHEN** 仓位已经触发止损
- **THEN** 页面使用危险图标、标签和文字，避免与盈利红色仅靠颜色区分

### Requirement: Preserve responsive accessibility
前端 SHALL 在 360px 及以上视口提供无横向溢出的页面、至少 44px 的主要触控目标、可见键盘焦点、可访问名称、合理标题层级和不遮挡内容的固定导航。

#### Scenario: Mobile bottom navigation
- **WHEN** 页面内容滚动到最后一项
- **THEN** 最后一项和其操作位于底部导航及安全区之上且可完整激活

#### Scenario: Full-screen mobile form
- **WHEN** 用户在手机端编辑复杂仓位或重新布防表单
- **THEN** 表单使用接近全屏的 sheet，提交操作保持可见，错误与对应字段关联

#### Scenario: Reduced motion preference
- **WHEN** 系统启用减少动态效果偏好
- **THEN** 非必要过渡和动画被关闭，状态变化仍可理解

### Requirement: Request privileged browser capabilities on demand
前端 SHALL 只在用户明确操作后请求通知等浏览器权限，并展示授权、拒绝和不支持状态。

#### Scenario: Page loads with notifications unset
- **WHEN** 用户首次打开应用且未配置系统通知
- **THEN** 页面不得自动弹出浏览器权限请求
