## dump_module.ps1
##
## Generates a consolidated <NN>_<slug>.txt file in temp/ containing all backend
## (apps/<name>/) and frontend (templates/<name>/) code for one NavERP module.
##
## NavERP is a multi-tenant Enterprise Resource Planning (ERP) platform (Django 5.1 + Tailwind/HTMX/Chart.js/Lucide,
## MySQL/MariaDB via PyMySQL, DB nav_erp). Module 0 (System Admin & Security) is realized by the foundation apps
## core/accounts/tenants/dashboard. Modules 1-13 (NavERP.md) are one Django app each, built on demand by the
## /next-module skill -- until then the script prints "(no backend folder found ...)" for them, which is expected.
##
## Usage:
##   pwsh .claude\skills\dump-module\dump_module.ps1 -Module tenants
##   pwsh .claude\skills\dump-module\dump_module.ps1 -Module 0
##   pwsh .claude\skills\dump-module\dump_module.ps1 -Module "crm"
##   pwsh .claude\skills\dump-module\dump_module.ps1 -Module all      # regenerates every module

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Module,

    [string]$RepoRoot = 'C:\xampp\htdocs\NavERP'
)

$ErrorActionPreference = 'Stop'

# -------- Module registry --------
# key = output file slug; value = @(<apps_folder>, <templates_folder>, <human title>)
# Module 0 (System Admin & Security) = the foundation apps core/accounts/tenants/dashboard.
# Modules 1-13 are FORWARD-COMPATIBLE entries matching the /next-module domain app slugs;
# their apps/<slug> + templates/<slug> folders do not exist until /next-module builds them.
$registry = [ordered]@{
    # --- Module 0 (System Admin & Security) + foundation apps ---
    '00_tenants'     = @('tenants',     'tenants',     '0. System Admin & Security (Tenant & Subscription)')
    'accounts'       = @('accounts',    'accounts',    'Foundation: Accounts (Users, Roles, IAM/RBAC, Auth)')
    'core'           = @('core',        'core',        'Foundation: Core (Tenant, Audit, Navigation, Party)')
    'dashboard'      = @('dashboard',   'dashboard',   'Foundation: Dashboard (KPI aggregation)')
    # --- Modules 1-13 (domain modules; built on demand by /next-module) ---
    '01_crm'         = @('crm',         'crm',         '1. Customer Relationship Management (CRM)')
    '02_accounting'  = @('accounting',  'accounting',  '2. Accounting & Finance')
    '03_hrm'         = @('hrm',         'hrm',         '3. Human Resource Management (HRM)')
    '04_scm'         = @('scm',         'scm',         '4. Supply Chain Management (SCM)')
    '05_inventory'   = @('inventory',   'inventory',   '5. Inventory Management System (IMS)')
    '06_procurement' = @('procurement', 'procurement', '6. Procurement Management System')
    '07_projects'    = @('projects',    'projects',    '7. Project Management')
    '08_sales'       = @('sales',       'sales',       '8. Sales Management System')
    '09_ecommerce'   = @('ecommerce',   'ecommerce',   '9. eCommerce Management System')
    '10_bi'          = @('bi',          'bi',          '10. Business Intelligence (BI)')
    '11_assets'      = @('assets',      'assets',      '11. Asset Management System')
    '12_quality'     = @('quality',     'quality',     '12. Quality Management System (QMS)')
    '13_documents'   = @('documents',   'documents',   '13. Document Management System (DMS)')
}

# Friendly aliases -> registry key (every key must be UNIQUE)
$aliases = @{
    # --- Numbers ---
    '0'   = '00_tenants'
    '00'  = '00_tenants'
    '1'   = '01_crm'
    '01'  = '01_crm'
    '2'   = '02_accounting'
    '02'  = '02_accounting'
    '3'   = '03_hrm'
    '03'  = '03_hrm'
    '4'   = '04_scm'
    '04'  = '04_scm'
    '5'   = '05_inventory'
    '05'  = '05_inventory'
    '6'   = '06_procurement'
    '06'  = '06_procurement'
    '7'   = '07_projects'
    '07'  = '07_projects'
    '8'   = '08_sales'
    '08'  = '08_sales'
    '9'   = '09_ecommerce'
    '09'  = '09_ecommerce'
    '10'  = '10_bi'
    '11'  = '11_assets'
    '12'  = '12_quality'
    '13'  = '13_documents'
    # --- Module 0 + foundation app folders + keywords ---
    'tenants'        = '00_tenants'
    'tenant'         = '00_tenants'
    'subscription'   = '00_tenants'
    'subscriptions'  = '00_tenants'
    'billing'        = '00_tenants'
    'invoice'        = '00_tenants'
    'invoices'       = '00_tenants'
    'accounts'       = 'accounts'
    'account'        = 'accounts'
    'users'          = 'accounts'
    'user'           = 'accounts'
    'roles'          = 'accounts'
    'role'           = 'accounts'
    'auth'           = 'accounts'
    'login'          = 'accounts'
    'iam'            = 'accounts'
    'rbac'           = 'accounts'
    'permissions'    = 'accounts'
    'sso'            = 'accounts'
    'core'           = 'core'
    'audit'          = 'core'
    'navigation'     = 'core'
    'settings'       = 'core'
    'party'          = 'core'
    'parties'        = 'core'
    'dashboard'      = 'dashboard'
    'kpi'            = 'dashboard'
    'home'           = 'dashboard'
    'overview'       = 'dashboard'
    # --- Modules 1-13 app folder names + friendly keywords ---
    'crm'            = '01_crm'
    'customer'       = '01_crm'
    'customers'      = '01_crm'
    'contact'        = '01_crm'
    'contacts'       = '01_crm'
    'lead'           = '01_crm'
    'leads'          = '01_crm'
    'campaign'       = '01_crm'
    'case'           = '01_crm'
    'ticket'         = '01_crm'
    'helpdesk'       = '01_crm'
    'accounting'     = '02_accounting'
    'finance'        = '02_accounting'
    'financials'     = '02_accounting'
    'gl'             = '02_accounting'
    'ledger'         = '02_accounting'
    'journal'        = '02_accounting'
    'ap'             = '02_accounting'
    'ar'             = '02_accounting'
    'payable'        = '02_accounting'
    'receivable'     = '02_accounting'
    'budget'         = '02_accounting'
    'tax'            = '02_accounting'
    'hrm'            = '03_hrm'
    'hr'             = '03_hrm'
    'employee'       = '03_hrm'
    'employees'      = '03_hrm'
    'payroll'        = '03_hrm'
    'leave'          = '03_hrm'
    'attendance'     = '03_hrm'
    'recruitment'    = '03_hrm'
    'performance'    = '03_hrm'
    'scm'            = '04_scm'
    'supplychain'    = '04_scm'
    'supply'         = '04_scm'
    'logistics'      = '04_scm'
    'transport'      = '04_scm'
    'freight'        = '04_scm'
    'carrier'        = '04_scm'
    '3pl'            = '04_scm'
    'demand'         = '04_scm'
    'shipment'       = '04_scm'
    'inventory'      = '05_inventory'
    'stock'          = '05_inventory'
    'ims'            = '05_inventory'
    'warehouse'      = '05_inventory'
    'wms'            = '05_inventory'
    'bin'            = '05_inventory'
    'sku'            = '05_inventory'
    'uom'            = '05_inventory'
    'lot'            = '05_inventory'
    'serial'         = '05_inventory'
    'reorder'        = '05_inventory'
    'product'        = '05_inventory'
    'products'       = '05_inventory'
    'procurement'    = '06_procurement'
    'purchase'       = '06_procurement'
    'po'             = '06_procurement'
    'purchaseorder'  = '06_procurement'
    'requisition'    = '06_procurement'
    'rfq'            = '06_procurement'
    'rfp'            = '06_procurement'
    'rfi'            = '06_procurement'
    'sourcing'       = '06_procurement'
    'tender'         = '06_procurement'
    'vendor'         = '06_procurement'
    'vendors'        = '06_procurement'
    'supplier'       = '06_procurement'
    'suppliers'      = '06_procurement'
    'grn'            = '06_procurement'
    'spend'          = '06_procurement'
    'projects'       = '07_projects'
    'project'        = '07_projects'
    'pmo'            = '07_projects'
    'task'           = '07_projects'
    'tasks'          = '07_projects'
    'gantt'          = '07_projects'
    'sprint'         = '07_projects'
    'milestone'      = '07_projects'
    'wbs'            = '07_projects'
    'timesheet'      = '07_projects'
    'sales'          = '08_sales'
    'opportunity'    = '08_sales'
    'opportunities'  = '08_sales'
    'pipeline'       = '08_sales'
    'deal'           = '08_sales'
    'deals'          = '08_sales'
    'quote'          = '08_sales'
    'quotes'         = '08_sales'
    'cpq'            = '08_sales'
    'proposal'       = '08_sales'
    'forecast'       = '08_sales'
    'forecasting'    = '08_sales'
    'territory'      = '08_sales'
    'quota'          = '08_sales'
    'commission'     = '08_sales'
    'order'          = '08_sales'
    'orders'         = '08_sales'
    'ecommerce'      = '09_ecommerce'
    'e-commerce'     = '09_ecommerce'
    'commerce'       = '09_ecommerce'
    'store'          = '09_ecommerce'
    'storefront'     = '09_ecommerce'
    'cart'           = '09_ecommerce'
    'checkout'       = '09_ecommerce'
    'catalog'        = '09_ecommerce'
    'shop'           = '09_ecommerce'
    'marketplace'    = '09_ecommerce'
    'pim'            = '09_ecommerce'
    'bi'             = '10_bi'
    'analytics'      = '10_bi'
    'intelligence'   = '10_bi'
    'reporting'      = '10_bi'
    'report'         = '10_bi'
    'reports'        = '10_bi'
    'etl'            = '10_bi'
    'olap'           = '10_bi'
    'assets'         = '11_assets'
    'asset'          = '11_assets'
    'fixedasset'     = '11_assets'
    'equipment'      = '11_assets'
    'fleet'          = '11_assets'
    'vehicle'        = '11_assets'
    'maintenance'    = '11_assets'
    'depreciation'   = '11_assets'
    'cmms'           = '11_assets'
    'itam'           = '11_assets'
    'quality'        = '12_quality'
    'qms'            = '12_quality'
    'capa'           = '12_quality'
    'ncr'            = '12_quality'
    'nonconformance' = '12_quality'
    'inspection'     = '12_quality'
    'calibration'    = '12_quality'
    'iqc'            = '12_quality'
    'lims'           = '12_quality'
    'complaint'      = '12_quality'
    'documents'      = '13_documents'
    'document'       = '13_documents'
    'dms'            = '13_documents'
    'dam'            = '13_documents'
    'clm'            = '13_documents'
    'records'        = '13_documents'
    'wiki'           = '13_documents'
    'knowledge'      = '13_documents'
    'file'           = '13_documents'
    'files'          = '13_documents'
}

# -------- Resolve which keys to process --------
$targetKeys = @()
$lookup = $Module.Trim().ToLower()

if ($lookup -eq 'all' -or $lookup -eq '*') {
    $targetKeys = @($registry.Keys)
}
elseif ($registry.Contains($Module)) {
    $targetKeys = @($Module)
}
elseif ($aliases.ContainsKey($lookup)) {
    $targetKeys = @($aliases[$lookup])
}
else {
    # last-chance fuzzy: contains match against title
    foreach ($k in $registry.Keys) {
        $title = $registry[$k][2].ToLower()
        if ($title -like "*$lookup*") {
            $targetKeys = @($k)
            break
        }
    }
}

if ($targetKeys.Count -eq 0) {
    Write-Error @"
Unknown module: '$Module'.

Valid identifiers:
  Number:       0..13  (or 00..13)
  App folder:   tenants, accounts, core, dashboard,
                crm, accounting, hrm, scm, inventory, procurement, projects,
                sales, ecommerce, bi, assets, quality, documents
  Special:      all   (regenerate every module)

Examples:
  pwsh .claude\skills\dump-module\dump_module.ps1 -Module tenants
  pwsh .claude\skills\dump-module\dump_module.ps1 -Module 0
  pwsh .claude\skills\dump-module\dump_module.ps1 -Module crm
  pwsh .claude\skills\dump-module\dump_module.ps1 -Module all
"@
    exit 1
}

# -------- Ensure temp/ exists --------
$outDir = Join-Path $RepoRoot 'temp'
if (-not (Test-Path $outDir)) {
    New-Item -ItemType Directory -Path $outDir -Force | Out-Null
}

# -------- Helpers --------
function Add-Section {
    param([string]$OutFile, [string]$Header)
    $banner = ('=' * 100)
    Add-Content -Path $OutFile -Value "`r`n$banner`r`n$Header`r`n$banner`r`n" -Encoding UTF8
}

function Add-FileBlock {
    param([string]$OutFile, [System.IO.FileInfo]$File, [string]$RelPath)
    $sub = ('-' * 100)
    Add-Content -Path $OutFile -Value "`r`n$sub`r`nFILE: $RelPath`r`n$sub" -Encoding UTF8
    $content = [System.IO.File]::ReadAllText($File.FullName)
    Add-Content -Path $OutFile -Value $content -Encoding UTF8
}

# -------- Generate --------
foreach ($key in $targetKeys) {
    $appsFolder, $tplFolder, $title = $registry[$key]
    $outFile = Join-Path $outDir "$key.txt"

    Set-Content -Path $outFile -Value "" -Encoding UTF8

    $banner = ('#' * 100)
    Add-Content -Path $outFile -Value "$banner`r`n# MODULE $title`r`n# Backend:  apps\$appsFolder\`r`n# Frontend: templates\$tplFolder\`r`n# Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')`r`n$banner" -Encoding UTF8

    # Backend
    $appsPath = Join-Path $RepoRoot "apps\$appsFolder"
    if (Test-Path $appsPath) {
        Add-Section -OutFile $outFile -Header "BACKEND  (apps\$appsFolder\)"
        $files = Get-ChildItem -Path $appsPath -Recurse -File `
            | Where-Object { $_.FullName -notmatch '__pycache__' } `
            | Where-Object { $_.Extension -in '.py', '.txt', '.md', '.json', '.yml', '.yaml', '.cfg', '.ini' } `
            | Sort-Object FullName
        foreach ($f in $files) {
            $rel = $f.FullName.Substring($RepoRoot.Length + 1)
            Add-FileBlock -OutFile $outFile -File $f -RelPath $rel
        }
    } else {
        Add-Content -Path $outFile -Value "`r`n(no backend folder found at apps\$appsFolder\)`r`n" -Encoding UTF8
    }

    # Frontend
    $tplPath = Join-Path $RepoRoot "templates\$tplFolder"
    if (Test-Path $tplPath) {
        Add-Section -OutFile $outFile -Header "FRONTEND  (templates\$tplFolder\)"
        $files = Get-ChildItem -Path $tplPath -Recurse -File `
            | Where-Object { $_.Extension -in '.html', '.htm', '.js', '.css', '.txt' } `
            | Sort-Object FullName
        foreach ($f in $files) {
            $rel = $f.FullName.Substring($RepoRoot.Length + 1)
            Add-FileBlock -OutFile $outFile -File $f -RelPath $rel
        }
    } else {
        Add-Content -Path $outFile -Value "`r`n(no frontend folder found at templates\$tplFolder\)`r`n" -Encoding UTF8
    }

    $size = (Get-Item $outFile).Length
    Write-Output ("OK  {0,-45} {1,12:N0} bytes  ->  temp\{0}.txt" -f $key, $size)
}
