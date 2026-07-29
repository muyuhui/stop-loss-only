## MODIFIED Requirements

### Requirement: Format financial values consistently
前端 SHALL 使用共享格式化组件显示后端 Decimal 字符串、千分位、带符号百分比、资产数量精度和不可用值，MUST NOT 在浏览器执行财务核算，也 MUST NOT 将 `null`、`undefined` 或空字符串通过数值强制转换显示为零。

#### Scenario: Decimal 值不可用
- **WHEN** API 返回未覆盖或不可行动值
- **THEN** 页面显示明确不可用语义，不显示零或 NaN

#### Scenario: 可空百分比不可用
- **WHEN** API 返回 `profit_loss_pct=null` 或 `stop_loss_distance_pct=null`
- **THEN** 共享百分比、色调、排序和风险标签工具保留未知语义，不输出 `0.00%` 或已知风险等级

### Requirement: 遵循服务端声明的运行时能力
前端 SHALL 在应用启动期间加载运行时能力契约，并将其作为可选导航、仪表盘区域、设置区域、路由行为和 API 轮询的判断依据。能力发现失败时，可选能力 MUST 默认关闭并从日常稳定工作流隐藏，同时受支持的核心流程仍应可以恢复。

#### Scenario: 旧版运行时不支持规划器
- **WHEN** 运行时能力表明风险预算读取和风险规划不可用
- **THEN** 稳定导航不展示规划器，仪表盘不请求或展示风险预算区域，设置页不展示风险政策输入，且不产生通用失败提示

#### Scenario: 能力不可用时直接访问规划器
- **WHEN** 用户直接打开 `/planner`，但风险规划不可用
- **THEN** 路由展示稳定的不可用状态和返回受支持页面的操作，并且不发起风险预览或仓位写入

#### Scenario: 能力发现失败
- **WHEN** 能力请求失败，但旧版核心页面仍可加载
- **THEN** 可选命令和区域保持隐藏，页面保留核心数据，并仅在直接访问相关可选路由时展示可恢复的能力状态说明

#### Scenario: 风险能力后续可用
- **WHEN** 受支持运行时同时声明对应风险读取或规划能力
- **THEN** 导航、仪表盘和设置页只展示与各自能力匹配的可完成区域
