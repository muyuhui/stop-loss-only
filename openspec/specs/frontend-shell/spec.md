# frontend-shell Specification

## Purpose
TBD - created by archiving change refine-frontend-experience. Update Purpose after archive.
## Requirements
### Requirement: 统一且克制的视觉语言
前端 SHALL 使用集中管理的语义化视觉变量统一页面背景、内容表面、文本层级、边框、圆角、阴影、间距和状态颜色，并限制风险颜色仅用于具有对应业务含义的内容。

#### Scenario: 在不同业务页面浏览
- **WHEN** 用户依次访问仪表盘、持仓、告警和设置页面
- **THEN** 页面使用一致的内容宽度、标题层级、面板样式、控件间距和状态颜色规则

#### Scenario: 展示金额和百分比
- **WHEN** 页面呈现金额、价格或百分比指标
- **THEN** 数字对齐稳定，正负符号可见，且含义不只依赖红色或绿色

### Requirement: 响应式应用外壳
前端 SHALL 在 360px 及以上视口中提供可用的主导航和内容布局，不产生页面级横向滚动，并在不同断点保持全部主入口可发现。

#### Scenario: 桌面宽度访问
- **WHEN** 视口宽度至少为 1024px
- **THEN** 顶部区域直接显示仪表盘、持仓管理、告警历史和设置四个主入口，不把设置隐藏为无名称的省略项

#### Scenario: 手机宽度访问
- **WHEN** 视口宽度介于 360px 和 767px
- **THEN** 页面使用适合触控的紧凑主导航，内容和固定导航均不造成页面级横向滚动

#### Scenario: 当前路由变化
- **WHEN** 用户在主页面之间导航
- **THEN** 当前入口通过文本以外的结构化选中状态清晰标识

### Requirement: 一致的异步状态反馈
数据页面 SHALL 区分首次加载、已有数据刷新、空数据、可恢复错误和数据过期状态，并避免在后台刷新期间清空已有内容。

#### Scenario: 首次加载数据
- **WHEN** 页面尚未取得第一次成功响应
- **THEN** 页面显示与最终结构匹配的加载状态，且不把零值误当成真实数据

#### Scenario: 后台刷新失败
- **WHEN** 页面已有成功数据但后续刷新失败
- **THEN** 页面保留最后成功数据，显示刷新失败和重试入口，并标识最后更新时间

#### Scenario: 数据持续未更新
- **WHEN** 距离最后成功刷新超过当前轮询间隔的两倍
- **THEN** 页面显示轻量的数据可能过期提示，而不是静默展示旧数据

#### Scenario: 空数据页面
- **WHEN** 请求成功但没有业务记录
- **THEN** 页面显示紧凑空状态，并在存在合理下一步时提供对应操作

### Requirement: 基础交互可访问性
前端 SHALL 为交互控件提供可访问名称、可见键盘焦点和一致中文文案，并为状态提供不依赖颜色的表达。

#### Scenario: 使用键盘浏览
- **WHEN** 用户使用键盘依次聚焦导航、按钮、表单和对话框控件
- **THEN** 焦点顺序符合页面任务顺序且当前焦点清晰可见

#### Scenario: 读取图标按钮
- **WHEN** 辅助技术读取告警铃铛、关闭或其他仅图标控件
- **THEN** 每个控件都暴露准确且唯一的中文可访问名称

#### Scenario: 展示风险状态
- **WHEN** 页面展示盈利、亏损、未读告警或临近止损状态
- **THEN** 状态同时包含文字、符号或图标提示，不仅通过颜色区分

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

### Requirement: Request privileged capabilities on demand
前端 SHALL 只在明确用户操作后请求系统通知、创建备份或选择导入文件，并显示已授权、已拒绝、不支持和失败状态。

#### Scenario: Page loads with notifications unset
- **WHEN** 用户首次打开设置且通知权限未决定
- **THEN** 页面不得自动请求权限，只显示解释和启用按钮

