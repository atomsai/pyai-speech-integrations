# Add a voice assistant to a website and save one confirmed demo enquiry

[Open the minimal site](https://pyai-voice-demo-wfls74alya-uc.a.run.app/managed-widget/start). Opening the page loads the button. Clicking it and allowing the microphone starts a cloud voice session and uses a slot in the demo's daily allowance. Use fictional details. The demo has no phone number and sends no email.

## Put the button on an empty page

1. Select your test project and verify its ID, environment, billing and limits with `whoami`. Create or select a voice agent. Our example is Lantern Desk, a fictional appointment-reminder service supporting teams of up to ten. Give your agent these facts and the instruction to stop when interrupted. This example uses facts in the saved agent profile.
2. In **Agents → Website & phone**, allow the exact HTTPS origin where you will serve the page. Set the daily widget-wide and per-IP session limits, preview and publish. These limits count session starts. They do not enforce a lifetime spending cap.
3. Paste the published script into an empty HTML page. Use your own public widget ID. Our measured demo pins browser runtime v12.1. Keep private keys off the page. With a restrictive Content Security Policy, allow the widget script, API HTTPS and WebSocket connections, and apply a per-response style nonce as shown in the server example.
4. Open the page from the allowed website, click the button and allow microphone access. Starting from a local file or a different website changes the origin.

```html
<!doctype html>
<html lang="en">
<meta charset="utf-8">
<title>Ask Lantern Desk</title>
<h1>Ask Lantern Desk</h1>
<script src="https://cdn.pyai.com/widget/v12.1/pyai-widget.js"
        data-widget="YOUR_PUBLIC_WIDGET_ID" async></script>
</html>
```

[Minimal page](public/managed-start.html) · [Official widget setup and privacy requirements](https://docs.pyai.com/guides/website-voice-widget)

## Connect the test backend

The example's only write is a private synthetic record containing a receipt, team size `4`, and `needs_reminders: true`. It never creates a real lead. The browser cannot authorize the webhook.

- Deploy the [example server](server.mjs) with its [private storage adapter](cloud-store.mjs). Set `ENQUIRY_AGENT_ID` to your agent ID. Generate a dedicated high-entropy credential, configure its SHA-256 hexadecimal digest in `ENQUIRY_TOKEN_SHA256`, and keep the credential in the registered server tool. The existing demo's other environment settings are in the [deployment guide](../PUBLIC-DEMO.md).
- Register the server tool `save_lantern_demo_enquiry` with your site's HTTPS `/api/managed-enquiry` endpoint, execution mode `server`, and side effect `action`. Set `auth_header` to `X-Lantern-Demo-Key` and `auth_secret` to the dedicated credential. The demonstration authenticates that header over HTTPS. Declare three required arguments: integer `team_size`, boolean `needs_reminders`, and boolean `confirmed`. Restrict the values to `4`, `true`, and `true` respectively. [Server tool registration and binding](https://docs.pyai.com/guides/omni-tools)
- Bind that tool to the demo agent. Tell it to call the tool only after the visitor expressly asks to save the fictional enquiry, and to announce success only after receiving the receipt. Keep any unrelated bindings on a shared agent intact.
- Verify the saved receipt in private storage. A create-only write keyed by the agent and call ID makes replay return the original receipt. A spoken promise, a transcript or a successful HTTP connection alone cannot establish a save.

## Try the three turns

1. Ask “What does Lantern Desk do? Can it help with appointment reminders?” Listen for an answer grounded in the product facts.
2. While the answer is audible, say “Wait, stop. Tell me only how many people are on our team.” The fictional visitor is on a four-person team. Listen for the previous answer to stop and a short reply about a four-person team.
3. Say “Yes, please save that synthetic enquiry now.” Look for one successful invocation and exactly one new receipt. If the response is uncertain, check the original receipt before considering another submission.

## Measured run on 27 November 2026

The timer started with an empty site directory. The PyAI test account, fictional agent profile, published widget, authorized HTTPS origin and hosted application already existed. The new HTML page and save action did not. This measures adding the feature to a prepared project. It excludes account signup, origin provisioning and the time to create the original agent.

The first public page loaded after **5 min 7 s**. The first managed conversation answered the product question, accepted a spoken interruption and wrote one receipt after **6 min 50 s** from the original start. A transcription of the mixed browser speaker and synthetic microphone recording contains “Lantern Desk sends reminder messages,” followed by “Wait, stop” and “Four people are on your team.” The browser stopped 27 scheduled audio buffers **300 ms** after the interrupting clip began. At that instant, up to **2,003 ms** of audio remained queued. These are browser audio-graph measurements from one run.

The original webhook persisted the record but returned only `saved: true`. The assistant correctly reported uncertainty. A fresh storage read confirmed a single four-person reminder enquiry. We changed the response to include `success: true` only after verifying the expected receipt. A missing or mismatched receipt still fails closed. Each run uses synthetic US-English visitor audio, Chromium in Google Cloud us-central1 and the widget's public v12.1 script. Neither a carrier nor a customer record is involved.
