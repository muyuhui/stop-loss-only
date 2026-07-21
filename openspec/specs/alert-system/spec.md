# Alert System

## Purpose

Automatically generate alerts when stop-loss triggers, notify via browser popup, and manage read status.

## Requirements

### Requirement: Create alert on stop-loss trigger
The system SHALL automatically create an alert record when a holding's stop-loss is triggered.

#### Scenario: Alert created on trigger
- **WHEN** a holding's current_price drops to or below its stop_loss_price
- **THEN** an alert is created with holding_id, trigger_price, current_price, read=false, and timestamp

### Requirement: List alerts
The system SHALL return a paginated list of alerts ordered by creation date descending.

#### Scenario: List all alerts
- **WHEN** user requests GET /api/alerts
- **THEN** system returns all alerts with holding name, trigger/current price, read status, and timestamps

#### Scenario: Filter unread alerts
- **WHEN** user requests GET /api/alerts?unread=true
- **THEN** system returns only alerts with read=false

### Requirement: Mark alert as read
The system SHALL allow users to mark an alert as read.

#### Scenario: Mark single alert as read
- **WHEN** user requests PUT /api/alerts/{id}/read
- **THEN** the alert's read field SHALL be set to true

#### Scenario: Mark all alerts as read
- **WHEN** user requests PUT /api/alerts/read-all
- **THEN** all alerts with read=false SHALL be set to read=true

### Requirement: Count unread alerts
The system SHALL provide the count of unread alerts for the dashboard and browser notification badge.

#### Scenario: Get unread count
- **WHEN** user requests GET /api/alerts/count
- **THEN** system returns the number of alerts with read=false

### Requirement: Browser notification for new alert
The frontend SHALL poll for unread alerts at a configurable interval and display a browser notification when new alerts are detected.

#### Scenario: New alert detected via polling
- **WHEN** the frontend polls GET /api/alerts/count and the count increases
- **THEN** a notification popup displays the alert details (holding name, trigger price, current price)

#### Scenario: No new alerts
- **WHEN** the frontend polls and no new alerts are found
- **THEN** no notification is shown
