## 1. 固化受支持边界

- [x] 1.1 增加后端权威阶段矩阵测试，覆盖 legacy、shadow-read、不受支持的 new-authoritative 启动/readiness、Position 写入、监控、仪表盘、价格、历史和运维路由。
- [x] 1.2 增加切换回归测试，证明 cutover 在备份、shadow 重建或权威状态修改前失败，并保持数据库不变。
- [x] 1.3 为全量和限定范围刷新增加 `refresh_busy`、`database_busy`、校验失败及未知故障 API 测试，验证有意返回的 HTTP 状态和稳定错误码不会丢失。
- [x] 1.4 增加测试，证明直接调用 CSV、Webhook 和其他推迟扩展时，不会写入 Position、ImportAudit、DeliveryAttempt、密钥或配置。
- [x] 1.5 增加前端路由测试，复现告警跳转到缺失 Position 路由的回归，并核对每个可见命令都有已注册路由。

## 2. 落实后端默认拒绝行为

- [x] 2.1 引入统一的受支持运行面边界 helper 或等价集中策略，供 CLI 与 HTTP 路由共同使用。
- [x] 2.2 让 `db_admin.py cutover` 在备份或修改前返回 `cutover_not_supported`，同时保留 shadow 启用、重建、状态和对账诊断。
- [x] 2.3 打开已处于 `new-authoritative` 的数据库时，让 readiness 失败并提供非敏感恢复指引；不得自动反向投影或写入 legacy 事实。
- [x] 2.4 在受支持版本中，以稳定的 `409 feature_not_supported` 保护所有仅 Position 支持的写路由和 CSV 导入导出路由。
- [x] 2.5 拒绝 Webhook 启用、目标、payload 和密钥修改，不改变运行时设置或密钥存储；稳定监控周期不再创建 DeliveryAttempt。
- [x] 2.6 重构全量与限定范围价格刷新接口，共享一个结果/错误映射器，透传有意 HTTP 错误，并统一报告 busy、数据库、校验和内部故障。
- [x] 2.7 验证存在 shadow 记录时，持仓、仪表盘、价格列表、价格历史、监控状态以及定时/手动监控只读写 legacy 权威事实。
- [x] 2.8 为本次涉及的公共边界增加或收紧 Pydantic 请求/错误模型，让 OpenAPI 准确记录稳定校验和错误响应。

## 3. 对齐稳定前端运行面

- [x] 3.1 让告警查看操作通过 `/holdings/:holding_id` 进入详情，移除稳定界面到 `/positions/:id` 的导航，并从生产路由图隔离孤立的 Position 组件和 store。
- [x] 3.2 从设置页移除 CSV、Webhook、retention 和浏览器系统通知控制，同时保留受支持的刷新间隔、手动刷新、监控诊断与备份控制。
- [x] 3.3 将告警和设置页剩余用户文案及可访问名称统一为中文，并明确区分已读与关闭持仓语义。
- [x] 3.4 统一前端对 `refresh_busy`、`database_busy`、校验失败和未知错误的处理，且不清空最后成功的持仓或仪表盘数据。
- [x] 3.5 使用真实 router/store 集成和确定性 API mock 挂载 Dashboard、Holdings、HoldingDetail、Alerts 与 Settings，覆盖加载、后台失败、导航、表单和计时器所有权。

## 4. 恢复可执行质量门禁

- [x] 4.1 增加真实浏览器 E2E 工具，使用构建后的前端、隔离数据库、fixture provider/calendar、仅 loopback 服务、有界启动和可靠的自有进程清理。
- [x] 4.2 在 `390x844`、`768x1024` 和 `1440x900` 覆盖受支持的创建、刷新、触发、查看告警、持仓详情与手动关闭流程。
- [x] 4.3 增加浏览器断言，检查未匹配路由、未捕获 console/page 错误、横向溢出、固定导航遮挡、不可操作控件和关键文本截断。
- [x] 4.4 将现有脚本明确命名和报告为 API/进程 smoke，而非浏览器 E2E，并保持 legacy fixture 流程完全离线。
- [x] 4.5 更新 `verify.ps1`，为每次运行使用独立临时根目录，预检完整依赖，执行后端/组件/浏览器/构建/恢复门禁，并运行 `openspec validate --all --strict --no-interactive`。
- [x] 4.6 更新启动依赖预检，在启动任何服务前拒绝不完整的 `node_modules`，并保留明确的 `setup.ps1` 恢复提示。
- [x] 4.7 扩展备份恢复测试和演练，覆盖同秒多次备份、无效 checksum/schema/完整性、恢复点回滚、WAL 状态以及已处于 new-authoritative 的数据库。
- [x] 4.8 在准备好的干净依赖状态中连续运行两次完整验证命令，确认第二次不受上次临时文件、端口、数据库或构建产物影响。

## 5. 对齐文档与发布证据

- [x] 5.1 为本 change 的每项 delta requirement 增加 requirement 到测试的可追溯表，并确保行为要求不以源码文本断言作为唯一证据。
- [x] 5.2 更新 README 与平台路线图，记录受支持运行面矩阵、推迟的 Position/CSV/投递工作、切换拒绝行为以及已切换数据库的恢复步骤。
- [x] 5.3 通过正常 OpenSpec 同步/归档流程替换受影响当前规格中剩余的 `TBD` Purpose，不重写历史归档产物。
- [x] 5.4 运行后端测试、前端组件测试、生产构建与包体预算、API/进程 smoke、三视口浏览器 E2E、恢复演练和严格 OpenSpec 校验；可选真实 provider 结果单独记录。
