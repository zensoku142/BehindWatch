# Run with Windows PowerShell 5.1; PowerShell 7 cannot project these WinRT types.
[CmdletBinding()]
param(
    [switch]$Capture,
    [ValidateRange(1, 60)][int]$Seconds = 10,
    [ValidateRange(0, 100)][int]$InfraredIndex = 0
)

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSEdition -ne 'Desktop') {
    throw 'Use powershell.exe -NoProfile -File tools\probe_ir_camera.ps1'
}
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$groupType = [Windows.Media.Capture.Frames.MediaFrameSourceGroup, Windows.Media.Capture, ContentType=WindowsRuntime]
$readerType = [Windows.Media.Capture.Frames.MediaFrameReader, Windows.Media.Capture, ContentType=WindowsRuntime]
$statusType = [Windows.Media.Capture.Frames.MediaFrameReaderStartStatus, Windows.Media.Capture, ContentType=WindowsRuntime]
$listType = [System.Collections.Generic.IReadOnlyList``1].MakeGenericType($groupType)
$asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and
    $_.GetGenericArguments().Count -eq 1 -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
} | Select-Object -First 1
$asActionTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and -not $_.IsGenericMethod -and
    $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction'
} | Select-Object -First 1

function Wait-WinRT($Operation, [Type]$ResultType) {
    if ($ResultType) {
        $task = $asTask.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    } else {
        # Reflection handles the WinRT COM projection that PowerShell's explicit cast rejects.
        $task = $asActionTask.Invoke($null, @($Operation))
    }
    # Bound driver waits; the outer finally releases the capture on failure.
    if (-not $task.Wait(15000)) {
        $Operation.Cancel()
        throw 'Windows camera operation timed out after 15 seconds.'
    }
    if ($ResultType) { return ,$task.GetAwaiter().GetResult() }
    $null = $task.GetAwaiter().GetResult()
}

$captureDevice = $reader = $null
$frameHandler = $null
$frameToken = $null
$started = $false
$exitCode = 0
try {
    Write-Host 'Enumerating frame sources (no capture yet)...'
    $groups = Wait-WinRT ($groupType::FindAllAsync()) $listType
    # Prefer an IR-only group to avoid initializing the combined RGB/IR group unnecessarily.
    $groups = @($groups | Sort-Object {
        @($_.SourceInfos | Where-Object { $_.SourceKind.ToString() -ne 'Infrared' }).Count
    })
    $infrared = @()
    foreach ($group in $groups) {
        Write-Host ('Group: {0}' -f $group.DisplayName)
        foreach ($source in $group.SourceInfos) {
            Write-Host ('  Kind={0}; Stream={1}; Device={2}' -f
                $source.SourceKind, $source.MediaStreamType, $source.DeviceInformation.Name)
            # Select by the driver's source kind, never by camera index/name alone.
            if ($source.SourceKind.ToString() -eq 'Infrared') {
                Write-Host ('  -> InfraredIndex={0}' -f $infrared.Count)
                $infrared += [pscustomobject]@{ Group = $group; Source = $source }
            }
        }
    }
    if ($infrared.Count -eq 0) {
        throw 'NO_IR_SOURCE: Windows exposes no infrared frame source to this application.'
    }
    if ($InfraredIndex -ge $infrared.Count) { throw 'InfraredIndex is out of range.' }
    if ($Capture) {
        $selected = $infrared[$InfraredIndex]
        $settings = New-Object Windows.Media.Capture.MediaCaptureInitializationSettings
        $settings.SourceGroup = $selected.Group
        $settings.SharingMode = 'SharedReadOnly'
        $settings.StreamingCaptureMode = 'Video'
        $settings.MemoryPreference = 'Cpu'
        $captureDevice = New-Object Windows.Media.Capture.MediaCapture
        Write-Host 'Initializing IR capture; no RGB reader or audio stream will be created.'
        Write-Host 'Observe the physical camera/IR lights. Shared hardware power cannot be inferred from this API.'
        Wait-WinRT ($captureDevice.InitializeAsync($settings))
        # WinRT's map is projected as key/value entries in Windows PowerShell.
        $frameSource = $null
        foreach ($entry in $captureDevice.FrameSources) {
            if ($entry.Key -eq $selected.Source.Id) { $frameSource = $entry.Value; break }
        }
        if ($null -eq $frameSource) { throw 'Selected IR source was absent after initialization.' }
        Write-Host ('Format: {0}; {1}x{2}; sensor rate {3}/{4} fps' -f
            $frameSource.CurrentFormat.Subtype,
            $frameSource.CurrentFormat.VideoFormat.Width,
            $frameSource.CurrentFormat.VideoFormat.Height,
            $frameSource.CurrentFormat.FrameRate.Numerator,
            $frameSource.CurrentFormat.FrameRate.Denominator)
        $reader = Wait-WinRT ($captureDevice.CreateFrameReaderAsync($frameSource)) $readerType
        # A CLR no-op callback avoids invoking PowerShell on the camera's native callback thread.
        $eventArgsType = [Windows.Media.Capture.Frames.MediaFrameArrivedEventArgs, Windows.Media.Capture, ContentType=WindowsRuntime]
        $handlerType = [Windows.Foundation.TypedEventHandler``2, Windows.Foundation, ContentType=WindowsRuntime].MakeGenericType($readerType, $eventArgsType)
        $parameters = [System.Linq.Expressions.ParameterExpression[]]@(
            [System.Linq.Expressions.Expression]::Parameter($readerType, 'sender'),
            [System.Linq.Expressions.Expression]::Parameter($eventArgsType, 'args'))
        $frameHandler = [System.Linq.Expressions.Expression]::Lambda(
            $handlerType, [System.Linq.Expressions.Expression]::Empty(), $parameters).Compile()
        $frameToken = $reader.add_FrameArrived($frameHandler)
        $status = Wait-WinRT ($reader.StartAsync()) $statusType
        if ($status.ToString() -ne 'Success') { throw "IR_START_FAILED: $status" }
        $started = $true
        $clock = [Diagnostics.Stopwatch]::StartNew()
        $count = 0
        $received = 0
        $bitmaps = 0
        $lastTimestamp = $null
        $lastFrameAt = 0.0
        $maxGap = 0.0
        $nextPixelCheck = 0.0
        $pixelChecks = 0
        $spatialChecks = 0
        $changedChecks = 0
        $previousSamples = $null
        $nextReport = 1
        while ($clock.Elapsed.TotalSeconds -lt $Seconds) {
            $frame = $bitmap = $null
            try {
                $frame = $reader.TryAcquireLatestFrame()
                if ($null -ne $frame -and $null -ne $frame.VideoMediaFrame) {
                    $received++
                    $bitmap = $frame.VideoMediaFrame.SoftwareBitmap
                    if ($null -ne $bitmap) { $bitmaps++ }
                    $timestamp = $frame.SystemRelativeTime
                    # Polling can return the latest frame repeatedly; count unique timestamps only.
                    if ($null -ne $bitmap -and $null -ne $timestamp -and $timestamp -ne $lastTimestamp) {
                        $count++
                        $lastTimestamp = $timestamp
                        $frameAt = $clock.Elapsed.TotalSeconds
                        $maxGap = [Math]::Max($maxGap, $frameAt - $lastFrameAt)
                        $lastFrameAt = $frameAt
                        if ($count -eq 1) {
                            Write-Host ('First IR bitmap: {0}x{1}, {2}' -f
                                $bitmap.PixelWidth, $bitmap.PixelHeight, $bitmap.BitmapPixelFormat)
                        }
                        if ($frameAt -ge $nextPixelCheck) {
                            # Inspect a sparse grayscale sample in memory; timestamps alone cannot exclude blank frames.
                            if ($bitmap.BitmapPixelFormat.ToString() -ne 'Gray8') {
                                throw 'PIXEL_CHECK_UNSUPPORTED: this probe currently checks Gray8 IR only.'
                            }
                            $length = $bitmap.PixelWidth * $bitmap.PixelHeight
                            $buffer = [Windows.Storage.Streams.Buffer, Windows.Storage.Streams, ContentType=WindowsRuntime]::new($length)
                            $bitmap.CopyToBuffer($buffer)
                            $dataReader = [Windows.Storage.Streams.DataReader, Windows.Storage.Streams, ContentType=WindowsRuntime]::FromBuffer($buffer)
                            try {
                                $bytes = New-Object byte[] $length
                                $dataReader.ReadBytes($bytes)
                            } finally { $dataReader.Dispose() }
                            $step = [Math]::Max(1, [int][Math]::Floor($length / 2048))
                            $samples = @(for ($i = 0; $i -lt $length; $i += $step) { [int]$bytes[$i] })
                            $stats = $samples | Measure-Object -Minimum -Maximum -Average
                            $delta = 0.0
                            if ($null -ne $previousSamples -and $previousSamples.Count -eq $samples.Count) {
                                for ($i = 0; $i -lt $samples.Count; $i++) {
                                    $delta += [Math]::Abs($samples[$i] - $previousSamples[$i])
                                }
                                $delta /= $samples.Count
                                if ($delta -gt 0) { $changedChecks++ }
                            }
                            $pixelChecks++
                            if ($stats.Maximum - $stats.Minimum -ge 8) { $spatialChecks++ }
                            Write-Host ('Pixels: min={0}; max={1}; mean={2:N2}; mean_abs_change={3:N2}' -f
                                $stats.Minimum, $stats.Maximum, $stats.Average, $delta)
                            $previousSamples = $samples
                            $nextPixelCheck = $frameAt + 1
                        }
                    }
                }
            } finally {
                # SoftwareBitmap has its own lifetime; keeping frames can exhaust the driver's pool.
                if ($null -ne $bitmap) { $bitmap.Dispose() }
                if ($null -ne $frame) { $frame.Dispose() }
            }
            if ($clock.Elapsed.TotalSeconds -ge $nextReport) {
                Write-Host ('{0:N1}s: {1} unique IR frames; acquired={2}; bitmaps={3}' -f
                    $clock.Elapsed.TotalSeconds, $count, $received, $bitmaps)
                $nextReport++
            }
            Start-Sleep -Milliseconds 30
        }
        if ($count -lt 2) { throw "NO_CONTINUOUS_IR_FRAMES: received $count unique frames." }
        $maxGap = [Math]::Max($maxGap, $clock.Elapsed.TotalSeconds - $lastFrameAt)
        Write-Host ('Signal summary: pixel_checks={0}; nonuniform_checks={1}; changed_checks={2}; max_gap_seconds={3:N3}' -f
            $pixelChecks, $spatialChecks, $changedChecks, $maxGap)
        if ($maxGap -gt 2) { throw 'IR_STALLED: more than two seconds without a fresh frame.' }
        if ($spatialChecks -eq 0) { throw 'IR_BLANK_OR_LOW_CONTRAST: no sampled frame has a grayscale range of at least 8.' }
        Write-Host ('PASS: {0} unique IR frames in {1:N1}s; observed polling rate {2:N1} fps.' -f
            $count, $clock.Elapsed.TotalSeconds, ($count / $clock.Elapsed.TotalSeconds))
        Write-Host 'This verifies frame access only, not image quality, person detection, power savings or RGB power state.'
    } else {
        Write-Host 'Enumeration passed. Add -Capture to test IR frames for a bounded duration.'
    }
} catch {
    Write-Host ('FAIL: {0}' -f $_.Exception.ToString())
    $exitCode = 1
} finally {
    if ($null -ne $reader) {
        try {
            if ($started) { Wait-WinRT ($reader.StopAsync()) }
        } catch {
            Write-Warning ('IR stop failed: {0}' -f $_.Exception.Message)
            $exitCode = 1
        } finally {
            if ($null -ne $frameToken) { $reader.remove_FrameArrived($frameToken) }
            $reader.Dispose()
        }
    }
    if ($null -ne $captureDevice) { $captureDevice.Dispose() }
    Write-Host 'Probe finished; capture resources disposed. No images saved.'
}
exit $exitCode
