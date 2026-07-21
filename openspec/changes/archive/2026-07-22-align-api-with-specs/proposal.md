## Why

当前多个接口没有遵守既有 OpenSpec：同一持仓在不同接口中的止损价不一致、列表没有分页、删除状态码不符、仪表盘缺少今日告警，保存的轮询设置也没有真正控制运行中的应用。核心监控稳定后，需要用一套明确且可测试的契约统一 API 与前端行为。

## What Changes

- 统一新建、详情、列表、修改和仪表盘中的持仓派生字段，并在正确的写入边界持久化止损价。
- 为持仓列表增加校验过的分页、状态筛选、稳定排序及分页元数据。
- 对齐删除接口的 HTTP 语义，并明确带历史告警持仓的删除规则。
- 区分当前持仓、已实现和未实现收益，补齐今日告警数与最新告警。
- 新增运行时设置能力：服务端校验、调度间隔重启恢复、前端轮询实时生效。
- 统一手动刷新与前一变更中监控周期的响应和错误语义。
- **BREAKING**：持仓列表和仪表盘响应结构将规范化；调用方必须识别 `triggered` 与 `closed`。

## Capabilities

### New Capabilities

- `runtime-settings`：运行时轮询与监控间隔的校验、持久化、恢复和动态应用。

### Modified Capabilities

- `holdings-crud`：统一派生字段、分页、删除语义和生命周期操作。
- `dashboard`：明确当前敞口、已实现/未实现收益和今日告警摘要。
- `price-fetching`：规范手动刷新 API 和部分成功响应。

## Impact

- 影响 holdings、dashboard、settings、prices 路由、Pydantic schema、服务层和 OpenAPI。
- 影响调度器启动配置及前端持仓、仪表盘、告警、设置和刷新页面。
- 依赖 `harden-stop-loss-monitoring` 先完成；使用旧响应结构的客户端需要同步调整。
