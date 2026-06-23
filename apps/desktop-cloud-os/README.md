# International Trade Cloud OS Desktop

This is the Windows desktop shell for the International Engineering Trade Cloud OS.

## Run in development

```powershell
cd C:\Users\Surface\Documents\智慧情报分析平台\02_源代码\desktop-cloud-os
npm install
npm start
```

The desktop shell starts `..\decision-hub\server.ps1 -Port 8787` and opens `http://127.0.0.1:8787/`.

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
