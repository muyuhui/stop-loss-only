function Test-RecordedProcessStart {
    param(
        [Parameter(Mandatory = $true)]$RecordedStart,
        [Parameter(Mandatory = $true)][DateTime]$ActualStart
    )

    try {
        if ($RecordedStart -is [DateTime]) {
            $recordedUtc = $RecordedStart.ToUniversalTime()
        } else {
            $recordedUtc = [DateTimeOffset]::Parse(
                [string]$RecordedStart,
                [Globalization.CultureInfo]::InvariantCulture,
                [Globalization.DateTimeStyles]::AssumeUniversal
            ).UtcDateTime
        }
        $actualUtc = $ActualStart.ToUniversalTime()
        return $recordedUtc.Ticks -eq $actualUtc.Ticks
    } catch {
        return $false
    }
}
