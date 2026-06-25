param(
  [int]$Port = 8787
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$PublicRoot = Join-Path $Root "public"
$DataPath = Join-Path $Root "data\store.json"
$SourceRoot = Split-Path -Parent $Root
$ProjectRoot = Split-Path -Parent $SourceRoot
$CloudRoot = Join-Path $ProjectRoot "backend"
$LicenseCachePath = Join-Path $Root "data\license-cache.json"
$JsonToCommand = Get-Command ConvertTo-Json -ErrorAction SilentlyContinue
$JsonFromCommand = Get-Command ConvertFrom-Json -ErrorAction SilentlyContinue
$SupportsConvertToJsonDepth = $JsonToCommand -and $JsonToCommand.Parameters.ContainsKey("Depth")
$SupportsConvertFromJsonDepth = $JsonFromCommand -and $JsonFromCommand.Parameters.ContainsKey("Depth")

[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12

function Convert-ToJsonText {
  param($Data)
  return Convert-ToJsonValue $Data
}

function Convert-FromJsonText {
  param([string]$Text)
  if ($SupportsConvertFromJsonDepth) {
    return ($Text | ConvertFrom-Json -Depth 30)
  }
  return ($Text | ConvertFrom-Json)
}

function Convert-ToJsonString {
  param([string]$Text)
  if ($null -eq $Text) { return "null" }
  $builder = [System.Text.StringBuilder]::new()
  [void]$builder.Append('"')
  foreach ($char in $Text.ToCharArray()) {
    switch ($char) {
      '"' { [void]$builder.Append('\"') }
      '\' { [void]$builder.Append('\\') }
      "`b" { [void]$builder.Append('\b') }
      "`f" { [void]$builder.Append('\f') }
      "`n" { [void]$builder.Append('\n') }
      "`r" { [void]$builder.Append('\r') }
      "`t" { [void]$builder.Append('\t') }
      default {
        $code = [int][char]$char
        if ($code -lt 32) {
          [void]$builder.Append(('\u{0:x4}' -f $code))
        } else {
          [void]$builder.Append($char)
        }
      }
    }
  }
  [void]$builder.Append('"')
  return $builder.ToString()
}

function Convert-ToJsonValue {
  param($Value)
  if ($null -eq $Value) { return "null" }
  if ($Value -is [string]) { return Convert-ToJsonString $Value }
  if ($Value -is [bool]) {
    if ($Value) { return "true" }
    return "false"
  }
  if ($Value -is [byte] -or $Value -is [int16] -or $Value -is [int32] -or $Value -is [int64] -or $Value -is [single] -or $Value -is [double] -or $Value -is [decimal]) {
    return [string]::Format([System.Globalization.CultureInfo]::InvariantCulture, "{0}", $Value)
  }
  if ($Value -is [datetime]) { return Convert-ToJsonString $Value.ToString("o") }

  if ($Value -is [System.Collections.IDictionary]) {
    $parts = @()
    foreach ($key in $Value.Keys) {
      $parts += "$(Convert-ToJsonString ([string]$key)):$(Convert-ToJsonValue $Value[$key])"
    }
    return "{" + ($parts -join ",") + "}"
  }

  if ($Value -is [System.Collections.IEnumerable]) {
    $parts = @()
    foreach ($item in $Value) {
      $parts += Convert-ToJsonValue $item
    }
    return "[" + ($parts -join ",") + "]"
  }

  $properties = $Value.PSObject.Properties | Where-Object { $_.MemberType -match "Property" }
  $objectParts = @()
  foreach ($property in $properties) {
    $objectParts += "$(Convert-ToJsonString $property.Name):$(Convert-ToJsonValue $property.Value)"
  }
  return "{" + ($objectParts -join ",") + "}"
}

function New-EmptyStore {
  return @{
    decisions = @()
    approvals = @()
    feedback = @()
    learning = @{
      acceptedPatterns = @()
      rejectedPatterns = @()
      notes = @()
      updatedAt = $null
    }
  }
}

function Read-Store {
  if (!(Test-Path $DataPath)) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $DataPath) | Out-Null
    Convert-ToJsonText (New-EmptyStore) | Set-Content -Encoding UTF8 $DataPath
  }
  return Convert-FromJsonText (Get-Content -Raw -Encoding UTF8 $DataPath)
}

function Save-Store {
  param($Store)
  Convert-ToJsonText $Store | Set-Content -Encoding UTF8 $DataPath
}

function Get-DeviceFingerprint {
  $raw = "$env:COMPUTERNAME|$env:USERNAME|$env:PROCESSOR_IDENTIFIER"
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try {
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($raw)
    $hash = $sha.ComputeHash($bytes)
    return ([BitConverter]::ToString($hash) -replace "-", "").ToLowerInvariant()
  } finally {
    $sha.Dispose()
  }
}

function Read-LicenseCache {
  if (!(Test-Path $LicenseCachePath)) { return $null }
  try {
    return Convert-FromJsonText (Get-Content -Raw -Encoding UTF8 $LicenseCachePath)
  } catch {
    return $null
  }
}

function Save-LicenseCache {
  param($License)
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $LicenseCachePath) | Out-Null
  $safe = @{
    enterpriseId = $License.enterpriseId
    enterpriseName = $License.enterpriseName
    status = $License.status
    plan = $License.plan
    validUntil = $License.validUntil
    checkedAt = $License.checkedAt
    graceUntil = $License.graceUntil
    deviceId = $License.deviceId
    reason = $License.reason
  }
  Convert-ToJsonText $safe | Set-Content -Encoding UTF8 $LicenseCachePath
}

function Get-LicenseFromEnvironment {
  $status = $env:CLOUD_OS_LICENSE_STATUS
  if ([string]::IsNullOrWhiteSpace($status)) {
    if ($env:CLOUD_OS_REQUIRE_LICENSE -eq "1") { $status = "unconfigured" } else { $status = "active" }
  }
  $validUntil = $env:CLOUD_OS_LICENSE_EXPIRES_AT
  if ([string]::IsNullOrWhiteSpace($validUntil) -and $status -eq "active") {
    $validUntil = (Get-Date).AddYears(1).ToUniversalTime().ToString("o")
  }
  return @{
    enterpriseId = if ($env:CLOUD_OS_ENTERPRISE_ID) { $env:CLOUD_OS_ENTERPRISE_ID } else { "local-owner" }
    enterpriseName = if ($env:CLOUD_OS_ENTERPRISE_NAME) { $env:CLOUD_OS_ENTERPRISE_NAME } else { "Local Owner" }
    status = $status
    plan = if ($env:CLOUD_OS_LICENSE_PLAN) { $env:CLOUD_OS_LICENSE_PLAN } else { "owner" }
    validUntil = $validUntil
    checkedAt = (Get-Date).ToUniversalTime().ToString("o")
    graceUntil = (Get-Date).AddHours(72).ToUniversalTime().ToString("o")
    deviceId = Get-DeviceFingerprint
    reason = if ($status -eq "unconfigured") { "License endpoint is not configured." } else { "Local development license." }
  }
}

function Test-LicenseUsable {
  param($License)
  if ($null -eq $License) { return $false }
  if ($License.status -eq "active" -or $License.status -eq "grace") {
    if (![string]::IsNullOrWhiteSpace($License.validUntil)) {
      try {
        if ([datetime]::Parse($License.validUntil).ToUniversalTime() -lt (Get-Date).ToUniversalTime()) { return $false }
      } catch {
        return $false
      }
    }
    if ($License.status -eq "grace" -and ![string]::IsNullOrWhiteSpace($License.graceUntil)) {
      try {
        if ([datetime]::Parse($License.graceUntil).ToUniversalTime() -lt (Get-Date).ToUniversalTime()) { return $false }
      } catch {
        return $false
      }
    }
    return $true
  }
  return $false
}

function Get-LicenseStatus {
  $endpoint = $env:CLOUD_OS_LICENSE_ENDPOINT
  $enterpriseId = if ($env:CLOUD_OS_ENTERPRISE_ID) { $env:CLOUD_OS_ENTERPRISE_ID } else { "local-owner" }
  $deviceId = Get-DeviceFingerprint

  if (![string]::IsNullOrWhiteSpace($endpoint)) {
    try {
      $payload = @{
        enterpriseId = $enterpriseId
        deviceId = $deviceId
        app = "international-trade-cloud-os"
        version = "0.1.0"
      }
      $headers = @{}
      if (![string]::IsNullOrWhiteSpace($env:CLOUD_OS_LICENSE_TOKEN)) {
        $headers["Authorization"] = "Bearer $env:CLOUD_OS_LICENSE_TOKEN"
      }
      $response = Invoke-RestMethod -Uri $endpoint -Method Post -Headers $headers -Body (Convert-ToJsonText $payload) -ContentType "application/json" -TimeoutSec 12
      $license = @{
        enterpriseId = if ($response.enterpriseId) { $response.enterpriseId } else { $enterpriseId }
        enterpriseName = if ($response.enterpriseName) { $response.enterpriseName } else { $enterpriseId }
        status = if ($response.status) { $response.status } else { "inactive" }
        plan = if ($response.plan) { $response.plan } else { "standard" }
        validUntil = $response.validUntil
        checkedAt = (Get-Date).ToUniversalTime().ToString("o")
        graceUntil = (Get-Date).AddHours(72).ToUniversalTime().ToString("o")
        deviceId = $deviceId
        reason = $response.reason
      }
      Save-LicenseCache $license
      return $license
    } catch {
      $cached = Read-LicenseCache
      if ($cached -and ![string]::IsNullOrWhiteSpace($cached.graceUntil)) {
        try {
          if ([datetime]::Parse($cached.graceUntil).ToUniversalTime() -gt (Get-Date).ToUniversalTime()) {
            $cached.status = "grace"
            $cached.reason = "License center is unavailable. Temporary 72-hour grace mode is active."
            return $cached
          }
        } catch {}
      }
      return @{
        enterpriseId = $enterpriseId
        enterpriseName = $enterpriseId
        status = "unreachable"
        plan = $null
        validUntil = $null
        checkedAt = (Get-Date).ToUniversalTime().ToString("o")
        graceUntil = $null
        deviceId = $deviceId
        reason = $_.Exception.Message
      }
    }
  }

  $license = Get-LicenseFromEnvironment
  Save-LicenseCache $license
  return $license
}

function Assert-LicenseAllowed {
  $license = Get-LicenseStatus
  if (!(Test-LicenseUsable $license)) {
    return New-JsonResponse @{
      error = "Enterprise license is not active. Core service is stopped."
      license = $license
    } 403
  }
  return $null
}

function Read-TextFileSafe {
  param([string]$Path)
  if (!(Test-Path $Path -PathType Leaf)) {
    return @{ exists = $false; path = $Path; content = "" }
  }
  return @{ exists = $true; path = $Path; content = (Get-Content -Raw -Encoding UTF8 $Path) }
}

function Read-JsonFileSafe {
  param([string]$Path)
  if (!(Test-Path $Path -PathType Leaf)) {
    return @{ exists = $false; path = $Path; data = $null }
  }
  try {
    return @{ exists = $true; path = $Path; data = (Convert-FromJsonText (Get-Content -Raw -Encoding UTF8 $Path)) }
  } catch {
    return @{ exists = $true; path = $Path; data = $null; error = $_.Exception.Message }
  }
}

function Read-CloudJsonLight {
  param([string]$Path, [string[]]$Fields)
  if (!(Test-Path $Path -PathType Leaf)) {
    return @{ exists = $false; path = $Path; data = $null }
  }
  $text = Get-Content -Raw -Encoding UTF8 $Path
  $summary = @{}
  foreach ($field in $Fields) {
    if ($text -match ('"' + [regex]::Escape($field) + '"\s*:\s*"(.*?)"')) {
      $summary[$field] = $Matches[1]
    } elseif ($text -match ('"' + [regex]::Escape($field) + '"\s*:\s*(true|false|null|-?\d+(\.\d+)?)')) {
      $summary[$field] = $Matches[1]
    }
  }
  return @{ exists = $true; path = $Path; data = $summary }
}

function Invoke-CloudScript {
  param([string]$ScriptName, [string[]]$Arguments = @())
  $guard = Assert-LicenseAllowed
  if ($guard) { return $guard }
  $script = Join-Path $ProjectRoot $ScriptName
  if (!(Test-Path $script -PathType Leaf)) {
    $script = Join-Path $SourceRoot $ScriptName
  }
  if (!(Test-Path $script -PathType Leaf)) {
    $fallbackName = $ScriptName -replace "-from-root", ""
    $script = Join-Path $CloudRoot $fallbackName
  }
  if (!(Test-Path $script -PathType Leaf)) {
    return New-JsonResponse @{ error = "Cloud command not found: $ScriptName" } 404
  }
  try {
    $output = & $script @Arguments 2>&1 | Out-String
    return New-JsonResponse @{
      ok = $LASTEXITCODE -eq 0
      exitCode = $LASTEXITCODE
      output = $output
      ranAt = (Get-Date).ToString("o")
    }
  } catch {
    return New-JsonResponse @{ error = $_.Exception.Message } 500
  }
}

function Add-Item {
  param($ArrayObject, $Item)
  $items = @($ArrayObject)
  $items += $Item
  return $items
}

function Get-ContentType {
  param([string]$Path)
  switch ([System.IO.Path]::GetExtension($Path).ToLowerInvariant()) {
    ".html" { "text/html; charset=utf-8" }
    ".css" { "text/css; charset=utf-8" }
    ".js" { "application/javascript; charset=utf-8" }
    ".json" { "application/json; charset=utf-8" }
    ".svg" { "image/svg+xml" }
    default { "application/octet-stream" }
  }
}

function Invoke-JsonGet {
  param([string]$Url, [hashtable]$Headers = @{})
  try {
    $response = Invoke-WebRequest -Uri $Url -Headers $Headers -Method Get -TimeoutSec 15 -UseBasicParsing
    $data = Convert-FromJsonText $response.Content
    return @{ ok = $true; data = $data; error = $null }
  } catch {
    return @{ ok = $false; data = $null; error = $_.Exception.Message }
  }
}

function Invoke-XmlGet {
  param([string]$Url, [hashtable]$Headers = @{})
  try {
    $response = Invoke-WebRequest -Uri $Url -Headers $Headers -Method Get -TimeoutSec 15 -UseBasicParsing
    return @{ ok = $true; data = ([xml]$response.Content); error = $null }
  } catch {
    return @{ ok = $false; data = $null; error = $_.Exception.Message }
  }
}

function New-UnicodeString {
  param([int[]]$Codes)
  $chars = @()
  foreach ($code in $Codes) { $chars += [char]$code }
  return -join $chars
}

function Expand-SearchQuery {
  param([string]$Query)
  $expanded = " $Query "
  $pairs = @(
    @((New-UnicodeString @(21704,33832,20811,26031,22374)), "Kazakhstan"),
    @((New-UnicodeString @(24037,31243)), "engineering EPC infrastructure"),
    @((New-UnicodeString @(36152,26131)), "trade commerce"),
    @((New-UnicodeString @(22269,38469)), "international"),
    @((New-UnicodeString @(39033,30446)), "project"),
    @((New-UnicodeString @(22522,24314)), "infrastructure"),
    @((New-UnicodeString @(21512,21516)), "contract"),
    @((New-UnicodeString @(39118,38505)), "risk"),
    @((New-UnicodeString @(28165,20851)), "customs clearance"),
    @((New-UnicodeString @(21046,35009)), "sanctions"),
    @((New-UnicodeString @(21512,35268)), "compliance")
  )
  foreach ($pair in $pairs) {
    $expanded = $expanded -replace [regex]::Escape($pair[0]), " $($pair[1]) "
  }
  $expanded = ($expanded -replace "\s+", " ").Trim()
  if ($expanded -and $expanded -ne $Query) { return $expanded }
  return $Query
}

function Join-SearchTerms {
  param([object[]]$Terms)
  $clean = @()
  foreach ($term in $Terms) {
    if ($term -is [System.Collections.IEnumerable] -and $term -isnot [string]) {
      foreach ($nested in $term) {
        $nestedText = "$nested".Trim()
        if ($nestedText -and $clean -notcontains $nestedText) { $clean += $nestedText }
      }
      continue
    }
    $text = "$term".Trim()
    if ($text -and $clean -notcontains $text) { $clean += $text }
  }
  return (($clean -join " ") -replace "\s+", " ").Trim()
}

function Get-EnhancedSearchQueries {
  param([string]$Query)
  $base = Expand-SearchQuery $Query
  $kazakhstan = New-UnicodeString @(21704,33832,20811,26031,22374)
  $isKazakhstan = $Query -match [regex]::Escape($kazakhstan) -or $base -match "Kazakhstan"

  $tradeTerms = @(
    "EPC", "infrastructure", "engineering contractor", "construction", "procurement",
    "tender", "bid", "project pipeline", "customs clearance", "logistics",
    "tariff", "import export", "sanctions", "compliance", "contract risk",
    "payment risk", "financing", "local partner", "supplier", "government procurement"
  )
  $regionalTerms = @("Central Asia", "Kazakhstan", "Astana", "Almaty", "KAZAKH INVEST", "Samruk Kazyna", "site:.kz", "site:.ru")
  $socialTerms = @("Douyin", "Toutiao", "Telegram", "channel", "group", "video", "supplier", "project news", "construction site")
  $academicTerms = @("Kazakhstan", "infrastructure investment", "international trade", "EPC contract", "Belt and Road", "risk assessment", "logistics corridor")
  $libraryTerms = @("Kazakhstan", "Central Asia", "trade", "infrastructure", "construction", "economic corridor", "project finance")

  if (!$isKazakhstan) {
    $regionalTerms = @("Central Asia", "regional market", "tender", "procurement", "site:.kz", "site:.ru", "site:.uz", "site:.kg")
    $academicTerms = @("international trade", "infrastructure investment", "EPC contract", "risk assessment", "logistics corridor")
    $libraryTerms = @("international trade", "infrastructure", "construction", "project finance")
  }

  return @{
    original = $Query
    base = $base
    web = Join-SearchTerms @($base, $tradeTerms)
    google = Join-SearchTerms @($base, "latest", "news", "2025", "2026", "policy", "market entry", ($tradeTerms | Select-Object -First 10))
    regional = Join-SearchTerms @($base, $regionalTerms, "tender", "procurement", "construction", "logistics", "customs")
    social = Join-SearchTerms @($base, $socialTerms, "EPC", "tender", "contractor", "supplier")
    academic = Join-SearchTerms @($base, $academicTerms)
    library = Join-SearchTerms @($base, $libraryTerms)
  }
}

function New-CategoryQuery {
  param([string]$Id, [string]$Label, [bool]$Required, [string[]]$Terms, [string]$Reason, [string]$Base, [string]$Region)
  $queries = @()
  foreach ($term in $Terms) {
    $queries += (Join-SearchTerms @($Base, $Region, $term))
  }
  return @{
    category = $Id
    label = $Label
    required = $Required
    queries = $queries
    reason = $Reason
  }
}

function Get-V11SearchPlan {
  param([string]$Query)
  $enhanced = Get-EnhancedSearchQueries $Query
  $base = $enhanced.base
  $region = "Central Asia"
  $officialDomains = @("gov.kz", "gov.uz", "gov.kg", "tajinvest.tj", "gov.tm")
  if ($base -match "Kazakhstan") {
    $region = "Kazakhstan"
    $officialDomains = @("gov.kz", "primeminister.kz", "invest.gov.kz", "adilet.zan.kz", "goszakup.gov.kz")
  }

  $categories = @(
    (New-CategoryQuery "government_confirmation" "政府官网确认" $true @("official government", "ministry", "project owner", "project page") "先确认项目是否真实存在、主管部门是谁、是否处于计划或在建阶段。" $base $region),
    (New-CategoryQuery "procurement_tender" "招标采购" $true @("public tender", "procurement", "EPC tender", "contract awarded") "判断采购阶段、总包/分包机会、招标变化和可参与窗口。" $base $region),
    (New-CategoryQuery "customs_trade" "海关与贸易合规" $true @("customs", "HS code", "tariff", "certificate of origin", "export control") "核验关税、清关文件、出口管制、制裁和付款交付风险。" $base $region),
    (New-CategoryQuery "stakeholders" "项目负责人和开发者" $false @("project owner", "developer", "investor", "responsible person", "contact") "建立招商引资和项目推进联系人图谱。" $base $region),
    (New-CategoryQuery "research_feasibility" "科研与可行性" $false @("feasibility study", "EIA", "technical report", "paper", "standard", "library") "把论文、标准、图书馆资料转成可行性报告证据。" $base $region),
    (New-CategoryQuery "public_attention" "论坛社媒和视频关注度" $false @("YouTube", "TikTok", "Douyin", "Telegram", "forum", "public sentiment") "只作为关注度和传播选题信号，不能替代官方证据。" $base $region)
  )

  $projectPlan = @()
  foreach ($category in $categories) {
    foreach ($candidate in @($category.queries | Select-Object -First 3)) {
      if ($category.required) {
        foreach ($domain in @($officialDomains | Select-Object -First 4)) {
          $projectPlan += @{
            intent = $category.category
            label = $category.label
            query = "$candidate site:$domain"
            required = $true
            evidence_tier = "official"
            reason = $category.reason
          }
        }
      } else {
        $projectPlan += @{
          intent = $category.category
          label = $category.label
          query = $candidate
          required = $false
          evidence_tier = "supporting"
          reason = $category.reason
        }
      }
    }
  }

  return @{
    search_expansion = @{
      original_query = $Query
      region_key = $region
      chinese_terms = @(
        "哈萨克斯坦 工程 招标",
        "哈萨克斯坦 EPC 项目",
        "哈萨克斯坦 基础设施 投资",
        "哈萨克斯坦 在建项目",
        "哈萨克斯坦 计划建设项目"
      )
      english_terms = @(
        "Kazakhstan EPC project",
        "Kazakhstan infrastructure tender",
        "Kazakhstan public procurement engineering",
        "Kazakhstan mining infrastructure",
        "Kazakhstan logistics project owner developer",
        "Central Asia EPC opportunity"
      )
      russian_terms = @(
        "Казахстан инфраструктурный проект",
        "Казахстан тендер строительство",
        "Казахстан EPC подрядчик"
      )
      industry_terms = @("EPC", "public tender", "mining infrastructure", "railway logistics", "port logistics", "industrial park")
      risk_terms = @("sanctions compliance", "export control", "customs clearance", "payment risk")
      project_stage_terms = @("planned project", "under construction", "tender announced", "contract awarded")
      platform_terms = @("government website", "procurement portal", "YouTube", "TikTok", "Douyin", "Telegram")
      all_terms = @($enhanced.web, $enhanced.google, $enhanced.regional, $enhanced.social, $enhanced.academic, $enhanced.library)
    }
    enrichment = @{
      original = $Query
      base = $base
      regions = @($region)
      category_queries = $categories
    }
    project_search_plan = @($projectPlan | Select-Object -First 72)
    project_confirmation_gate = @{
      status = "lead_only"
      can_create_confirmed_project_record = $false
      can_create_lead_record = $true
      required_before_confirmed_project = @(
        "政府官网或官方采购页面确认项目存在、阶段、主管部门。",
        "海关或官方税则资料确认 HS code、关税、进口许可、清关文件。",
        "官方企业、政府或采购资料确认业主、开发者、投资方或负责人候选。",
        "证据进入证据核验，置信度和风险边界通过后，再进入项目库确认。"
      )
      blocked_until_confirmed = @(
        "招商引资正式发布",
        "客户外联",
        "报价",
        "合同或付款承诺",
        "交期或清关承诺",
        "公开视频发布"
      )
    }
    evidence_execution_brief = @{
      mode = "search_to_execution_brief"
      query = $Query
      region = $region
      verification_status = "search_plan_only"
      confidence = 30
      why_not_confirmed = "No live official evidence item has been attached yet. Search results are leads, not confirmed facts."
      evidence_requirements = @(
        "At least one official government or procurement page for project existence and stage.",
        "Customs authority, tariff database, or broker-verifiable source for HS code, tariff, import license, and clearance documents.",
        "Official company or government page for project owner, developer, investor, and responsible office/person.",
        "Academic, library, EIA, or technical report evidence for feasibility assumptions."
      )
      project_execution = @{
        can_create_project_record = $false
        record_status = "lead_only"
        next_actions = @(
          "Open the highest-priority official search URLs and collect title, URL, source date, and snippet.",
          "Attach collected official evidence to the project execution package.",
          "Classify the project as planned or under construction only after official evidence supports it.",
          "Map owner, developer, responsible office/person, tender status, customs impact, and next meeting task.",
          "Request human approval before outreach, quotation, publication, contract, payment, or customer promise."
        )
      }
      blocked_actions = @(
        "招商引资正式发布",
        "客户外联",
        "报价",
        "合同或付款承诺",
        "交期或清关承诺",
        "公开视频发布"
      )
    }
    project_library_rule = "Only create confirmed investment-promotion records after government, customs, procurement, regulator, or official company evidence is attached."
    answer_rule = "Final answers must separate verified facts, weak signals, assumptions, risks, and next actions."
    safety = "Search only; public posting, outreach, quotation, contract, payment, and customer commitments require human approval."
  }
}

function New-SearchLinkItem {
  param([string]$Title, [string]$Url, [string]$Summary, [string]$Meta)
  return @{
    title = $Title
    url = $Url
    summary = $Summary
    meta = $Meta
  }
}

function Convert-RssToSearchItems {
  param($Rss, [string]$Meta, [int]$Limit = 6)
  $items = @()
  if ($Rss.data.rss.channel.item) {
    $items = @($Rss.data.rss.channel.item | Select-Object -First $Limit | ForEach-Object {
      @{
        title = $_.title
        url = $_.link
        summary = $_.description
        meta = $Meta
      }
    })
  }
  return $items
}

function Search-BingRss {
  param([string]$Query, [string]$Source, [string]$Meta, [string]$Market = "zh-CN")
  $rssUrl = "https://www.bing.com/search?q={0}&format=rss&mkt={1}" -f ([uri]::EscapeDataString($Query)), $Market
  $rss = Invoke-XmlGet -Url $rssUrl -Headers @{ "User-Agent" = "Mozilla/5.0" }
  if (!$rss.ok) {
    return @{ source = $Source; ok = $false; error = $rss.error; items = @() }
  }
  return @{ source = $Source; ok = $true; error = $null; items = @(Convert-RssToSearchItems $rss $Meta 6) }
}

function Search-Bing {
  param([string]$Query)
  $key = $env:BING_SEARCH_KEY
  $enhanced = Get-EnhancedSearchQueries $Query
  if ([string]::IsNullOrWhiteSpace($key)) {
    $fallbackQuery = $enhanced.web
    $result = Search-BingRss $fallbackQuery "bing" "Bing Web RSS fallback" "zh-CN"
    $result.query = $fallbackQuery
    $result.error = if ($result.ok) { "BING_SEARCH_KEY is not configured; using Bing RSS fallback." } else { "BING_SEARCH_KEY is not configured, and Bing RSS fallback failed: $($result.error)" }
    return $result
  }

  $endpoint = $env:BING_SEARCH_ENDPOINT
  if ([string]::IsNullOrWhiteSpace($endpoint)) {
    $endpoint = "https://api.bing.microsoft.com/v7.0/search"
  }
  $url = "{0}?q={1}&count=6&mkt=zh-CN" -f $endpoint, ([uri]::EscapeDataString($enhanced.web))
  $result = Invoke-JsonGet -Url $url -Headers @{ "Ocp-Apim-Subscription-Key" = $key }
  if (!$result.ok) {
    return @{ source = "bing"; ok = $false; error = $result.error; items = @() }
  }

  $items = @()
  if ($result.data.webPages.value) {
    $items = @($result.data.webPages.value | ForEach-Object {
      @{
        title = $_.name
        url = $_.url
        summary = $_.snippet
        meta = "Bing Web"
      }
    })
  }
  return @{ source = "bing"; ok = $true; error = $null; query = $enhanced.web; items = $items }
}

function Search-Google {
  param([string]$Query)
  $enhanced = Get-EnhancedSearchQueries $Query
  $fallbackQuery = $enhanced.google
  $googleUrl = "https://www.google.com/search?q={0}" -f ([uri]::EscapeDataString($fallbackQuery))
  $rssUrl = "https://news.google.com/rss/search?q={0}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans" -f ([uri]::EscapeDataString($fallbackQuery))
  $rss = Invoke-XmlGet -Url $rssUrl -Headers @{ "User-Agent" = "Mozilla/5.0" }
  $items = @(
    (New-SearchLinkItem "Open Google web search" $googleUrl "Google public web search entry. Direct scraping is not used without a Google API key." "Google Web")
  )
  if ($rss.ok) {
    $items += @(Convert-RssToSearchItems $rss "Google News RSS" 5)
    return @{ source = "google"; ok = $true; error = "Using Google News RSS plus Google web search entry."; query = $fallbackQuery; items = $items }
  }
  return @{ source = "google"; ok = $true; error = "Google News RSS failed: $($rss.error). Showing Google web search entry."; query = $fallbackQuery; items = $items }
}

function Search-YandexRegional {
  param([string]$Query)
  $enhanced = Get-EnhancedSearchQueries $Query
  $fallbackQuery = $enhanced.regional
  $yandexUrl = "https://yandex.com/search/?text={0}" -f ([uri]::EscapeDataString($fallbackQuery))
  $regionalQuery = "$fallbackQuery (site:.kz OR site:.ru OR site:.uz OR site:.kg OR site:.tj OR site:.tm)"
  $regional = Search-BingRss $regionalQuery "yandex" "Central Asia/Russia regional web fallback" "ru-RU"
  $items = @(
    (New-SearchLinkItem "Open Yandex regional search" $yandexUrl "Yandex search entry for Russia/Central Asia oriented discovery." "Yandex Web")
  )
  if ($regional.ok) { $items += @($regional.items | Select-Object -First 5) }
  return @{ source = "yandex"; ok = $true; error = "Yandex public entry plus regional web fallback."; query = $fallbackQuery; items = $items }
}

function Search-SocialChannels {
  param([string]$Query)
  $enhanced = Get-EnhancedSearchQueries $Query
  $fallbackQuery = $enhanced.social
  $socialQuery = "$fallbackQuery (site:douyin.com OR site:toutiao.com OR site:t.me OR site:telegram.me OR site:iesdouyin.com)"
  $result = Search-BingRss $socialQuery "social" "Douyin/Toutiao/Telegram indexed web fallback" "zh-CN"
  $items = @(
    (New-SearchLinkItem "Open Douyin search" ("https://www.douyin.com/search/{0}" -f ([uri]::EscapeDataString($Query))) "Douyin in-app/web search entry." "Douyin"),
    (New-SearchLinkItem "Open Toutiao search" ("https://so.toutiao.com/search?keyword={0}" -f ([uri]::EscapeDataString($Query))) "ByteDance Toutiao search entry." "Toutiao"),
    (New-SearchLinkItem "Open Telegram public search" ("https://t.me/s/{0}" -f ([uri]::EscapeDataString($Query))) "Telegram public channel entry; exact channel names require manual selection." "Telegram")
  )
  if ($result.ok) { $items += @($result.items | Select-Object -First 6) }
  return @{ source = "social"; ok = $true; error = "Using public indexed results plus Douyin/Toutiao/Telegram entry links."; query = $fallbackQuery; items = $items }
}

function Search-OpenAlex {
  param([string]$Query)
  $enhanced = Get-EnhancedSearchQueries $Query
  $fallbackQuery = $enhanced.academic
  $fields = "id,doi,display_name,publication_year,primary_location,concepts,cited_by_count"
  $url = "https://api.openalex.org/works?search={0}&per-page=6&select={1}" -f ([uri]::EscapeDataString($fallbackQuery)), $fields
  $result = Invoke-JsonGet -Url $url -Headers @{ "User-Agent" = "decision-hub/1.0 (mailto:local@example.com)" }
  if (!$result.ok) {
    return @{ source = "academic"; ok = $false; error = $result.error; items = @() }
  }
  $items = @()
  if ($result.data.results) {
    $items = @($result.data.results | ForEach-Object {
      $sourceName = ""
      if ($_.primary_location -and $_.primary_location.source) {
        $sourceName = $_.primary_location.source.display_name
      }
      $concepts = @($_.concepts | Select-Object -First 3 | ForEach-Object { $_.display_name }) -join ", "
      @{
        title = $_.display_name
        url = if ($_.doi) { $_.doi } else { $_.id }
        summary = if ($concepts) { "Topics: $concepts" } else { "OpenAlex academic record." }
        meta = "$($_.publication_year) | $sourceName | citations $($_.cited_by_count) | OpenAlex fallback"
      }
    })
  }
  return @{ source = "academic"; ok = $true; error = "Semantic Scholar unavailable/rate-limited; using OpenAlex fallback."; query = $fallbackQuery; items = $items }
}

function Search-Academic {
  param([string]$Query)
  $fields = "title,url,abstract,year,authors,citationCount,venue"
  $enhanced = Get-EnhancedSearchQueries $Query
  $semanticQuery = $enhanced.academic
  $url = "https://api.semanticscholar.org/graph/v1/paper/search?query={0}&limit=6&fields={1}" -f ([uri]::EscapeDataString($semanticQuery)), $fields
  $result = Invoke-JsonGet -Url $url
  if (!$result.ok) {
    return Search-OpenAlex $Query
  }

  $items = @()
  if ($result.data.data) {
    $items = @($result.data.data | ForEach-Object {
      $authors = @($_.authors | Select-Object -First 3 | ForEach-Object { $_.name }) -join ", "
      @{
        title = $_.title
        url = $_.url
        summary = if ($_.abstract) { $_.abstract } else { "No abstract available." }
        meta = "$($_.year) | $($_.venue) | citations $($_.citationCount) | $authors"
      }
    })
  }
  if ($items.Count -eq 0) {
    return Search-OpenAlex $Query
  }
  return @{ source = "academic"; ok = $true; error = $null; query = $semanticQuery; items = $items }
}

function Search-LibraryOfCongress {
  param([string]$Query)
  $enhanced = Get-EnhancedSearchQueries $Query
  $fallbackQuery = $enhanced.library
  $url = "https://www.loc.gov/books/?fo=json&c=6&q={0}" -f ([uri]::EscapeDataString($fallbackQuery))
  $result = Invoke-JsonGet -Url $url -Headers @{ "User-Agent" = "decision-hub/1.0" }
  if (!$result.ok) {
    return Search-InternetArchive $Query
  }
  $items = @()
  if ($result.data.results) {
    $items = @($result.data.results | Select-Object -First 6 | ForEach-Object {
      $contributors = @($_.contributor | Select-Object -First 3) -join ", "
      @{
        title = $_.title
        url = $_.url
        summary = if ($contributors) { "$contributors | $($_.date)" } else { "Library of Congress catalog record | $($_.date)" }
        meta = "Library of Congress fallback"
      }
    })
  }
  return @{ source = "library"; ok = $true; error = "Open Library had no matching records; using Library of Congress fallback."; query = $fallbackQuery; items = $items }
}

function Search-InternetArchive {
  param([string]$Query)
  $enhanced = Get-EnhancedSearchQueries $Query
  $fallbackQuery = $enhanced.library
  $items = @()
  $lastError = $null
  $queries = @($fallbackQuery, $Query)
  $kazakhstan = New-UnicodeString @(21704,33832,20811,26031,22374)
  if ($Query -match [regex]::Escape($kazakhstan)) {
    $queries += @(
      "Kazakhstan infrastructure trade",
      "Kazakhstan engineering trade",
      "Kazakhstan foreign trade construction"
    )
  }
  foreach ($candidate in @($queries | Where-Object { ![string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique)) {
    $url = "https://archive.org/advancedsearch.php?q={0}&fl[]=title&fl[]=creator&fl[]=date&fl[]=identifier&fl[]=description&rows=6&output=json" -f ([uri]::EscapeDataString($candidate))
    $result = Invoke-JsonGet -Url $url -Headers @{ "User-Agent" = "decision-hub/1.0" }
    if (!$result.ok) {
      $lastError = $result.error
      continue
    }
    if ($result.data.response.docs) {
      $items = @($result.data.response.docs | Select-Object -First 6 | ForEach-Object {
        $creator = "Unknown creator"
        if ($_.creator) {
          $creator = @($_.creator | Select-Object -First 3) -join ", "
        }
        $identifier = $_.identifier
        @{
          title = $_.title
          url = "https://archive.org/details/$identifier"
          summary = "$creator | $($_.date)"
          meta = "Internet Archive library fallback"
        }
      })
    }
    if ($items.Count -gt 0) { break }
  }
  if ($items.Count -eq 0 -and $lastError) {
    return @{ source = "library"; ok = $false; error = $lastError; items = @() }
  }
  return @{ source = "library"; ok = $true; error = "Open Library/Library of Congress unavailable or empty; using Internet Archive fallback."; query = $fallbackQuery; items = $items }
}

function Search-Library {
  param([string]$Query)
  $enhanced = Get-EnhancedSearchQueries $Query
  $libraryQuery = $enhanced.library
  $url = "https://openlibrary.org/search.json?q={0}&limit=6" -f ([uri]::EscapeDataString($libraryQuery))
  $result = Invoke-JsonGet -Url $url -Headers @{ "User-Agent" = "decision-hub/1.0" }
  if (!$result.ok) {
    return Search-LibraryOfCongress $Query
  }

  $items = @()
  if ($result.data.docs) {
    $items = @($result.data.docs | ForEach-Object {
      $author = "Unknown author"
      if ($_.author_name) {
        $author = @($_.author_name | Select-Object -First 3) -join ", "
      }
      $bookUrl = "https://openlibrary.org/search?q={0}" -f ([uri]::EscapeDataString($libraryQuery))
      if ($_.key) {
        $bookUrl = "https://openlibrary.org$($_.key)"
      }
      @{
        title = $_.title
        url = $bookUrl
        summary = "$author | first published $($_.first_publish_year) | editions $($_.edition_count)"
        meta = "Open Library"
      }
    })
  }
  if ($items.Count -eq 0) {
    return Search-LibraryOfCongress $Query
  }
  return @{ source = "library"; ok = $true; error = $null; query = $libraryQuery; items = $items }
}

function Test-AnyPattern {
  param([string]$Text, [string[]]$Patterns)
  foreach ($pattern in $Patterns) {
    if ($Text -match $pattern) { return $true }
  }
  return $false
}

function Get-ObjectField {
  param($Object, [string]$Name, $Default = $null)
  if ($null -eq $Object) { return $Default }
  if ($Object -is [System.Collections.IDictionary] -and $Object.Contains($Name)) {
    return $Object[$Name]
  }
  $property = $Object.PSObject.Properties[$Name]
  if ($property) { return $property.Value }
  return $Default
}

function Normalize-List {
  param($Value)
  if ($null -eq $Value) { return @() }
  if ($Value -is [string]) { return @($Value) }
  if ($Value -is [System.Collections.IEnumerable]) {
    $items = @()
    foreach ($item in $Value) { $items += $item }
    return $items
  }
  return @($Value)
}

function New-DecisionAnalysis {
  param($Body)
  $options = @(Normalize-List (Get-ObjectField $Body "options") | Where-Object { ![string]::IsNullOrWhiteSpace((Get-ObjectField $_ "name" "")) })
  if ($options.Count -eq 0) {
    $options = @(@{ name = "Collect more evidence"; evidence = "Evidence is not enough."; risk = "Action may be delayed." })
  }

  $criteria = @(Normalize-List (Get-ObjectField $Body "criteria") | Where-Object { ![string]::IsNullOrWhiteSpace((Get-ObjectField $_ "name" "")) })
  if ($criteria.Count -eq 0) {
    $criteria = @(
      @{ name = "benefit"; weight = 4 },
      @{ name = "risk"; weight = 4 },
      @{ name = "cost"; weight = 3 },
      @{ name = "reversibility"; weight = 3 }
    )
  }

  $positive = @("evidence", "data", "validated", "user", "revenue", "saving", "growth", "clear", "low cost", "pilot", "rollback", "reversible", "staged")
  $negative = @("high risk", "irreversible", "compliance", "privacy", "security", "expensive", "delay", "unknown", "uncertain", "missing", "blocked")
  $approvalTriggers = @("compliance", "budget", "people", "customer promise", "irreversible", "security", "privacy")

  $scored = @()
  foreach ($option in $options) {
    $optionName = [string](Get-ObjectField $option "name" "")
    $optionEvidence = [string](Get-ObjectField $option "evidence" "")
    $optionRisk = [string](Get-ObjectField $option "risk" "")
    $text = "$optionName $optionEvidence $optionRisk"
    $score = 50
    if (Test-AnyPattern $text $positive) { $score += 18 }
    if ($text -match "pilot|rollback|reversible|staged") { $score += 10 }
    if (Test-AnyPattern $text $negative) { $score -= 16 }
    foreach ($criterion in $criteria) {
      $weight = [int](Get-ObjectField $criterion "weight" 1)
      if ($weight -le 0) { $weight = 1 }
      if ($text -match [regex]::Escape([string](Get-ObjectField $criterion "name" ""))) {
        $score += [Math]::Min(10, $weight * 2)
      }
    }
    $score = [Math]::Max(0, [Math]::Min(100, $score))
    $scored += @{
      name = $optionName
      score = $score
      evidence = $optionEvidence
      risk = $optionRisk
    }
  }

  $remaining = @($scored)
  $ranked = @()
  while ($remaining.Count -gt 0) {
    $bestIndex = 0
    for ($i = 1; $i -lt $remaining.Count; $i++) {
      if ([int]$remaining[$i].score -gt [int]$remaining[$bestIndex].score) {
        $bestIndex = $i
      }
    }
    $ranked += $remaining[$bestIndex]
    $nextRemaining = @()
    for ($i = 0; $i -lt $remaining.Count; $i++) {
      if ($i -ne $bestIndex) {
        $nextRemaining += $remaining[$i]
      }
    }
    $remaining = $nextRemaining
  }
  $top = $null
  foreach ($item in $scored) {
    if ($null -eq $top -or [int]$item.score -gt [int]$top.score) {
      $top = $item
    }
  }
  $confidence = "low"
  if ($top.score -ge 75) {
    $confidence = "high"
  } elseif ($top.score -ge 58) {
    $confidence = "medium"
  }

  $contextText = [string](Get-ObjectField $Body "context" "")
  $askNeeded = ($confidence -ne "high") -or (Test-AnyPattern $contextText $approvalTriggers)

  return @{
    ranked = $ranked
    recommendation = "Choose '$($top.name)' and move forward with a small verifiable step plus a rollback point."
    confidence = $confidence
    askNeeded = $askNeeded
    rationale = @(
      "Scoring considers benefit, risk, cost, reversibility, and evidence strength.",
      "High-impact or irreversible items enter the approval flow.",
      "Your reply is written to the learning record for future decisions."
    )
  }
}

function New-JsonResponse {
  param($Data, [int]$Status = 200)
  return @{
    Status = $Status
    ContentType = "application/json; charset=utf-8"
    Body = [System.Text.Encoding]::UTF8.GetBytes((Convert-ToJsonText $Data))
  }
}

function New-TextResponse {
  param([string]$Text, [string]$ContentType = "text/plain; charset=utf-8", [int]$Status = 200)
  return @{
    Status = $Status
    ContentType = $ContentType
    Body = [System.Text.Encoding]::UTF8.GetBytes($Text)
  }
}

function Invoke-ProjectPipeline {
  param($Body)
  $guard = Assert-LicenseAllowed
  if ($guard) { return $guard }

  $topic = "$($Body.topic)".Trim()
  if ([string]::IsNullOrWhiteSpace($topic)) {
    $topic = "$($Body.query)".Trim()
  }
  if ([string]::IsNullOrWhiteSpace($topic)) {
    $topic = "$($Body.title)".Trim()
  }
  if ([string]::IsNullOrWhiteSpace($topic)) {
    return New-JsonResponse @{ error = "Project topic is required." } 400
  }

  $country = "$($Body.country)".Trim()
  if ([string]::IsNullOrWhiteSpace($country)) { $country = "Kazakhstan" }
  $evidence = @($Body.evidence)
  $payloadPath = Join-Path ([System.IO.Path]::GetTempPath()) ("v11-project-pipeline-{0}.json" -f ([guid]::NewGuid().ToString("N")))
  $scriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("v11-project-pipeline-{0}.py" -f ([guid]::NewGuid().ToString("N")))
  $payload = @{
    topic = $topic
    country = $country
    evidence = $evidence
  }
  Convert-ToJsonText $payload | Set-Content -Encoding UTF8 $payloadPath

  @'
import json
import sys
from pathlib import Path

project_root = Path(sys.argv[1])
payload_path = Path(sys.argv[2])
sys.path.insert(0, str(project_root))

from backend.services.project_intelligence_service import build_project_pipeline

payload = json.loads(payload_path.read_text(encoding="utf-8-sig"))
result = build_project_pipeline(
    str(payload.get("topic") or ""),
    str(payload.get("country") or "Kazakhstan"),
    payload.get("evidence") if isinstance(payload.get("evidence"), list) else [],
    persist=True,
)
print(json.dumps(result, ensure_ascii=True))
'@ | Set-Content -Encoding UTF8 $scriptPath

  try {
    $python = Get-Command python -ErrorAction Stop
    $output = & $python.Source $scriptPath $ProjectRoot $payloadPath 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
      return New-JsonResponse @{ error = "Project pipeline failed."; output = $output } 500
    }
    return New-JsonResponse (Convert-FromJsonText $output)
  } catch {
    return New-JsonResponse @{ error = "Project pipeline failed."; detail = $_.Exception.Message } 500
  } finally {
    Remove-Item -LiteralPath $payloadPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $scriptPath -Force -ErrorAction SilentlyContinue
  }
}

function Invoke-ProjectLibrary {
  $guard = Assert-LicenseAllowed
  if ($guard) { return $guard }

  $scriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("v11-project-library-{0}.py" -f ([guid]::NewGuid().ToString("N")))
  @'
import json
import sys
from pathlib import Path

project_root = Path(sys.argv[1])
sys.path.insert(0, str(project_root))

from backend.services.project_intelligence_service import read_project_library

print(json.dumps(read_project_library(), ensure_ascii=True))
'@ | Set-Content -Encoding UTF8 $scriptPath

  try {
    $python = Get-Command python -ErrorAction Stop
    $oldErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
      $output = & $python.Source $scriptPath $ProjectRoot 2>&1 | Out-String
      $exitCode = $LASTEXITCODE
    } finally {
      $ErrorActionPreference = $oldErrorActionPreference
    }
    if ($exitCode -ne 0) {
      return New-JsonResponse @{ error = "Project library failed."; output = $output } 500
    }
    return New-JsonResponse (Convert-FromJsonText $output)
  } catch {
    return New-JsonResponse @{ error = "Project library failed."; detail = $_.Exception.Message; output = $output } 500
  } finally {
    Remove-Item -LiteralPath $scriptPath -Force -ErrorAction SilentlyContinue
  }
}

function Invoke-VideoCenter {
  param($Body)
  $guard = Assert-LicenseAllowed
  if ($guard) { return $guard }

  $topic = "$($Body.topic)".Trim()
  if ([string]::IsNullOrWhiteSpace($topic)) {
    $topic = "$($Body.query)".Trim()
  }
  if ([string]::IsNullOrWhiteSpace($topic)) {
    $topic = "engineering trade project"
  }
  $countries = @($Body.countries)
  if ($countries.Count -eq 0) {
    $country = "$($Body.country)".Trim()
    if ([string]::IsNullOrWhiteSpace($country)) { $country = "Kazakhstan" }
    $countries = @($country)
  }
  $industries = @($Body.industries)
  if ($industries.Count -eq 0) {
    $industry = "$($Body.industry)".Trim()
    if ([string]::IsNullOrWhiteSpace($industry)) { $industry = "infrastructure" }
    $industries = @($industry)
  }

  $payloadPath = Join-Path ([System.IO.Path]::GetTempPath()) ("v11-video-center-{0}.json" -f ([guid]::NewGuid().ToString("N")))
  $scriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("v11-video-center-{0}.py" -f ([guid]::NewGuid().ToString("N")))
  Convert-ToJsonText @{ topic = $topic; countries = $countries; industries = $industries } | Set-Content -Encoding UTF8 $payloadPath

  @'
import json
import sys
from pathlib import Path

project_root = Path(sys.argv[1])
payload_path = Path(sys.argv[2])
sys.path.insert(0, str(project_root))

from backend.services.intelligence_center_service import build_video_production_center

payload = json.loads(payload_path.read_text(encoding="utf-8-sig"))
result = build_video_production_center(
    [str(payload.get("topic") or "engineering trade project")],
    payload.get("countries") if isinstance(payload.get("countries"), list) else ["Kazakhstan"],
    payload.get("industries") if isinstance(payload.get("industries"), list) else ["infrastructure"],
)
print(json.dumps(result, ensure_ascii=True))
'@ | Set-Content -Encoding UTF8 $scriptPath

  try {
    $python = Get-Command python -ErrorAction Stop
    $oldErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
      $output = & $python.Source $scriptPath $ProjectRoot $payloadPath 2>&1 | Out-String
      $exitCode = $LASTEXITCODE
    } finally {
      $ErrorActionPreference = $oldErrorActionPreference
    }
    if ($exitCode -ne 0) {
      return New-JsonResponse @{ error = "Video center failed."; output = $output } 500
    }
    return New-JsonResponse (Convert-FromJsonText $output)
  } catch {
    return New-JsonResponse @{ error = "Video center failed."; detail = $_.Exception.Message; output = $output } 500
  } finally {
    Remove-Item -LiteralPath $payloadPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $scriptPath -Force -ErrorAction SilentlyContinue
  }
}

function Invoke-IntelligenceBrief {
  param($Body)
  $guard = Assert-LicenseAllowed
  if ($guard) { return $guard }

  $topic = "$($Body.topic)".Trim()
  if ([string]::IsNullOrWhiteSpace($topic)) {
    $topic = "$($Body.query)".Trim()
  }
  if ([string]::IsNullOrWhiteSpace($topic)) {
    $topic = "international engineering trade"
  }
  $countries = @($Body.countries)
  if ($countries.Count -eq 0) {
    $country = "$($Body.country)".Trim()
    if ([string]::IsNullOrWhiteSpace($country)) { $country = "Kazakhstan" }
    $countries = @($country)
  }
  $industries = @($Body.industries)
  if ($industries.Count -eq 0) {
    $industry = "$($Body.industry)".Trim()
    if ([string]::IsNullOrWhiteSpace($industry)) { $industry = "infrastructure" }
    $industries = @($industry)
  }
  $items = @($Body.items)

  $payloadPath = Join-Path ([System.IO.Path]::GetTempPath()) ("v11-intelligence-brief-{0}.json" -f ([guid]::NewGuid().ToString("N")))
  $scriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("v11-intelligence-brief-{0}.py" -f ([guid]::NewGuid().ToString("N")))
  Convert-ToJsonText @{ topic = $topic; countries = $countries; industries = $industries; items = $items } | Set-Content -Encoding UTF8 $payloadPath

  @'
import json
import sys
from pathlib import Path

project_root = Path(sys.argv[1])
payload_path = Path(sys.argv[2])
sys.path.insert(0, str(project_root))

from backend.services.intelligence_center_service import generate_intelligence_brief

payload = json.loads(payload_path.read_text(encoding="utf-8-sig"))
result = generate_intelligence_brief(
    [str(payload.get("topic") or "international engineering trade")],
    payload.get("countries") if isinstance(payload.get("countries"), list) else ["Kazakhstan"],
    payload.get("industries") if isinstance(payload.get("industries"), list) else ["infrastructure"],
    payload.get("items") if isinstance(payload.get("items"), list) else [],
)
print(json.dumps(result, ensure_ascii=True))
'@ | Set-Content -Encoding UTF8 $scriptPath

  try {
    $python = Get-Command python -ErrorAction Stop
    $oldErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
      $output = & $python.Source $scriptPath $ProjectRoot $payloadPath 2>&1 | Out-String
      $exitCode = $LASTEXITCODE
    } finally {
      $ErrorActionPreference = $oldErrorActionPreference
    }
    if ($exitCode -ne 0) {
      return New-JsonResponse @{ error = "Intelligence brief failed."; output = $output } 500
    }
    return New-JsonResponse (Convert-FromJsonText $output)
  } catch {
    return New-JsonResponse @{ error = "Intelligence brief failed."; detail = $_.Exception.Message; output = $output } 500
  } finally {
    Remove-Item -LiteralPath $payloadPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $scriptPath -Force -ErrorAction SilentlyContinue
  }
}

function Invoke-TeamExecution {
  param($Body)
  $guard = Assert-LicenseAllowed
  if ($guard) { return $guard }

  $objective = "$($Body.objective)".Trim()
  if ([string]::IsNullOrWhiteSpace($objective)) {
    $objective = "$($Body.query)".Trim()
  }
  if ([string]::IsNullOrWhiteSpace($objective)) {
    $objective = "$($Body.topic)".Trim()
  }
  if ([string]::IsNullOrWhiteSpace($objective)) {
    return New-JsonResponse @{ error = "Team execution objective is required." } 400
  }

  $country = "$($Body.country)".Trim()
  if ([string]::IsNullOrWhiteSpace($country)) { $country = "Kazakhstan" }
  $industries = @($Body.industries)
  if ($industries.Count -eq 0) { $industries = @("infrastructure", "mining", "logistics", "energy") }
  $evidence = @($Body.evidence)
  $audience = "$($Body.audience)".Trim()
  if ([string]::IsNullOrWhiteSpace($audience)) { $audience = "internal" }

  $payloadPath = Join-Path ([System.IO.Path]::GetTempPath()) ("v11-team-execution-{0}.json" -f ([guid]::NewGuid().ToString("N")))
  $scriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("v11-team-execution-{0}.py" -f ([guid]::NewGuid().ToString("N")))
  $payload = @{
    objective = $objective
    country = $country
    industries = $industries
    evidence = $evidence
    audience = $audience
  }
  Convert-ToJsonText $payload | Set-Content -Encoding UTF8 $payloadPath

  @'
import json
import sys
from pathlib import Path

project_root = Path(sys.argv[1])
payload_path = Path(sys.argv[2])
sys.path.insert(0, str(project_root))

from backend.services.team_execution_service import build_team_execution_package

payload = json.loads(payload_path.read_text(encoding="utf-8-sig"))
result = build_team_execution_package(
    str(payload.get("objective") or ""),
    country=str(payload.get("country") or "Kazakhstan"),
    industries=payload.get("industries") if isinstance(payload.get("industries"), list) else ["infrastructure", "mining", "logistics", "energy"],
    evidence=payload.get("evidence") if isinstance(payload.get("evidence"), list) else [],
    audience=str(payload.get("audience") or "internal"),
)
print(json.dumps(result, ensure_ascii=True))
'@ | Set-Content -Encoding UTF8 $scriptPath

  try {
    $python = Get-Command python -ErrorAction Stop
    $output = & $python.Source $scriptPath $ProjectRoot $payloadPath 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
      return New-JsonResponse @{ error = "Team execution failed."; output = $output } 500
    }
    return New-JsonResponse (Convert-FromJsonText $output)
  } catch {
    return New-JsonResponse @{ error = "Team execution failed."; detail = $_.Exception.Message } 500
  } finally {
    Remove-Item -LiteralPath $payloadPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $scriptPath -Force -ErrorAction SilentlyContinue
  }
}

function Invoke-TeamResponse {
  param($Body)
  $guard = Assert-LicenseAllowed
  if ($guard) { return $guard }

  $question = "$($Body.question)".Trim()
  if ([string]::IsNullOrWhiteSpace($question)) {
    $question = "$($Body.query)".Trim()
  }
  if ([string]::IsNullOrWhiteSpace($question)) {
    $question = "$($Body.topic)".Trim()
  }
  if ([string]::IsNullOrWhiteSpace($question)) {
    return New-JsonResponse @{ error = "Team response question is required." } 400
  }

  $country = "$($Body.country)".Trim()
  if ([string]::IsNullOrWhiteSpace($country)) { $country = "Kazakhstan" }
  $industries = @($Body.industries)
  if ($industries.Count -eq 0) {
    $industry = "$($Body.industry)".Trim()
    if ([string]::IsNullOrWhiteSpace($industry)) { $industry = "infrastructure,mining,logistics,energy" }
    $industries = @($industry -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ })
  }
  $evidence = @($Body.evidence)
  $metadata = @{
    country = $country
    industries = $industries
    project = "$($Body.project)".Trim()
    stage = "$($Body.stage)".Trim()
  }

  $payloadPath = Join-Path ([System.IO.Path]::GetTempPath()) ("v11-team-response-{0}.json" -f ([guid]::NewGuid().ToString("N")))
  $scriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("v11-team-response-{0}.py" -f ([guid]::NewGuid().ToString("N")))
  Convert-ToJsonText @{ question = $question; metadata = $metadata; evidence = $evidence } | Set-Content -Encoding UTF8 $payloadPath

  @'
import json
import sys
from pathlib import Path

project_root = Path(sys.argv[1])
payload_path = Path(sys.argv[2])
sys.path.insert(0, str(project_root))

from backend.services.team_response_service import build_team_response_pack

payload = json.loads(payload_path.read_text(encoding="utf-8-sig"))
result = build_team_response_pack(
    str(payload.get("question") or ""),
    metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
    evidence=payload.get("evidence") if isinstance(payload.get("evidence"), list) else [],
    persist=True,
)
print(json.dumps(result, ensure_ascii=True))
'@ | Set-Content -Encoding UTF8 $scriptPath

  try {
    $python = Get-Command python -ErrorAction Stop
    $output = & $python.Source $scriptPath $ProjectRoot $payloadPath 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
      return New-JsonResponse @{ error = "Team response failed."; output = $output } 500
    }
    return New-JsonResponse (Convert-FromJsonText $output)
  } catch {
    return New-JsonResponse @{ error = "Team response failed."; detail = $_.Exception.Message } 500
  } finally {
    Remove-Item -LiteralPath $payloadPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $scriptPath -Force -ErrorAction SilentlyContinue
  }
}

function Invoke-WarRoomBuild {
  param($Body)
  $guard = Assert-LicenseAllowed
  if ($guard) { return $guard }

  $objective = "$($Body.objective)".Trim()
  if ([string]::IsNullOrWhiteSpace($objective)) {
    $objective = "$($Body.query)".Trim()
  }
  if ([string]::IsNullOrWhiteSpace($objective)) {
    $objective = "$($Body.topic)".Trim()
  }
  if ([string]::IsNullOrWhiteSpace($objective)) {
    return New-JsonResponse @{ error = "War room objective is required." } 400
  }

  $country = "$($Body.country)".Trim()
  if ([string]::IsNullOrWhiteSpace($country)) { $country = "Kazakhstan" }
  $industries = @($Body.industries)
  if ($industries.Count -eq 0) {
    $industry = "$($Body.industry)".Trim()
    if ([string]::IsNullOrWhiteSpace($industry)) { $industry = "infrastructure,logistics,energy" }
    $industries = @($industry -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ })
  }
  $evidence = @($Body.evidence)
  $audience = "$($Body.audience)".Trim()
  if ([string]::IsNullOrWhiteSpace($audience)) { $audience = "internal" }

  $payloadPath = Join-Path ([System.IO.Path]::GetTempPath()) ("v11-war-room-{0}.json" -f ([guid]::NewGuid().ToString("N")))
  $scriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("v11-war-room-{0}.py" -f ([guid]::NewGuid().ToString("N")))
  Convert-ToJsonText @{ objective = $objective; country = $country; industries = $industries; evidence = $evidence; audience = $audience } | Set-Content -Encoding UTF8 $payloadPath

  @'
import json
import sys
from pathlib import Path

project_root = Path(sys.argv[1])
payload_path = Path(sys.argv[2])
sys.path.insert(0, str(project_root))

from backend.services.industry_war_room_service import build_industry_war_room

payload = json.loads(payload_path.read_text(encoding="utf-8-sig"))
result = build_industry_war_room(
    str(payload.get("objective") or ""),
    country=str(payload.get("country") or "Kazakhstan"),
    industries=payload.get("industries") if isinstance(payload.get("industries"), list) else ["infrastructure", "logistics", "energy"],
    evidence=payload.get("evidence") if isinstance(payload.get("evidence"), list) else [],
    audience=str(payload.get("audience") or "internal"),
    persist=True,
)
print(json.dumps(result, ensure_ascii=True))
'@ | Set-Content -Encoding UTF8 $scriptPath

  try {
    $python = Get-Command python -ErrorAction Stop
    $oldErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
      $output = & $python.Source $scriptPath $ProjectRoot $payloadPath 2>&1 | Out-String
      $exitCode = $LASTEXITCODE
    } finally {
      $ErrorActionPreference = $oldErrorActionPreference
    }
    if ($exitCode -ne 0) {
      return New-JsonResponse @{ error = "War room build failed."; output = $output } 500
    }
    return New-JsonResponse (Convert-FromJsonText $output)
  } catch {
    return New-JsonResponse @{ error = "War room build failed."; detail = $_.Exception.Message; output = $output } 500
  } finally {
    Remove-Item -LiteralPath $payloadPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $scriptPath -Force -ErrorAction SilentlyContinue
  }
}

function Invoke-WarRoomExecutionQueue {
  $guard = Assert-LicenseAllowed
  if ($guard) { return $guard }

  $queuePath = Join-Path $CloudRoot "memory\war_room_execution\latest.json"
  $reportPath = Join-Path $CloudRoot "reports\war_room_execution\latest.md"
  $queue = (Read-JsonFileSafe $queuePath).data
  $report = Read-TextFileSafe $reportPath
  $ok = $null -ne $queue
  return New-JsonResponse @{
    ok = $ok
    queue = $queue
    report = $report
    json_path = $queuePath
    report_path = $reportPath
    missing = if ($ok) { @() } else { @("memory\war_room_execution\latest.json") }
    note = "Read-only queue view. It does not send external messages or bypass approval gates."
    readAt = (Get-Date).ToString("o")
  }
}

function Invoke-AnswerScore {
  param($Body)
  $guard = Assert-LicenseAllowed
  if ($guard) { return $guard }

  $question = "$($Body.question)".Trim()
  $answer = "$($Body.answer)".Trim()
  if ([string]::IsNullOrWhiteSpace($question) -or [string]::IsNullOrWhiteSpace($answer)) {
    return New-JsonResponse @{ error = "Question and answer are required." } 400
  }
  $evidence = @($Body.evidence)
  $payloadPath = Join-Path ([System.IO.Path]::GetTempPath()) ("v11-answer-score-{0}.json" -f ([guid]::NewGuid().ToString("N")))
  $scriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("v11-answer-score-{0}.py" -f ([guid]::NewGuid().ToString("N")))
  Convert-ToJsonText @{ question = $question; answer = $answer; evidence = $evidence } | Set-Content -Encoding UTF8 $payloadPath

  @'
import json
import sys
from pathlib import Path

project_root = Path(sys.argv[1])
payload_path = Path(sys.argv[2])
sys.path.insert(0, str(project_root))

from backend.services.knowledge_benchmark_service import score_answer

payload = json.loads(payload_path.read_text(encoding="utf-8-sig"))
result = score_answer(
    str(payload.get("question") or ""),
    str(payload.get("answer") or ""),
    evidence=payload.get("evidence") if isinstance(payload.get("evidence"), list) else [],
)
print(json.dumps(result, ensure_ascii=False))
'@ | Set-Content -Encoding UTF8 $scriptPath

  try {
    $python = Get-Command python -ErrorAction Stop
    $output = & $python.Source $scriptPath $ProjectRoot $payloadPath 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
      return New-JsonResponse @{ error = "Answer scoring failed."; output = $output } 500
    }
    return New-JsonResponse (Convert-FromJsonText $output)
  } catch {
    return New-JsonResponse @{ error = "Answer scoring failed."; detail = $_.Exception.Message } 500
  } finally {
    Remove-Item -LiteralPath $payloadPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $scriptPath -Force -ErrorAction SilentlyContinue
  }
}

function Invoke-BenchmarkCompare {
  param($Body)
  $guard = Assert-LicenseAllowed
  if ($guard) { return $guard }

  $question = "$($Body.question)".Trim()
  if ([string]::IsNullOrWhiteSpace($question)) {
    return New-JsonResponse @{ error = "Question is required." } 400
  }
  $answers = Get-ObjectField $Body "answers" $null
  if ($null -eq $answers) {
    return New-JsonResponse @{ error = "Answers are required." } 400
  }
  $payloadPath = Join-Path ([System.IO.Path]::GetTempPath()) ("v11-benchmark-compare-{0}.json" -f ([guid]::NewGuid().ToString("N")))
  $scriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("v11-benchmark-compare-{0}.py" -f ([guid]::NewGuid().ToString("N")))
  Convert-ToJsonText @{ question = $question; answers = $answers } | Set-Content -Encoding UTF8 $payloadPath

  @'
import json
import sys
from pathlib import Path

project_root = Path(sys.argv[1])
payload_path = Path(sys.argv[2])
sys.path.insert(0, str(project_root))

from backend.services.knowledge_benchmark_service import compare_answers

payload = json.loads(payload_path.read_text(encoding="utf-8-sig"))
answers = payload.get("answers") if isinstance(payload.get("answers"), dict) else {}
result = compare_answers(str(payload.get("question") or ""), {str(k): str(v) for k, v in answers.items()})
print(json.dumps(result, ensure_ascii=False))
'@ | Set-Content -Encoding UTF8 $scriptPath

  try {
    $python = Get-Command python -ErrorAction Stop
    $output = & $python.Source $scriptPath $ProjectRoot $payloadPath 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
      return New-JsonResponse @{ error = "Benchmark comparison failed."; output = $output } 500
    }
    return New-JsonResponse (Convert-FromJsonText $output)
  } catch {
    return New-JsonResponse @{ error = "Benchmark comparison failed."; detail = $_.Exception.Message } 500
  } finally {
    Remove-Item -LiteralPath $payloadPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $scriptPath -Force -ErrorAction SilentlyContinue
  }
}

function Invoke-KnowledgeBuild {
  $guard = Assert-LicenseAllowed
  if ($guard) { return $guard }

  $scriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("v11-knowledge-build-{0}.py" -f ([guid]::NewGuid().ToString("N")))
  @'
import json
import sys
from pathlib import Path

project_root = Path(sys.argv[1])
sys.path.insert(0, str(project_root))

from backend.services.knowledge_benchmark_service import build_industry_knowledge_base

result = build_industry_knowledge_base()
print(json.dumps(result, ensure_ascii=True))
'@ | Set-Content -Encoding UTF8 $scriptPath

  try {
    $python = Get-Command python -ErrorAction Stop
    $output = & $python.Source $scriptPath $ProjectRoot 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
      return New-JsonResponse @{ error = "Knowledge base build failed."; output = $output } 500
    }
    return New-JsonResponse (Convert-FromJsonText $output)
  } catch {
    return New-JsonResponse @{ error = "Knowledge base build failed."; detail = $_.Exception.Message } 500
  } finally {
    Remove-Item -LiteralPath $scriptPath -Force -ErrorAction SilentlyContinue
  }
}

function Invoke-BenchmarkBuild {
  $guard = Assert-LicenseAllowed
  if ($guard) { return $guard }

  $scriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("v11-benchmark-build-{0}.py" -f ([guid]::NewGuid().ToString("N")))
  @'
import json
import sys
from pathlib import Path

project_root = Path(sys.argv[1])
sys.path.insert(0, str(project_root))

from backend.services.knowledge_benchmark_service import build_v11_benchmark

result = build_v11_benchmark()
print(json.dumps(result, ensure_ascii=True))
'@ | Set-Content -Encoding UTF8 $scriptPath

  try {
    $python = Get-Command python -ErrorAction Stop
    $output = & $python.Source $scriptPath $ProjectRoot 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
      return New-JsonResponse @{ error = "Benchmark build failed."; output = $output } 500
    }
    return New-JsonResponse (Convert-FromJsonText $output)
  } catch {
    return New-JsonResponse @{ error = "Benchmark build failed."; detail = $_.Exception.Message } 500
  } finally {
    Remove-Item -LiteralPath $scriptPath -Force -ErrorAction SilentlyContinue
  }
}

function Invoke-SocialAnalyze {
  param($Body)
  $guard = Assert-LicenseAllowed
  if ($guard) { return $guard }

  $message = "$($Body.message)".Trim()
  if ([string]::IsNullOrWhiteSpace($message)) {
    $message = "$($Body.inbound_message)".Trim()
  }
  if ([string]::IsNullOrWhiteSpace($message)) {
    return New-JsonResponse @{ error = "Message is required." } 400
  }
  $channel = "$($Body.channel)".Trim()
  if ([string]::IsNullOrWhiteSpace($channel)) { $channel = "wechat" }
  $audience = "$($Body.audience)".Trim()
  if ([string]::IsNullOrWhiteSpace($audience)) { $audience = "external" }
  $authorization = Get-ObjectField $Body "authorization" @{ scope = "draft_only" }
  $evidence = @($Body.evidence)
  $payloadPath = Join-Path ([System.IO.Path]::GetTempPath()) ("v11-social-analyze-{0}.json" -f ([guid]::NewGuid().ToString("N")))
  $scriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("v11-social-analyze-{0}.py" -f ([guid]::NewGuid().ToString("N")))
  Convert-ToJsonText @{ channel = $channel; message = $message; authorization = $authorization; evidence = $evidence; audience = $audience } | Set-Content -Encoding UTF8 $payloadPath

  @'
import json
import sys
from pathlib import Path

project_root = Path(sys.argv[1])
payload_path = Path(sys.argv[2])
sys.path.insert(0, str(project_root))

from backend.services.social_communication_service import assess_social_context

payload = json.loads(payload_path.read_text(encoding="utf-8-sig"))
result = assess_social_context(
    str(payload.get("channel") or "wechat"),
    str(payload.get("message") or ""),
    authorization=payload.get("authorization") if isinstance(payload.get("authorization"), dict) else {"scope": "draft_only"},
    evidence=payload.get("evidence") if isinstance(payload.get("evidence"), list) else [],
    audience=str(payload.get("audience") or "external"),
)
print(json.dumps(result, ensure_ascii=True))
'@ | Set-Content -Encoding UTF8 $scriptPath

  try {
    $python = Get-Command python -ErrorAction Stop
    $oldErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
      $output = & $python.Source $scriptPath $ProjectRoot $payloadPath 2>&1 | Out-String
      $exitCode = $LASTEXITCODE
    } finally {
      $ErrorActionPreference = $oldErrorActionPreference
    }
    if ($exitCode -ne 0) {
      return New-JsonResponse @{ error = "Social analysis failed."; output = $output } 500
    }
    return New-JsonResponse (Convert-FromJsonText $output)
  } catch {
    return New-JsonResponse @{ error = "Social analysis failed."; detail = $_.Exception.Message; output = $output } 500
  } finally {
    Remove-Item -LiteralPath $payloadPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $scriptPath -Force -ErrorAction SilentlyContinue
  }
}

function Invoke-EvidenceVerify {
  param($Body)
  $guard = Assert-LicenseAllowed
  if ($guard) { return $guard }

  $claim = "$($Body.claim)".Trim()
  if ([string]::IsNullOrWhiteSpace($claim)) {
    $claim = "$($Body.query)".Trim()
  }
  if ([string]::IsNullOrWhiteSpace($claim)) {
    $claim = "$($Body.topic)".Trim()
  }
  if ([string]::IsNullOrWhiteSpace($claim)) {
    return New-JsonResponse @{ error = "Evidence claim is required." } 400
  }
  $project = "$($Body.project)".Trim()
  $country = "$($Body.country)".Trim()
  if ([string]::IsNullOrWhiteSpace($country)) { $country = "Kazakhstan" }
  $evidence = @($Body.evidence)
  $payloadPath = Join-Path ([System.IO.Path]::GetTempPath()) ("v11-evidence-verify-{0}.json" -f ([guid]::NewGuid().ToString("N")))
  $scriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("v11-evidence-verify-{0}.py" -f ([guid]::NewGuid().ToString("N")))
  Convert-ToJsonText @{ claim = $claim; project = $project; country = $country; evidence = $evidence } | Set-Content -Encoding UTF8 $payloadPath

  @'
import json
import sys
from pathlib import Path

project_root = Path(sys.argv[1])
payload_path = Path(sys.argv[2])
sys.path.insert(0, str(project_root))

from backend.services.evidence_verification_service import verify_claim

payload = json.loads(payload_path.read_text(encoding="utf-8-sig"))
result = verify_claim(
    str(payload.get("claim") or ""),
    payload.get("evidence") if isinstance(payload.get("evidence"), list) else [],
    project=str(payload.get("project") or ""),
    country=str(payload.get("country") or "Kazakhstan"),
    persist=True,
)
print(json.dumps(result, ensure_ascii=True))
'@ | Set-Content -Encoding UTF8 $scriptPath

  try {
    $python = Get-Command python -ErrorAction Stop
    $oldErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
      $output = & $python.Source $scriptPath $ProjectRoot $payloadPath 2>&1 | Out-String
      $exitCode = $LASTEXITCODE
    } finally {
      $ErrorActionPreference = $oldErrorActionPreference
    }
    if ($exitCode -ne 0) {
      return New-JsonResponse @{ error = "Evidence verification failed."; output = $output } 500
    }
    return New-JsonResponse (Convert-FromJsonText $output)
  } catch {
    return New-JsonResponse @{ error = "Evidence verification failed."; detail = $_.Exception.Message; output = $output } 500
  } finally {
    Remove-Item -LiteralPath $payloadPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $scriptPath -Force -ErrorAction SilentlyContinue
  }
}

function Invoke-SocialReplyDraft {
  param($Body)
  $guard = Assert-LicenseAllowed
  if ($guard) { return $guard }

  $message = "$($Body.message)".Trim()
  if ([string]::IsNullOrWhiteSpace($message)) {
    $message = "$($Body.inbound_message)".Trim()
  }
  if ([string]::IsNullOrWhiteSpace($message)) {
    return New-JsonResponse @{ error = "Inbound message is required." } 400
  }
  $channel = "$($Body.channel)".Trim()
  if ([string]::IsNullOrWhiteSpace($channel)) { $channel = "wechat" }
  $recipient = "$($Body.recipient)".Trim()
  if ([string]::IsNullOrWhiteSpace($recipient)) { $recipient = "owner" }
  $audience = "$($Body.audience)".Trim()
  if ([string]::IsNullOrWhiteSpace($audience)) { $audience = "external" }
  $authorization = Get-ObjectField $Body "authorization" @{ scope = "draft_only" }
  $evidence = @($Body.evidence)
  $payloadPath = Join-Path ([System.IO.Path]::GetTempPath()) ("v11-social-reply-{0}.json" -f ([guid]::NewGuid().ToString("N")))
  $scriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("v11-social-reply-{0}.py" -f ([guid]::NewGuid().ToString("N")))
  Convert-ToJsonText @{ channel = $channel; recipient = $recipient; message = $message; authorization = $authorization; evidence = $evidence; audience = $audience } | Set-Content -Encoding UTF8 $payloadPath

  @'
import json
import sys
from pathlib import Path

project_root = Path(sys.argv[1])
payload_path = Path(sys.argv[2])
sys.path.insert(0, str(project_root))

from backend.services.social_communication_service import build_authorized_social_reply

payload = json.loads(payload_path.read_text(encoding="utf-8-sig"))
result = build_authorized_social_reply(
    str(payload.get("channel") or "wechat"),
    str(payload.get("recipient") or "owner"),
    str(payload.get("message") or ""),
    authorization=payload.get("authorization") if isinstance(payload.get("authorization"), dict) else {"scope": "draft_only"},
    evidence=payload.get("evidence") if isinstance(payload.get("evidence"), list) else [],
    audience=str(payload.get("audience") or "external"),
)
print(json.dumps(result, ensure_ascii=True))
'@ | Set-Content -Encoding UTF8 $scriptPath

  try {
    $python = Get-Command python -ErrorAction Stop
    $oldErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
      $output = & $python.Source $scriptPath $ProjectRoot $payloadPath 2>&1 | Out-String
      $exitCode = $LASTEXITCODE
    } finally {
      $ErrorActionPreference = $oldErrorActionPreference
    }
    if ($exitCode -ne 0) {
      return New-JsonResponse @{ error = "Social reply draft failed."; output = $output } 500
    }
    return New-JsonResponse (Convert-FromJsonText $output)
  } catch {
    return New-JsonResponse @{ error = "Social reply draft failed."; detail = $_.Exception.Message; output = $output } 500
  } finally {
    Remove-Item -LiteralPath $payloadPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $scriptPath -Force -ErrorAction SilentlyContinue
  }
}

function Handle-ApiRequest {
  param([string]$Method, [string]$Path, [string]$BodyText)

  $body = @{}
  if (![string]::IsNullOrWhiteSpace($BodyText)) {
    $body = Convert-FromJsonText $BodyText
  }

  if ($Method -eq "GET" -and $Path -eq "/api/state") {
    return New-JsonResponse (Read-Store)
  }

  if ($Method -eq "GET" -and $Path -eq "/api/license/status") {
    return New-JsonResponse @{ license = (Get-LicenseStatus); allowed = (Test-LicenseUsable (Get-LicenseStatus)) }
  }

  if ($Method -eq "POST" -and $Path -eq "/api/license/refresh") {
    $license = Get-LicenseStatus
    return New-JsonResponse @{ license = $license; allowed = (Test-LicenseUsable $license) }
  }

  if ($Method -eq "GET" -and $Path -eq "/api/cloud/status") {
    $license = Get-LicenseStatus
    $rootStatus = Read-TextFileSafe (Join-Path $ProjectRoot "cloud-test-status.md")
    $cloudStatus = Read-TextFileSafe (Join-Path $CloudRoot "reports\cloud_test_status.md")
    $cloudRun = Read-CloudJsonLight (Join-Path $CloudRoot "reports\cloud_run.json") @("ok", "stage", "run_url", "conclusion", "updated_at")
    $cloudAcceptance = Read-CloudJsonLight (Join-Path $CloudRoot "reports\cloud_acceptance_remote.json") @("ok", "stage", "run_url", "conclusion", "updated_at")
    $watchdog = Read-TextFileSafe (Join-Path $CloudRoot "reports\watchdog_status.md")
    return New-JsonResponse @{
      license = $license
      allowed = (Test-LicenseUsable $license)
      rootStatus = $rootStatus
      cloudStatus = $cloudStatus
      cloudRun = $cloudRun
      cloudAcceptance = $cloudAcceptance
      watchdog = $watchdog
      checkedAt = (Get-Date).ToString("o")
    }
  }

  if ($Method -eq "GET" -and $Path -eq "/api/cloud/inbox") {
    return New-JsonResponse @{
      inbox = Read-TextFileSafe (Join-Path $CloudRoot "reports\owner_inbox.md")
      headquarters = Read-TextFileSafe (Join-Path $CloudRoot "reports\headquarters_status.md")
      readAt = (Get-Date).ToString("o")
    }
  }

  if ($Method -eq "GET" -and $Path -eq "/api/mission-control") {
    return New-JsonResponse @{
      snapshot = (Read-JsonFileSafe (Join-Path $CloudRoot "memory\mission_control\latest.json")).data
      report = Read-TextFileSafe (Join-Path $CloudRoot "reports\mission_control\latest.md")
      readAt = (Get-Date).ToString("o")
    }
  }

  if ($Method -eq "POST" -and $Path -eq "/api/cloud/check") {
    return Invoke-CloudScript "check-cloud-config-from-root.cmd"
  }

  if ($Method -eq "POST" -and $Path -eq "/api/cloud/run") {
    return Invoke-CloudScript "run-cloud-test-from-root.cmd" @("-Upload")
  }

  if ($Method -eq "POST" -and $Path -eq "/api/search") {
    $guard = Assert-LicenseAllowed
    if ($guard) { return $guard }
    $query = "$($body.query)".Trim()
    if ([string]::IsNullOrWhiteSpace($query)) {
      return New-JsonResponse @{ error = "Search query is required." } 400
    }
    $v11Plan = Get-V11SearchPlan $query
    $sources = @($body.sources)
    if ($sources.Count -eq 0) { $sources = @("bing", "google", "yandex", "social", "academic", "library") }
    $results = @()
    if ($sources -contains "bing") { $results += Search-Bing $query }
    if ($sources -contains "google") { $results += Search-Google $query }
    if ($sources -contains "yandex") { $results += Search-YandexRegional $query }
    if ($sources -contains "social") { $results += Search-SocialChannels $query }
    if ($sources -contains "academic") { $results += Search-Academic $query }
    if ($sources -contains "library") { $results += Search-Library $query }
    $missingConfig = @($results | Where-Object { $_.ok -eq $false -and "$($_.error)" -match "Missing environment variable|configuration" } | ForEach-Object {
      @{ source = $_.source; reason = $_.error }
    })
    $manualCount = @($results | Where-Object { $_.items -and @($_.items).Count -gt 0 }).Count
    $sourceStatus = @($results | ForEach-Object {
      $status = if ($_.ok) { "configured" } elseif ("$($_.error)" -match "Missing environment variable|configuration") { "missing_configuration" } else { "unavailable_or_limited" }
      $reason = if ($_.ok) { "Source returned results or fallback entries." } else { "$($_.error)" }
      $nextAction = if ($status -eq "missing_configuration") { "Configure the required key or use manual search URLs." } else { "Review returned items and attach official evidence before confirmation." }
      @{
        source = $_.source
        status = $status
        result_count = @($_.items).Count
        reason = $reason
        next_action = $nextAction
      }
    })
    $candidateProjects = @(
      @{
        project_name = "$query - planned project lead"
        country = if ($v11Plan.evidence_execution_brief.region -eq "Kazakhstan") { "Kazakhstan" } else { "Central Asia" }
        sector = "engineering trade / infrastructure"
        stage = "candidate_planned"
        stage_label = "计划建设候选项目"
        official_source_status = "not_verified_search_plan_only"
        owner = "待官方证据确认"
        developer = "待官方证据确认"
        confidence = 30
        risk_flags = @(
          "Search plan only; do not treat as a confirmed project.",
          "Government or procurement evidence is required before investment-promotion use."
        )
        next_actions = @($v11Plan.project_search_plan | Where-Object { $_.intent -in @("government_confirmation", "procurement_tender") } | Select-Object -First 6)
      }
    )
    $resultCategories = @{
      projects = $candidateProjects
      official_sources = @($v11Plan.project_search_plan | Where-Object { $_.intent -eq "government_confirmation" } | Select-Object -First 8)
      tenders = @($v11Plan.project_search_plan | Where-Object { $_.intent -eq "procurement_tender" } | Select-Object -First 8)
      risks = @($v11Plan.project_search_plan | Where-Object { $_.intent -eq "customs_trade" } | Select-Object -First 8)
      background = @($v11Plan.project_search_plan | Where-Object { $_.intent -eq "stakeholders" } | Select-Object -First 8)
      social_video = @($results | Where-Object { $_.source -in @("social", "yandex") })
      research = @($results | Where-Object { $_.source -in @("academic", "library") })
    }
    $briefDraft = @{
      title = "Search intelligence brief draft: $query"
      status = "draft_not_approved_for_external_use"
      search_topic = $query
      summary = "Search expansion and source readiness are prepared. Candidate projects remain leads until official evidence is attached."
      enhanced_query_count = @($v11Plan.search_expansion.all_terms).Count
      source_summary = @{
        total = $sourceStatus.Count
        missing_configuration = @($sourceStatus | Where-Object { $_.status -eq "missing_configuration" }).Count
        manual_sources = $manualCount
      }
      candidate_projects = $candidateProjects
      official_source_status = $v11Plan.project_confirmation_gate.status
      risk_notice = "Do not publish, quote, outreach, or create confirmed project records before official evidence and human approval."
      next_actions = @(
        "Open government and procurement search URLs first.",
        "Attach official evidence items with title, URL, date, and snippet.",
        "Verify project stage, owner, developer, tender status, customs impact, and risk flags.",
        "Generate feasibility report only as an internal draft until evidence is sufficient."
      )
    }
    return New-JsonResponse @{
      ok = $true
      query = $query
      search_expansion = $v11Plan.search_expansion
      enrichment = $v11Plan.enrichment
      source_status = $sourceStatus
      source_readiness = @{
        ok = $missingConfig.Count -eq 0
        configured_count = $results.Count
        live_adapter_count = @($results | Where-Object { $_.ok -eq $true }).Count
        manual_entry_count = $manualCount
        missing_configuration = $missingConfig
        explanation = "Live API keys improve automation, but official/manual search URLs still require evidence verification before confirmation."
      }
      result_categories = $resultCategories
      candidate_projects = $candidateProjects
      project_search_plan = $v11Plan.project_search_plan
      project_brief_draft = $briefDraft
      project_confirmation_gate = $v11Plan.project_confirmation_gate
      evidence_execution_brief = $v11Plan.evidence_execution_brief
      project_library_rule = $v11Plan.project_library_rule
      answer_rule = $v11Plan.answer_rule
      safety = $v11Plan.safety
      results = $results
      searchedAt = (Get-Date).ToString("o")
    }
  }

  if ($Method -eq "POST" -and $Path -eq "/api/project/pipeline") {
    return Invoke-ProjectPipeline $body
  }

  if ($Method -eq "GET" -and $Path -eq "/api/projects/library") {
    return Invoke-ProjectLibrary
  }

  if ($Method -eq "POST" -and $Path -eq "/api/video/center") {
    return Invoke-VideoCenter $body
  }

  if ($Method -eq "POST" -and $Path -eq "/api/intelligence/brief") {
    return Invoke-IntelligenceBrief $body
  }

  if ($Method -eq "POST" -and $Path -eq "/api/team/execute") {
    return Invoke-TeamExecution $body
  }

  if ($Method -eq "POST" -and $Path -eq "/api/team/response") {
    return Invoke-TeamResponse $body
  }

  if ($Method -eq "POST" -and $Path -eq "/api/war-room/build") {
    return Invoke-WarRoomBuild $body
  }

  if ($Method -eq "GET" -and $Path -eq "/api/war-room/execution-queue") {
    return Invoke-WarRoomExecutionQueue
  }

  if ($Method -eq "POST" -and $Path -eq "/api/answers/score") {
    return Invoke-AnswerScore $body
  }

  if ($Method -eq "POST" -and $Path -eq "/api/benchmark/compare") {
    return Invoke-BenchmarkCompare $body
  }

  if ($Method -eq "POST" -and $Path -eq "/api/knowledge/build") {
    return Invoke-KnowledgeBuild
  }

  if ($Method -eq "POST" -and $Path -eq "/api/benchmark/build") {
    return Invoke-BenchmarkBuild
  }

  if ($Method -eq "POST" -and $Path -eq "/api/social/analyze") {
    return Invoke-SocialAnalyze $body
  }

  if ($Method -eq "POST" -and $Path -eq "/api/evidence/verify") {
    return Invoke-EvidenceVerify $body
  }

  if ($Method -eq "POST" -and $Path -eq "/api/social/reply-draft") {
    return Invoke-SocialReplyDraft $body
  }

  if ($Method -eq "POST" -and $Path -eq "/api/decision") {
    $guard = Assert-LicenseAllowed
    if ($guard) { return $guard }
    $store = Read-Store
    $analysis = New-DecisionAnalysis $body
    $decision = @{
      id = [guid]::NewGuid().ToString()
      type = if (Get-ObjectField $body "type" $null) { Get-ObjectField $body "type" "project" } else { "project" }
      title = [string](Get-ObjectField $body "title" "")
      context = [string](Get-ObjectField $body "context" "")
      options = Normalize-List (Get-ObjectField $body "options")
      criteria = Normalize-List (Get-ObjectField $body "criteria")
      analysis = $analysis
      createdAt = (Get-Date).ToString("o")
    }
    $store.decisions = Add-Item $store.decisions $decision

    $approval = $null
    if ($analysis.askNeeded) {
      $approval = @{
        id = [guid]::NewGuid().ToString()
        decisionId = $decision.id
        status = "waiting"
        question = "Approve this recommendation: $($analysis.recommendation)"
        recommendation = $analysis.recommendation
        createdAt = (Get-Date).ToString("o")
        repliedAt = $null
      }
      $store.approvals = Add-Item $store.approvals $approval
    }

    Save-Store $store
    return New-JsonResponse @{ decision = $decision; approval = $approval }
  }

  if ($Method -eq "POST" -and $Path -eq "/api/feedback") {
    $guard = Assert-LicenseAllowed
    if ($guard) { return $guard }
    $store = Read-Store
    $feedback = @{
      id = [guid]::NewGuid().ToString()
      approvalId = [string](Get-ObjectField $body "approvalId" "")
      decisionId = [string](Get-ObjectField $body "decisionId" "")
      reply = [string](Get-ObjectField $body "reply" "")
      accepted = [bool](Get-ObjectField $body "accepted" $false)
      notes = [string](Get-ObjectField $body "notes" "")
      createdAt = (Get-Date).ToString("o")
    }
    $store.feedback = Add-Item $store.feedback $feedback

    foreach ($approval in @($store.approvals)) {
      if ($approval.id -eq $feedback.approvalId) {
        if ($feedback.accepted) {
          $approval.status = "approved"
        } else {
          $approval.status = "rejected"
        }
        $approval.reply = $feedback.reply
        $approval.repliedAt = (Get-Date).ToString("o")
      }
    }

    if ($feedback.accepted) {
      $store.learning.acceptedPatterns = Add-Item $store.learning.acceptedPatterns $feedback.reply
    } else {
      $store.learning.rejectedPatterns = Add-Item $store.learning.rejectedPatterns $feedback.reply
    }
    if (![string]::IsNullOrWhiteSpace($feedback.notes)) {
      $store.learning.notes = Add-Item $store.learning.notes $feedback.notes
    }
    $store.learning.updatedAt = (Get-Date).ToString("o")
    Save-Store $store
    return New-JsonResponse @{ feedback = $feedback; learning = $store.learning }
  }

  return New-JsonResponse @{ error = "Unknown API path: $Path" } 404
}

function Handle-StaticRequest {
  param([string]$Path)
  $cleanPath = [uri]::UnescapeDataString($Path.TrimStart("/"))
  if ([string]::IsNullOrWhiteSpace($cleanPath)) { $cleanPath = "index.html" }
  $target = Join-Path $PublicRoot $cleanPath
  $fullPublic = [System.IO.Path]::GetFullPath($PublicRoot)
  $fullTarget = [System.IO.Path]::GetFullPath($target)
  if (!$fullTarget.StartsWith($fullPublic, [System.StringComparison]::OrdinalIgnoreCase)) {
    return New-TextResponse "Forbidden" "text/plain; charset=utf-8" 403
  }
  if (!(Test-Path $fullTarget -PathType Leaf)) {
    return New-TextResponse "Not found" "text/plain; charset=utf-8" 404
  }
  return @{
    Status = 200
    ContentType = Get-ContentType $fullTarget
    Body = [System.IO.File]::ReadAllBytes($fullTarget)
  }
}

function Find-ByteSequence {
  param([byte[]]$Bytes, [byte[]]$Needle)
  if ($Bytes.Length -lt $Needle.Length) { return -1 }
  for ($i = 0; $i -le $Bytes.Length - $Needle.Length; $i++) {
    $found = $true
    for ($j = 0; $j -lt $Needle.Length; $j++) {
      if ($Bytes[$i + $j] -ne $Needle[$j]) {
        $found = $false
        break
      }
    }
    if ($found) { return $i }
  }
  return -1
}

function Read-HttpRequest {
  param($Stream)
  $buffer = New-Object byte[] 8192
  $memory = [System.IO.MemoryStream]::new()
  $headerEnd = -1
  $contentLength = 0
  $delimiter = [byte[]](13, 10, 13, 10)

  while ($true) {
    $read = $Stream.Read($buffer, 0, $buffer.Length)
    if ($read -le 0) { break }
    $memory.Write($buffer, 0, $read)
    $all = $memory.ToArray()
    if ($headerEnd -lt 0) {
      $headerEnd = Find-ByteSequence $all $delimiter
      if ($headerEnd -ge 0) {
        $headerText = [System.Text.Encoding]::ASCII.GetString($all, 0, $headerEnd)
        foreach ($line in $headerText -split "`r`n") {
          if ($line -match "^Content-Length:\s*(\d+)") {
            $contentLength = [int]$Matches[1]
          }
        }
      }
    }
    if ($headerEnd -ge 0 -and $all.Length -ge ($headerEnd + 4 + $contentLength)) {
      break
    }
  }

  $bytes = $memory.ToArray()
  if ($bytes.Length -eq 0 -or $headerEnd -lt 0) { return $null }
  $header = [System.Text.Encoding]::ASCII.GetString($bytes, 0, $headerEnd)
  $firstLine = ($header -split "`r`n")[0]
  $parts = $firstLine -split " "
  $bodyStart = $headerEnd + 4
  $bodyText = ""
  if ($contentLength -gt 0) {
    $bodyBytes = New-Object byte[] $contentLength
    [Array]::Copy($bytes, $bodyStart, $bodyBytes, 0, $contentLength)
    $bodyText = [System.Text.Encoding]::UTF8.GetString($bodyBytes)
  }
  $path = ($parts[1] -split "\?")[0]
  return @{
    Method = $parts[0]
    Path = $path
    Body = $bodyText
  }
}

function Write-HttpResponse {
  param($Stream, $Response)
  $reason = switch ($Response.Status) {
    200 { "OK" }
    400 { "Bad Request" }
    403 { "Forbidden" }
    404 { "Not Found" }
    500 { "Internal Server Error" }
    default { "OK" }
  }
  $headers = @(
    "HTTP/1.1 $($Response.Status) $reason",
    "Content-Type: $($Response.ContentType)",
    "Content-Length: $($Response.Body.Length)",
    "Connection: close",
    "Access-Control-Allow-Origin: *",
    "",
    ""
  ) -join "`r`n"
  $headerBytes = [System.Text.Encoding]::ASCII.GetBytes($headers)
  $Stream.Write($headerBytes, 0, $headerBytes.Length)
  $Stream.Write($Response.Body, 0, $Response.Body.Length)
}

function Try-WriteHttpResponse {
  param($Stream, $Response)
  try {
    if ($Stream) {
      Write-HttpResponse $Stream $Response
    }
  } catch {
    Write-Warning "HTTP client disconnected before response completed: $($_.Exception.Message)"
  }
}

$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Parse("127.0.0.1"), $Port)
$listener.Start()
Write-Host "Decision Hub running at http://127.0.0.1:$Port/"
Write-Host "Press Ctrl+C to stop."

try {
  while ($true) {
    $client = $listener.AcceptTcpClient()
    try {
      $client.ReceiveTimeout = 2000
      $client.SendTimeout = 10000
      $stream = $client.GetStream()
      $request = Read-HttpRequest $stream
      if ($null -eq $request) {
        $response = New-TextResponse "Bad request" "text/plain; charset=utf-8" 400
      } elseif ($request.Path.StartsWith("/api/")) {
        $response = Handle-ApiRequest $request.Method $request.Path $request.Body
      } else {
        $response = Handle-StaticRequest $request.Path
      }
      Try-WriteHttpResponse $stream $response
    } catch {
      $response = New-JsonResponse @{ error = $_.Exception.Message } 500
      Try-WriteHttpResponse $stream $response
    } finally {
      if ($stream) { $stream.Close() }
      $client.Close()
    }
  }
} finally {
  $listener.Stop()
}
