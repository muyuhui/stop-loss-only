## ADDED Requirements

### Requirement: Request privileged capabilities on demand
前端 SHALL 只在明确用户操作后请求系统通知、创建备份或选择导入文件，并显示已授权、已拒绝、不支持和失败状态。

#### Scenario: Page loads with notifications unset
- **WHEN** 用户首次打开设置且通知权限未决定
- **THEN** 页面不得自动请求权限，只显示解释和启用按钮
