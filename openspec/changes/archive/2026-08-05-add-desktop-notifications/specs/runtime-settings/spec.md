## ADDED Requirements

### Requirement: 桌面通知设置持久化
系统 SHALL 在 `/api/settings` 提供并持久化三个桌面通知设置：`desktop_notifications_enabled`（布尔，默认 `false`，opt-in）、`desktop_notification_mode`（`full` / `redacted`，默认 `full`）、`desktop_notifications_paused`（布尔，默认 `false`）。`GET /api/settings` MUST 始终返回三键；`PUT /api/settings` MUST 接受三键并持久化（重启后保留）；非法 `desktop_notification_mode` 值 MUST 返回 422。

#### Scenario: 返回默认设置
- **WHEN** 用户请求 `GET /api/settings` 且从未修改桌面通知设置
- **THEN** `desktop_notifications_enabled` 为 `false`、`desktop_notification_mode` 为 `full`、`desktop_notifications_paused` 为 `false`

#### Scenario: 保存并回读设置
- **WHEN** 用户 `PUT /api/settings` 提交启用、`redacted` 模式与暂停状态
- **THEN** 三键持久化，`GET /api/settings` 回读一致

#### Scenario: 模式值非法
- **WHEN** 用户提交 `desktop_notification_mode` 为约定范围外的字符串
- **THEN** 系统返回 422，设置不变化
