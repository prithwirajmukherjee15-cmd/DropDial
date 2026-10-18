# Removing the macOS "could not verify" warning (Developer ID + notarization)

The build already signs and notarizes DropDial automatically **once these repository secrets exist**
(GitHub → Settings → Secrets and variables → Actions → New repository secret).

1. Join the Apple Developer Program ($99/year): https://developer.apple.com/programs/
2. In Xcode → Settings → Accounts (or developer.apple.com → Certificates), create a
   **Developer ID Application** certificate. Export it from Keychain Access as a `.p12` with a password.
3. Create an app-specific password for your Apple ID at https://account.apple.com → Sign-In and Security.
4. Add the secrets:

| Secret | Value |
|---|---|
| `MACOS_CERT_P12` | the .p12 file, base64-encoded: `base64 -i cert.p12 \| pbcopy` |
| `MACOS_CERT_PASSWORD` | the .p12 export password |
| `MACOS_SIGN_IDENTITY` | e.g. `Developer ID Application: Your Name (TEAMID1234)` |
| `APPLE_ID` | your Apple ID email |
| `APPLE_APP_PASSWORD` | the app-specific password |
| `APPLE_TEAM_ID` | your 10-character Team ID |

Push any commit (or re-run the "Build Windows app" workflow). The Mac job will sign every binary with
the hardened runtime, submit to Apple's notary service, staple the ticket to the app and the .dmg,
and verify with `spctl`. Downloads then open with no warning.
