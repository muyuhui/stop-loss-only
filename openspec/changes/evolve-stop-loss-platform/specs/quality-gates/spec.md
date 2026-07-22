## ADDED Requirements

### Requirement: Block all network access in mandatory tests
必选测试 SHALL 使用 fixture provider 和固定市场日历，并安装网络哨兵；任何 DNS、socket 或真实行情调用 SHALL 立即失败并指出调用位置。

#### Scenario: Provider accidentally calls the network
- **WHEN** 必选单元、集成或冒烟测试尝试创建外部网络连接
- **THEN** 测试立即失败，不等待提供方超时

#### Scenario: Optional live-provider test
- **WHEN** 用户显式开启真实行情测试
- **THEN** 网络哨兵仅为该独立测试关闭，结果不影响必选离线门禁的记录

### Requirement: Test concurrent monitoring outcomes
必选集成测试 SHALL 覆盖手动与调度周期并发、幂等告警、单标的 savepoint 和数据库 busy 行为，并断言响应只包含已提交结果。

#### Scenario: Two cycles trigger one position
- **WHEN** 两个并发周期都观察到同一仓位跌破止损
- **THEN** 最终只有一个触发事件和告警，两个响应均不声称不存在的提交

#### Scenario: One instrument fails to commit
- **WHEN** 一个标的事务失败而另一标的有效
- **THEN** 有效标的按设计提交，失败标的明确报告，测试验证没有跨标的静默回滚

### Requirement: Validate responsive UI with browser E2E
必选浏览器测试 SHALL 在 390x844、768x1024 和 1440x900 视口覆盖核心页面，检查无横向溢出、无固定导航遮挡、关键操作可达和业务文本正确。

#### Scenario: Mobile core journey
- **WHEN** fixture 环境完成新增、刷新、触发、确认、重新布防和部分平仓
- **THEN** 每一步在 390px 视口可完成且关键状态与后端一致

#### Scenario: Closed position presentation
- **WHEN** 浏览器打开关闭仓位详情
- **THEN** 页面显示净已实现收益且不存在活动止损编辑操作

## MODIFIED Requirements

### Requirement: 可复现的验证命令
项目 SHALL 提供非交互命令，在明确的临时目录中执行全部必选后端、前端、迁移、构建和浏览器门禁，禁止真实网络访问；任一必选项失败都必须返回非零并清理自有进程。

#### Scenario: 所有门禁通过
- **WHEN** 在准备好的干净环境运行验证命令
- **THEN** 命令成功退出，报告每项门禁、测试数量和构建预算，且没有残留监听进程

#### Scenario: 任一门禁失败
- **WHEN** 测试、网络哨兵、迁移对账、浏览器检查或包体预算失败
- **THEN** 验证命令非零退出并标明失败门禁，同时只清理自己启动的进程

#### Scenario: 系统临时目录不可写
- **WHEN** 默认临时目录不可访问但项目允许的隔离临时目录可用
- **THEN** 验证命令使用显式可写 basetemp，而不是因环境权限产生误报

### Requirement: 后端分层测试
必选后端测试 SHALL 覆盖纯领域规则、Decimal 财务口径、API/数据库集成、有序迁移升级/降级与数据对账、调度器生命周期、并发触发、历史保留、导入安全和隔离行情适配器契约。

#### Scenario: 核心流程回归
- **WHEN** 建仓、加仓、刷新、触发、确认、重新布防、部分平仓、关闭、告警或汇总违反规格
- **THEN** 至少一项必选自动化测试失败

#### Scenario: Migration loses financial precision
- **WHEN** 升级或降级改变数量、价格、费用或收益 Decimal 值
- **THEN** 数据保真测试失败并输出不敏感的差异字段

### Requirement: 前端行为测试
必选前端测试 SHALL 真实挂载 store、组件和路由，覆盖行情状态、筛选 URL、生命周期处置、轮询共享、分页、部分刷新、通知权限和关闭仓位展示；源码字符串检查不得作为交互行为的唯一证明。

#### Scenario: Alert list has more than one page
- **WHEN** mock API 返回超过页面大小的告警
- **THEN** 组件测试验证用户可到达下一页且筛选与总数正确

#### Scenario: Background refresh fails
- **WHEN** 页面已有成功数据而后续请求失败
- **THEN** 组件保留最后数据、显示年龄和重试入口，不闪回空状态

### Requirement: 本地端到端冒烟测试
项目 SHALL 使用临时数据库、fixture 行情、固定交易日历和实际构建产物启动隔离服务，验证 readiness、核心 API 及浏览器用户旅程，并关闭所有自有进程。

#### Scenario: 完全离线冒烟成功
- **WHEN** 主机无法访问外网且运行必选冒烟
- **THEN** 新增、刷新、触发、告警、处置、平仓和仪表盘流程成功完成

#### Scenario: 冒烟启动或请求失败
- **WHEN** 服务未就绪或核心请求超过与操作匹配的超时
- **THEN** 测试失败并保存临时诊断，最终清理自己启动的后端和前端进程
