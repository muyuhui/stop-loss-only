## ADDED Requirements

### Requirement: Persist validated risk budget settings
The system SHALL read and update optional manual portfolio equity, portfolio risk limit percentage, and default per-position risk limit percentage through the runtime settings API using Decimal-safe representations. It MUST validate the three fields together, preserve prior effective values on failure, and return the equity last-update time.

#### Scenario: Read settings before equity is entered
- **WHEN** the settings store contains no portfolio equity
- **THEN** the response returns equity as unavailable, documented percentage defaults, and no fabricated update time

#### Scenario: Save complete risk settings
- **WHEN** the user submits valid equity and percentage limits with the other runtime settings
- **THEN** the system atomically persists the values and returns their Decimal-safe effective representations

#### Scenario: Reject invalid equity
- **WHEN** the user submits zero or negative portfolio equity
- **THEN** the system returns a stable field validation error and all previously effective runtime settings remain unchanged

#### Scenario: Preserve risk settings when updating monitoring
- **WHEN** the user changes only polling or monitoring intervals
- **THEN** the stored risk budget settings remain unchanged
