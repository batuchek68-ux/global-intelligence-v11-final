# International Trade Cloud OS Desktop

This is the Windows desktop shell for the International Engineering Trade Cloud OS.

## Run in development

```powershell
cd C:\Users\Surface\Documents\智慧情报分析平台\02_源代码\desktop-cloud-os
npm install
npm start
```

The desktop shell starts the v11 Decision Hub bridge and opens `http://127.0.0.1:8787/`. It must use v11 APIs and must not depend on the old legacy wisdom-platform workspace at runtime.

## Enterprise license variables

Production deployments should set:

```powershell
$env:CLOUD_OS_REQUIRE_LICENSE = "1"
$env:CLOUD_OS_LICENSE_ENDPOINT = "https://your-license-center.example.com/api/license/check"
$env:CLOUD_OS_ENTERPRISE_ID = "enterprise-code"
$env:CLOUD_OS_LICENSE_TOKEN = "runtime-token"
```

Local owner mode works without an endpoint unless `CLOUD_OS_REQUIRE_LICENSE=1` is set.

## Package

```powershell
npm run dist
```

The installer and portable build are written to `dist/`.

## v11 Runtime Boundary

This desktop package belongs to v11. The old `legacy wisdom-platform workspace` desktop code can be inspected as migration reference only. Runtime paths, packaging, API calls, license checks, cloud status, and owner approval flows must stay inside `global-intelligence-v11`.

