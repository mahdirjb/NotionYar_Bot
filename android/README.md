# NotionYar Android

This is a thin Android shell around the production NotionYar web app. The web app
remains the source of truth, so login, Telegram Mini App behavior, IndexedDB
offline queueing, reports and future web releases stay aligned between platforms.

## Build

Open the `android` folder in Android Studio, or run:

```powershell
.\gradlew.bat assembleDebug
```

The debug APK is generated at:

```text
app/build/outputs/apk/debug/app-debug.apk
```

To use another deployment URL for a staging build:

```powershell
.\gradlew.bat assembleDebug -PwebAppUrl=https://staging.example.com/
```

The device must open the URL once while online so the PWA shell and offline
outbox can be cached. After that, writes can be entered offline and synced when
the connection returns.

## Release

Before publishing to Google Play, create a release keystore, configure signing in
`app/build.gradle`, replace the temporary launcher icon with the branded PNG/adaptive
icon set, and verify the production domain over HTTPS. Do not embed Telegram or
Notion secrets in this Android project.
