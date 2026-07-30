## ADDED Requirements

### Requirement: 验证风险试算的只读与权威边界
强制质量门禁 SHALL 通过后端服务/API、真实前端组件和目标视口浏览器流程验证新仓与加仓风险试算的 Decimal 计算、拒绝原因、权威数据选择、能力可见性和零写入保证。仅比较源码字符串 MUST NOT 作为行为正确的唯一证据。

#### Scenario: 新仓试算计算正确
- **WHEN** 固定 fixture 提供已知组合权益、风险容量、计划价格、止损、费用和资产数量单位
- **THEN** 服务与 API 测试断言取整前数量、最大数量、预计损失、所需资金和试算后风险均与 Decimal 公式一致

#### Scenario: 加仓试算计算正确
- **WHEN** 固定 fixture Holding 具有已知当前风险、现有止损价、单笔剩余容量和组合剩余容量
- **THEN** 测试断言增量允许风险使用两种容量中的较小值，止损价保持不变，结果按资产数量单位向下取整

#### Scenario: 试算前后没有业务写入
- **WHEN** 后端依次执行成功和拒绝的新仓、加仓试算
- **THEN** 测试证明 Holding、Position、批次、规则、事件、告警、设置和行情表的记录与关键字段均未变化

#### Scenario: shadow 投影不重复计入
- **WHEN** `shadow-read` fixture 同时包含 legacy Holding 与对应 shadow Position
- **THEN** 风险预算和试算结果只计算一次 legacy 权威事实

#### Scenario: 稳定界面只提供试算
- **WHEN** 三个目标视口运行 `risk_plan_previews=true` 且所有 Position 写入能力为 false 的 fixture
- **THEN** 用户可以完成新仓和加仓试算，页面不存在创建 Position、写入批次、自动下单或“推荐标的”命令，且不产生横向溢出或浏览器错误
