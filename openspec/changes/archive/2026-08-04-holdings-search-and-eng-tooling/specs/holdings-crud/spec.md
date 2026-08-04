## ADDED Requirements

### Requirement: 搜索持仓列表
系统 SHALL 在 `GET /api/holdings` 接受 `search` 查询参数，对持仓名称或代码进行转义后的包含匹配（子串、ASCII 不区分大小写），与生命周期状态、资产类型筛选可组合；未提供或空白 `search` 等同于不筛选。匹配发生在分页之前，`total` 反映过滤后数量。

#### Scenario: 按名称搜索命中
- **WHEN** 用户以持仓名称的子串请求 `GET /api/holdings?search=银行`
- **THEN** 响应只包含名称含"银行"的持仓，`total` 为该过滤数量

#### Scenario: 按代码搜索命中
- **WHEN** 用户以代码子串请求 `GET /api/holdings?search=0000`
- **THEN** 响应只包含代码含 `0000` 的持仓

#### Scenario: 搜索特殊字符不按通配解释
- **WHEN** 用户搜索包含 `%` 或 `_` 的字符串且持仓名称/代码中存在该字面量
- **THEN** 只按字面量匹配，不把 `%`/`_` 当作 LIKE 通配符

#### Scenario: 空搜索不筛选
- **WHEN** 用户省略 `search` 或提交空白值
- **THEN** 列表行为与不提供搜索参数一致

### Requirement: 按类型筛选持仓列表
系统 SHALL 在 `GET /api/holdings` 接受 `type` 查询参数（`stock` 或 `fund`）按资产类型等值筛选；非法值返回 422；未提供时不筛选。

#### Scenario: 筛选股票
- **WHEN** 用户请求 `GET /api/holdings?type=stock`
- **THEN** 响应只包含类型为 `stock` 的持仓

#### Scenario: 筛选基金
- **WHEN** 用户请求 `GET /api/holdings?type=fund`
- **THEN** 响应只包含类型为 `fund` 的持仓

#### Scenario: 类型参数非法
- **WHEN** 用户提交 `type` 值为约定范围外的字符串
- **THEN** 系统返回 422

### Requirement: 排序持仓列表
系统 SHALL 在 `GET /api/holdings` 接受 `sort` 查询参数（`newest` 默认 / `name` / `risk`）控制稳定分页排序：`newest` 按创建时间与 ID 倒序；`name` 按名称与 ID 升序；`risk` 按止损距离升序（距离为 `(current_price - stop_loss_price) / current_price`），无估值行情持仓排在所有已知距离之后，平局按 ID 升序；非法 `sort` 值返回 422。

#### Scenario: 默认最新优先
- **WHEN** 用户不带 `sort` 请求列表
- **THEN** 排序与现状一致（创建时间与 ID 倒序）

#### Scenario: 按名称排序
- **WHEN** 用户请求 `sort=name`
- **THEN** 持仓按名称升序、同名按 ID 升序

#### Scenario: 按风险排序
- **WHEN** 用户请求 `sort=risk`
- **THEN** 有估值行情的持仓按止损距离升序排列（已触发等最小距离在前），未定价或无估值持仓排在最后

#### Scenario: 排序参数非法
- **WHEN** 用户提交 `sort` 值为约定范围外的字符串
- **THEN** 系统返回 422

### Requirement: 组合筛选排序与分页
系统 SHALL 在应用 `status`、`type`、`search` 过滤与 `sort` 排序之后再计算 `total` 并切片分页；任意过滤组合下 `total` 恒为过滤后记录数，分页只返回对应切片。

#### Scenario: 组合搜索与状态筛选
- **WHEN** 用户请求 `GET /api/holdings?search=银行&status=holding&sort=risk&page=1&size=20`
- **THEN** 过滤与排序同时生效，`total` 为该组合下的记录数，`items` 为对应切片

#### Scenario: 筛选后分页
- **WHEN** 过滤条件下记录数超过一页且请求第 2 页
- **THEN** 第 2 页只包含第 2 个切片，且整体顺序与第 1 页连续

### Requirement: 持仓工具栏
前端持仓页 SHALL 提供搜索、筛选与排序工具栏：搜索输入（名称或代码）、生命周期状态下拉（全部/持有中/已触发/已关闭）、资产类型下拉（全部/A股/基金）、排序下拉（最新优先/名称/风险优先）、重置操作与过滤后总数展示；任一筛选或排序变化 MUST 重置到第 1 页；工具栏 MUST 只提供稳定 legacy Holding 语义的选项，MUST NOT 展示 position-only 的筛选项；≤767px 视口下为紧凑布局且不产生页面级横向滚动。

#### Scenario: 搜索收窄列表
- **WHEN** 用户输入搜索词并触发搜索
- **THEN** 列表回到第 1 页并按搜索词收窄，总数随之更新

#### Scenario: 切换筛选或排序
- **WHEN** 用户选择状态、类型或排序
- **THEN** 列表回到第 1 页并按新条件刷新

#### Scenario: 重置筛选
- **WHEN** 用户点击重置
- **THEN** 搜索、筛选、排序恢复默认，列表回到第 1 页并显示全部持仓

#### Scenario: 手机端使用工具栏
- **WHEN** 用户在 360px 到 767px 宽的视口使用持仓工具栏
- **THEN** 搜索与各下拉控件可触控使用，页面无横向滚动

### Requirement: 记忆排序偏好
前端 SHALL 将用户最后选择的排序方式保存在浏览器 localStorage，并在进入持仓页时恢复；恢复时 MUST 校验存储值，非法或缺失回退默认排序；搜索词与筛选条件不持久化。

#### Scenario: 排序选择被记忆
- **WHEN** 用户选择"风险优先"后离开持仓页并再次进入
- **THEN** 排序下拉与列表使用"风险优先"，无需重新选择

#### Scenario: 存储值非法时回退
- **WHEN** localStorage 中保存了约定范围外的排序值
- **THEN** 页面回退默认排序并正常展示列表
