# PoC App - XCLMitigation Demo

This is a simple proof-of-concept app that demonstrates the XCLMitigation working.

## What it does

The app contains a simple login screen with:
- Username field (autofillHints="username")
- Password field (autofillHints="password")
- Login button

## How to test the mitigation

1. **Install the XCLMitigation app first:**
   ```bash
   cd ../XCLMitigation
   ./gradlew installDebug
   ```

2. **Enable the autofill service:**
   - Go to Settings → System → Languages & input → Autofill service
   - Select "Secure Autofill PoC"

3. **Install and run this PoC app:**
   ```bash
   cd ../PoCApp
   ./gradlew installDebug
   ```

4. **Test the mitigation:**
   - Open PoC App
   - Tap on the username field
   - The autofill suggestion will appear
   - When you select it, the **WarningActivity** will show a security warning
   - This proves the XCLMitigation is working - it intercepts the autofill request
   - After confirming, credentials are filled

## What this proves

The mitigation successfully:
- Intercepts autofill requests from third-party apps
- Shows a security warning when digital asset link verification fails
- Only releases credentials after explicit user confirmation
- Prevents silent credential leakage to unverified apps
