## 1. 仪表盘展示已实现盈亏

- [x] 1.1 在 `frontend/src/views/Dashboard.vue` 资产摘要 `metric-grid` 增加“已实现盈亏（毛）”卡片，使用 `dashboard.realized_profit_loss` 与 `valueTone` 着色，桌面网格调整为 4 列并保持移动端两列布局
- [x] 1.2 更新/新增前端 mount 测试：存在已关闭持仓时展示金额，无已关闭持仓时展示零值，窄屏不产生横向滚动

## 2. 告警全部已读按钮状态

- [x] 2.1 在 `frontend/src/stores/alert.js` 增加 `countLoaded` 标记，仅在未读计数成功加载后置真
- [x] 2.2 在 `frontend/src/views/Alerts.vue` 为“全部标记已读”绑定禁用：`countLoaded && unreadCount === 0` 时禁用；`markAll` 成功后同步刷新计数
- [x] 2.3 新增 mount/unit 测试：计数未加载时不禁用、已加载且为 0 时禁用、大于 0 时可用

## 3. 平仓预填与盈亏预览

- [x] 3.1 新增纯函数 `estimateRealizedProfitLoss(closePrice, buyPrice, quantity)`（建议放 `frontend/src/utils/format.js`），输入无效时返回 `null`，并补充 unit 测试
- [x] 3.2 在 `frontend/src/views/HoldingDetail.vue` 中，仅当 `holding.is_actionable` 且 `current_price != null` 时预填 `closePrice = current_price`；行情不可用时保持为空
- [x] 3.3 平仓确认弹窗展示预计毛已实现盈亏（`(平仓价 - 买入价) × 数量`），文案标注“不含费用、仅供参考”，用户修改平仓价后按新输入重新计算
- [x] 3.4 新增 mount 测试：可行动行情预填、不可行动为空、修改价格后重算、提交成功后清除输入

## 4. 试算结果填入新增持仓

- [x] 4.1 新增纯函数 `holdingPrefillFromPlan(result)`（建议放 `frontend/src/utils/holdingForm.js`）：输出 `{ code, name, type, buy_price, quantity, buy_date, stop_loss_method, stop_loss_value }`，数量向下取整为整数、买入价按资产精度取整、买入日期默认本地当天；补充 unit 测试（含基金小数数量取整）
- [x] 4.2 在 `frontend/src/views/RiskPlanner.vue` 新仓结果面板增加“填入新增持仓”入口：仅 `mode === 'new'`、结果 `ready` 且运行时声明 `legacy_holding_writes` 时显示；`new-authoritative` 的受约束 Position 创建入口保持不变
- [x] 4.3 入口跳转 `/holdings?create=1&code=...&name=...&type=...&buy_price=...&quantity=...&stop_method=...&stop_value=...&buy_date=...`；`frontend/src/views/Holdings.vue` 在挂载时解析该参数并自动打开新增弹窗
- [x] 4.4 `frontend/src/components/HoldingForm.vue` 支持 `initialValues` props 初始化表单（默认值保持现有行为），预填数量提示“已按整数份取整，可调整”
- [x] 4.5 参数缺失、非法或对应能力不可用时静默忽略，保持正常列表行为；表单提交成功或取消后清理路由中的 `create` 参数
- [x] 4.6 新增 mount 测试：入口渲染条件、跳转参数与表单预填、非法参数忽略、取消后路由清理

## 5. Windows 本机密钥存储与回归验证

- [x] 5.1 在 `backend/requirements.txt` 固定 `pywin32==312`，使 Windows 运行环境可导入 `win32crypt` 并使用既有 DPAPI 密钥存储；不引入明文或数据库回退
- [x] 5.2 在安装依赖后的同一 Python 解释器中验证 `import win32crypt`，并运行 `backend/tests/test_ai_review.py` 中的 Windows DPAPI round-trip 测试

- [x] 5.3 运行 `npm test`（node --test + vitest run），全部前端单元/挂载测试通过
- [x] 5.4 运行 `npm run build`，通过依赖校验与 bundle 预算门禁
- [x] 5.5 在 Playwright E2E 中扩展一条场景（桌面视口）：配置风险权益后完成新仓试算，断言“填入新增持仓”入口存在且可进入预填表单
- [x] 5.6 运行 `.\verify.ps1` 全门禁并修复回归
