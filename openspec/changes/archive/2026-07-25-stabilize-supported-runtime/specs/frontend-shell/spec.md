## ADDED Requirements

### Requirement: 每个可见命令都必须指向受支持工作流
前端 SHALL 只显示能够完成的稳定命令，且每个可见导航、列表行、告警操作和详情入口 MUST 匹配已注册路由与受支持后端操作。未完成组件可以保留在源码中供后续 change 使用，但 MUST NOT 从稳定 UI 可达。

#### Scenario: 点击告警处置入口
- **WHEN** 用户点击告警中的持仓处置入口
- **THEN** 路由进入已注册的 legacy 持仓详情且页面可以加载对应记录

#### Scenario: 检查稳定导航
- **WHEN** 浏览器遍历所有稳定页面和可见操作
- **THEN** 不出现未匹配路由、空白页面、不可达命令或未捕获控制台错误

## MODIFIED Requirements

### Requirement: Request privileged capabilities on demand
前端 SHALL 只在明确用户操作后创建受支持的本地备份，并显示成功、失败和恢复边界。稳定界面 MUST NOT 请求尚无完整运行时实现的系统通知权限或导入文件。

#### Scenario: 页面加载
- **WHEN** 用户首次打开任一稳定页面
- **THEN** 页面不请求系统通知权限、不打开文件选择器，也不触发备份

#### Scenario: 明确创建备份
- **WHEN** 用户在设置中明确选择创建备份
- **THEN** 页面调用受支持备份操作并显示经过校验的结果或可操作错误
