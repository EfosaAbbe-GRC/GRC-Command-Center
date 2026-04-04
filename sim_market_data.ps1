$logPath = "C:\Users\efosb\OneDrive\Desktop\Google IDE\Mufasa BloomBerg Terminal\backend_log.txt"
$statePath = "C:\Users\efosb\OneDrive\Desktop\Google IDE\Mufasa BloomBerg Terminal\backend\data\market_state_cache.json"

# Ensure directories exist
$logDir = Split-Path $logPath
if (!(Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force }
$stateDir = Split-Path $statePath
if (!(Test-Path $stateDir)) { New-Item -ItemType Directory -Path $stateDir -Force }

# 1. Append formatted Log Entry
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$logMessage = "$timestamp [VETO] RiskAgent: Blocked SPY Trade (Beta > 2.5) - SIMULATION TEST"
Add-Content -Path $logPath -Value $logMessage
Write-Host "Appended Log: $logMessage"

# 2. Update Market State Cache (Simulate Active Positions)
$json = @{
    state = @{
        SPY = @{
            strat = @{
                status = "ACTIVE"
                grade = "B"
            }
        }
        QQQ = @{
            strat = @{
                status = "ACTIVE"
                grade = "A"
            }
        }
    }
} | ConvertTo-Json -Depth 5

Set-Content -Path $statePath -Value $json
Write-Host "Updated Market State: Active Holdings set to 2"
