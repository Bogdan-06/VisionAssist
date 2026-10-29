# Use Google Gemini with VisionAssist

Gemini is optional. Camera preview, object recognition and installed Romanian TextToSpeech
continue locally without an account or internet. Google currently offers a limited free tier
for `gemini-3.8-live`. Your Google project's tier, quotas and terms determine availability and
charges; this app does not enable billing or guarantee unlimited free use.

## On this computer

1. Open `C:\Users\Moth\Desktop\VisionAssist\backend\.env.local` privately in a text editor.
   The Gemini key has already been saved and successfully tested. Keep `GEMINI_API_KEY` and
   the existing `APP_ACCESS_TOKEN` there. Do not put either value in `.env.example` or chat.
2. Open PowerShell and run:

   ```powershell
   cd C:\Users\Moth\Desktop\VisionAssist\backend
   node --env-file=.env.local src/server.mjs
   ```

   Leave this window running while using the assistant. It should say it is listening on
   `127.0.0.1:8787`. Stop it with Ctrl+C when finished.
3. Install the supplied `VisionAssist-0.5.0-debug.apk` on your Android phone, or open the
   Desktop project in Android Studio and Run the app. Android 8.0 or later is required.
4. For a USB connection, enable USB debugging on the phone, connect it and approve that
   computer on the phone. In another PowerShell window run:

   ```powershell
   & "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" devices
   ```

   Find your phone's serial. Replace `YOUR_PHONE_SERIAL` below with that serial:

   ```powershell
   & "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" -s YOUR_PHONE_SERIAL reverse tcp:8787 tcp:8787
   ```

   This forwarding usually needs repeating after reconnecting the phone. The phone needs
   internet for Gemini even though the backend is reached over USB.

## In VisionAssist

5. Open **Configurarea serverului vocal**, select **Google Gemini**, and enter:
   - Server: `http://127.0.0.1:8787` (USB/debug only).
   - Access code: the value after `APP_ACCESS_TOKEN=` in the private `.env.local` file.
     Use the separate app access code, never the Gemini or OpenAI API key.
   Select **Salvează**. The app encrypts this access code using Android Keystore.
6. Select **Pornește conversația AI**, grant microphone permission, and wait for **Ascultă**.
   Ask a question in Romanian. Voice goes to Google while the conversation is running.
7. To describe a scene, start the camera and select **Ce este în fața mea? Trimite o fotografie**.
   This sends one fresh photo. A voice request for a description asks for confirmation on
   the phone; it never silently captures or uploads an image.
8. To stop, select **Oprește conversația AI**, or leave the app. Both close the microphone.
   A local announcement also immediately ends the Gemini session. Restart the conversation
   after the announcement if wanted. There is no automatic reconnection or provider fallback.

## If something fails

- “Gemini nu este configurat”: check `GEMINI_API_KEY` in `.env.local`, then restart the backend.
- Access refused: check the app's separate access code and server address.
- Quota message: check the project's free quota in Google AI Studio and wait for its reset.
  Creating another key does not replenish the project's quota. Enabling paid billing is optional.
- Session ended: restart manually. Tokens and Live sessions expire; resumption is not implemented.
- No local Romanian voice: install an offline Romanian TTS voice in Android's text-to-speech settings.
- The server must remain running and the USB forwarding active. Remote/release connections
  require HTTPS and a properly secured backend.

Optional developer check (contacts Google and consumes quota):

```powershell
node --env-file=.env.local scripts/verify-gemini.mjs --session
```

This checks actual token minting, session setup and a short spoken response without saving audio.
Phone acoustics, Romanian pronunciation, TalkBack use and real camera conditions still need
hands-on testing while stationary. Model descriptions can be wrong. VisionAssist does not
confirm hazards, distances or safe paths, and does not replace a white cane.

References checked 2026-10-15:
- [Google pricing and free tier](https://ai.google.dev/gemini-api/docs/pricing)
- [Live capabilities](https://ai.google.dev/gemini-api/docs/live-api/capabilities)
- [Ephemeral tokens](https://ai.google.dev/gemini-api/docs/live-api/ephemeral-tokens)
- [Raw protocol and token constraints](https://ai.google.dev/api/live)
