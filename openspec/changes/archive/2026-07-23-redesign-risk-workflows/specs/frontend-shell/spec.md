## ADDED Requirements

### Requirement: Use distinct risk and trust semantics
前端 SHALL 分别表达监控健康、行情可行动性、业务风险和财务盈亏，所有状态 MUST 同时使用文本、图标、符号或结构而不是只依赖颜色。

#### Scenario: Profit and danger are both red
- **WHEN** 页面同时显示正收益和已触发危险状态
- **THEN** 正收益带正号且危险带标签/图标，用户无需仅凭红色区分

### Requirement: Format financial values consistently
前端 SHALL 使用共享格式化组件显示后端 Decimal 字符串、千分位、带符号百分比、资产数量精度和不可用值，MUST NOT 在浏览器执行财务核算。

#### Scenario: Decimal value is unavailable
- **WHEN** API 返回未覆盖或不可行动值
- **THEN** 页面显示明确不可用语义，不显示零或 NaN

### Requirement: Preserve responsive accessibility
前端 SHALL 支持最低 360px 宽度、44px 移动触控目标、键盘操作、焦点管理、减少动画偏好和不会遮挡内容的安全区。

#### Scenario: Full-screen mobile form
- **WHEN** 用户在移动端编辑重新布防或平仓表单
- **THEN** 表单接近全屏、焦点可见且提交操作不被底部导航遮挡
