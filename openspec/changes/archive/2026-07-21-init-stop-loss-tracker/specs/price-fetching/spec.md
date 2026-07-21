## ADDED Requirements

### Requirement: Fetch real-time stock price
The system SHALL fetch the current real-time price for an A-share stock using akshare.

#### Scenario: Fetch stock price during trading hours
- **WHEN** system calls the price fetcher for code "000001" during trading hours
- **THEN** system returns current price, change percentage, and timestamp

#### Scenario: Fetch stock price outside trading hours
- **WHEN** system calls the price fetcher outside trading hours
- **THEN** system returns the last available closing price

### Requirement: Fetch fund NAV
The system SHALL fetch the latest net asset value (NAV) for a fund using akshare.

#### Scenario: Fetch ETF fund price
- **WHEN** system calls price fetcher for a fund with type "fund" and code "510050"
- **THEN** system returns the latest available price or NAV

#### Scenario: Fetch off-exchange fund NAV
- **WHEN** system calls price fetcher for an off-exchange fund
- **THEN** system returns the latest published NAV (may be T or T-1 day)

### Requirement: Batch fetch prices for all holdings
The system SHALL support batch price fetching for all active holdings to minimize API calls.

#### Scenario: Batch fetch for multiple holdings
- **WHEN** system requests prices for holdings ["000001", "510050", "159915"]
- **THEN** system returns price data for all valid codes in a single response

### Requirement: Trading day detection
The system SHALL detect whether the current day is an A-share trading day and only run scheduled monitoring during trading hours.

#### Scenario: Current day is a trading day
- **WHEN** it is a weekday and not a Chinese public holiday
- **THEN** the scheduler SHALL run price monitoring between 9:30 and 15:00

#### Scenario: Current day is a weekend or holiday
- **WHEN** it is Saturday, Sunday, or a Chinese public holiday
- **THEN** the scheduler SHALL skip price monitoring

### Requirement: Scheduled price monitoring
The system SHALL run price monitoring at a configurable interval during trading hours.

#### Scenario: Monitoring triggers during trading hours
- **WHEN** the scheduled job runs at the configured interval (default 5 minutes)
- **THEN** system fetches current prices for all active holdings, updates highest prices, and checks stop-loss triggers

#### Scenario: Monitoring skipped on non-trading days
- **WHEN** it is a non-trading day (weekend/holiday)
- **THEN** the scheduled job skips execution and logs the reason

### Requirement: Manual price refresh API
The system SHALL provide an API endpoint to manually trigger a full price refresh and stop-loss check for all holdings.

#### Scenario: Manual refresh request
- **WHEN** user requests POST /api/prices/refresh
- **THEN** system fetches all prices, updates holdings, checks stop-loss triggers, and returns the updated status
