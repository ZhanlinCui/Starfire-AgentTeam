---
name: social-media-post
description: Playbook for posting content (video, image, or text) to Reno Stars social media accounts via browser automation. Use when the user asks to post to TikTok, Instagram, Facebook, X/Twitter, LinkedIn, YouTube Shorts, Xiaohongshu, or Reddit, or when running the social-media-poster / social-media-engage crons. Captures every quirk and failure mode learned the hard way on 2026-04-07 across all 8 platforms.
---

# Social Media Post Playbook

This skill is the source of truth for browser-automating posts to Reno Stars accounts. The cron prompts (`social-media-poster.md`, `social-media-engage.md`, `social-media-monitor.md`) reference this skill — when they're updated they should stay aligned with what's here.

## Dreamina before/after morph video generation (added 2026-04-08)

The social-media-poster cron generates a before/after morph video every 2 days using Dreamina (CapCut's AI video tool). The cron picks an unused before/after image pair from `project_image_pairs`, sends both to Dreamina, generates the video, then posts it to all 7 platforms via the normal flow.

### State file (avoid re-using project pairs)

`/Users/renostars/reno-star-business-intelligent/data/dreamina-video-history.jsonl` — append-only JSON Lines, one entry per generated video. Schema:
```json
{"used_at":"<ISO>","project_slug":"<slug>","pair_id":"<uuid>","video_path":"<abs-path>","posted_post_id":"<post_id|null>","note":"<optional>"}
```
**Always append to this file BEFORE posting** so an interrupted run doesn't pick the same pair on retry.

### Cadence check

```bash
HISTORY=/Users/renostars/reno-star-business-intelligent/data/dreamina-video-history.jsonl
LAST_TS=$(date -j -u -f "%Y-%m-%dT%H:%M:%SZ" "$(tail -1 "$HISTORY" | jq -r .used_at)" +%s 2>/dev/null || echo 0)
HOURS_SINCE=$(( ($(date -u +%s) - LAST_TS) / 3600 ))
# >= 47 → it's a video day; otherwise normal photo post
```

### Selecting an unused project pair

```sql
SELECT pip.id AS pair_id, pip.before_image_url, pip.after_image_url,
       pip.title_en, p.slug, p.title_en AS project_title,
       p.location_city, p.budget_range, p.duration_en
FROM project_image_pairs pip
JOIN projects p ON p.id = pip.project_id
WHERE pip.before_image_url IS NOT NULL
  AND pip.after_image_url IS NOT NULL
  AND p.is_published = true
  AND p.slug NOT IN (<list of project_slug from history>)
ORDER BY p.created_at DESC
LIMIT 10;
```

### Image pair quality gate (run BEFORE uploading to Dreamina)

For each candidate pair, download both images and check ALL of the following. Skip the pair and try the next one if any check fails.

**1. Aspect ratio must match (no padding allowed)**
```js
const sharp = require('sharp');
const bMeta = await sharp(beforeBuf).metadata();
const aMeta = await sharp(afterBuf).metadata();
const bRatio = bMeta.width / bMeta.height;
const aRatio = aMeta.width / aMeta.height;
if (Math.abs(bRatio - aRatio) > 0.05) { /* SKIP — aspect mismatch */ }
```
Do NOT pad or crop to force a match — the morph looks bad with letterboxed frames. Just skip to the next pair.

**2. Minimum resolution: 800px on shortest side**
```js
const minDim = Math.min(bMeta.width, bMeta.height, aMeta.width, aMeta.height);
if (minDim < 800) { /* SKIP — too low res */ }
```

**3. Both URLs return actual image data (not HTML 404)**
Download both images and verify the first bytes are a JPEG/PNG header (`\xFF\xD8` for JPEG, `\x89PNG` for PNG). Some R2 URLs return HTML error pages with a 200 status code.

**4. Visual quality check — download and inspect**
After passing the automated checks above, visually verify (via sharp metadata or by reading the image):
- **Same space, same general orientation**: before and after must show the same room/area facing roughly the same direction. Exact angle match is NOT required — the morph prompt handles camera movement. But completely different rooms or opposite-wall shots won't work.
- **No people visible**: mirror selfies, contractors in frame, family members — skip these. The morph will try to "transition" the person which looks uncanny.
- **Compelling transformation**: the before/after difference should be visually dramatic (old→new, dark→light, cluttered→clean). Skip pairs where the change is subtle (e.g. just a new faucet on an otherwise identical vanity).
- **Not just a close-up of tile/wall**: both frames need recognizable room context (fixtures, counters, cabinets). A tight crop of blank tile produces a boring morph.

**5. File size < 10MB per image**
If either image exceeds 10MB, resize with sharp before uploading:
```js
if (buf.length > 10 * 1024 * 1024) {
  buf = await sharp(buf).resize(2048, 2048, { fit: 'inside', withoutEnlargement: true }).jpeg({ quality: 90 }).toBuffer();
}
```

### Selection priority
When multiple pairs pass all checks, prefer:
1. **Portrait/mobile aspect (3:4 or 9:16) over landscape** — videos are consumed on phones, vertical fills the screen. Only use landscape (4:3) if no portrait pairs are available.
2. Higher resolution over lower
3. Projects from different cities (for SEO diversity) — avoid posting 3 Richmond videos in a row
4. Kitchen/whole-house over bathroom-only (more dramatic transformations)

### Dreamina UI flow

URL: `https://dreamina.capcut.com/ai-tool/home?type=video&model=dreamina_seedance_40_pro`

Login state: the user has Dreamina open in Chrome at `dreamina.capcut.com` already; the session is persistent. If not logged in, abort and ping the user via Telegram.

The tool supports a "first frame + last frame + prompt" workflow which is exactly what we need for the morph effect.

**The exact prompt to use** (Chinese, do not translate or modify):
```
首帧和尾帧是同一个地方同一个角度，这是装修前后的两个照片，我想要第一张照片里面的设施都向图片外滑走，后面新的设备在滑入, 这个期间镜头慢慢转移动到最终位置
```

Translation for context: "First frame and last frame are the same place same angle — these are the before and after photos. I want all the fixtures in the first photo to slide off the screen and the new equipment to slide in behind, with the camera slowly panning to the final position during the transition."

**Steps** (selectors confirmed on 2026-04-08 against the live Dreamina UI):

1. Connect via puppeteer-core CDP (port 9222), find or open the Dreamina tab.
   ```js
   let dr = pages.find(p => p.url().includes('dreamina.capcut.com'));
   if (!dr) dr = await browser.newPage();
   await dr.bringToFront();
   await dr.goto('https://dreamina.capcut.com/ai-tool/home?type=video&model=dreamina_seedance_40_pro', { waitUntil: 'networkidle2', timeout: 30000 });
   await new Promise(r => setTimeout(r, 4000));
   ```

2. Verify mode + login state by inspecting body text — should contain "First frame", "Last frame", "First and last frames", "10s", "4:3". If "sign in" or "log in" appears in the first 500 chars, abort and ping user.

3. Download the before/after image URLs locally (Dreamina needs file uploads, not URLs):
   ```js
   const fs = require('fs');
   for (const [key, url] of [['before','/tmp/dreamina-before.jpg'], ['after','/tmp/dreamina-after.jpg']]) { /* ... */ }
   // Use fetch + arrayBuffer to download both image URLs to /tmp
   ```

4. **Upload the frames via the hidden file inputs.** Dreamina has 4 hidden `<input type="file">` elements initially. **React re-renders the DOM after the first upload** — 4 inputs become 2, and the indexes shift. Upload in two steps:
   ```js
   // Step 1: Upload FIRST frame to inputs[0]
   let inputs = await dr.$$('input[type=file]');
   // Initially 4 inputs: [First, Last, First, Last]
   await inputs[0].uploadFile('/tmp/dreamina-before.jpg');
   await new Promise(r => setTimeout(r, 2500));
   
   // Step 2: Re-query! React re-rendered — now only 2 inputs remain.
   // inputs[0] is now the EMPTY last frame slot.
   inputs = await dr.$$('input[type=file]');
   await inputs[0].uploadFile('/tmp/dreamina-after.jpg');
   await new Promise(r => setTimeout(r, 2500));
   ```
   **CRITICAL: Always re-query `$$('input[type=file]')` after the first upload.** If you use the stale reference, the second upload silently fails.
   
   The inputs accept `image/jpeg,image/jpg,image/png,image/webp,image/bmp` only (no .heic, no .gif, no .mp4). If the source is anything else, convert via sharp first.
   
   **Aspect ratio must match.** Dreamina rejects mismatched aspect ratios with: "Aspect ratios of the first and the last frame should be the same". The quality gate above already filters for this — only pairs with matching ratios (within 0.05 tolerance) reach this step. Do NOT pad/letterbox to force a match; the morph looks bad with white bars. If a pair somehow gets here with mismatched ratios, skip it.

5. **Type the prompt** into the description textarea. There are 2 textareas with placeholder `"Describe the video you're imagining"` — use index `[0]`. It's a plain `<textarea>`, not Lexical, so `keyboard.type` works directly:
   ```js
   const tas = await dr.$$('textarea');
   await tas[0].click();
   await new Promise(r => setTimeout(r, 300));
   await dr.keyboard.type('首帧和尾帧是同一个地方同一个角度，这是装修前后的两个照片，我想要第一张照片里面的设施都向图片外滑走，后面新的设备在滑入, 这个期间镜头慢慢转移动到最终位置', { delay: 5 });
   ```

6. **Wait for the Generate button to appear.** The Generate button is NOT in the DOM until both frames are uploaded AND the prompt is non-empty. Poll for it (up to 30s):
   ```js
   for (let i = 0; i < 30; i++) {
     await new Promise(r => setTimeout(r, 1000));
     const found = await dr.evaluate(() => {
       const btn = Array.from(document.querySelectorAll('button, [role=button]'))
         .find(b => b.offsetParent && /^(generate|create|生成|创建)$/i.test((b.innerText || '').trim()) && !b.disabled);
       return !!btn;
     });
     if (found) break;
   }
   ```

7. **Click Generate**:
   ```js
   await dr.evaluate(() => {
     const btn = Array.from(document.querySelectorAll('button, [role=button]'))
       .find(b => b.offsetParent && /^(generate|create|生成|创建)$/i.test((b.innerText || '').trim()) && !b.disabled);
     btn.click();
   });
   ```
   This consumes credits (visible cost on the page is "230" per 10s generation as of 2026-04-08; you have ~508 credits = ~2 generations of headroom — top up if approaching empty).

8. **Poll for the render to complete.** Dreamina shows the completed video in a result card with a download button. Hard cap: 5 minutes (300s). Poll every 5 seconds:
   ```js
   for (let i = 0; i < 60; i++) {
     await new Promise(r => setTimeout(r, 5000));
     const ready = await dr.evaluate(() => {
       // Check for a video element OR a "Download" button OR the result card
       const hasVideo = !!document.querySelector('video[src]');
       const dlBtn = Array.from(document.querySelectorAll('button, [role=button], [aria-label]'))
         .find(b => b.offsetParent && /(download|下载)/i.test((b.innerText || b.getAttribute('aria-label') || '')));
       return { hasVideo, hasDownload: !!dlBtn };
     });
     if (ready.hasDownload || ready.hasVideo) break;
   }
   ```

9. **Click the Download button.** Dreamina downloads to `~/Downloads/` with a long autogenerated filename like `dreamina-2026-04-08-XXXX-<chinese-prompt-prefix>.mp4`. Watch the directory:
   ```bash
   BEFORE=$(ls -1 ~/Downloads/dreamina*.mp4 2>/dev/null | wc -l)
   # ... click download ...
   for i in 1 2 3 4 5 6 7 8 9 10; do
     sleep 2
     AFTER=$(ls -1 ~/Downloads/dreamina*.mp4 2>/dev/null | wc -l)
     [ "$AFTER" -gt "$BEFORE" ] && break
   done
   NEW_FILE=$(ls -1t ~/Downloads/dreamina*.mp4 | head -1)
   ```

10. **Move to a clean ASCII path** under `/Users/renostars/`:
    ```bash
    DEST="/Users/renostars/dreamina-${PROJECT_SLUG}-$(date +%Y%m%d).mp4"
    mv "$NEW_FILE" "$DEST"
    ```

11. **Append to history file** + proceed to normal posting flow with `$DEST` as the video file path.

### Verified facts (2026-04-08, Reno Stars Sylvia account)

- Logged-in session is persistent in the user's Chrome profile — no re-auth needed
- URL `?type=video&model=dreamina_seedance_40_pro` lands directly in the "First and last frames" mode
- 4 hidden `<input type=file>` paired as First/Last/First/Last — use index 0 for first frame, then RE-QUERY and use new index 0 for last frame (React re-renders after first upload, shifting from 4→2 inputs)
- 2 plain `<textarea>` with placeholder "Describe the video you're imagining" — use index 0
- Mode shows: "AI Video / Dreamina Seedance 2.0 / First and last frames / 4:3 / 10s / 230 credits per generation"
- ~278 Basic credits available as of 2026-04-09 (after 2 test generations; ≈ 1 generation remaining — credits may need topping up)
- Both frames MUST have matching aspect ratios — skip mismatched pairs (do NOT pad/letterbox)
- Quality gate: min 800px shortest side, same space/orientation, no people, compelling transformation, no blank close-ups
- Prefer landscape 4:3 pairs, diverse cities, kitchens/whole-house over bathroom-only
- Some R2 URLs return HTML instead of images despite 200 status — always verify first bytes are JPEG/PNG header
- Generate button is gated — appears only after both uploads complete AND prompt is non-empty
- Output mp4 lands in `~/Downloads/` with a `dreamina-*.mp4` filename pattern

### Failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| `dreamina.capcut.com` shows login page | Session expired | Abort, ping user via Telegram, do not bother retrying |
| Generate button stays disabled | First/last frame upload didn't complete | Wait 10s, check `<img>` previews appeared, re-upload if missing |
| Render takes > 5 min | Server queue or model issue | Hard cap at 300s, fall back to photo post for today |
| Output mp4 has the wrong content (not a morph) | Wrong mode selected at top of page | Re-verify model param `dreamina_seedance_40_pro` is in URL; some other modes don't accept first+last frame |
| Image upload "image too large" error | Source > 10 MB | Resize via sharp before uploading: `sharp(buf).resize(2048, null, { withoutEnlargement: true }).toBuffer()` |
| "Aspect ratios of the first and the last frame should be the same" | Before/after images have different aspect ratios | Skip this pair — the quality gate should have caught it. Do NOT pad; letterboxed morphs look bad |
| Second frame upload silently fails (only 1 thumbnail visible) | Used stale input handle after first upload — React re-renders DOM | Always re-query `dr.$$('input[type=file]')` after first upload; indexes shift from 4→2 |
| All project_image_pairs already used | History file is full (>125 entries) | Telegram alert "exhausted all before/after pairs", fall back to photo posts indefinitely |

### Cost note

Dreamina credits are consumed per generation. If the generation fails AFTER credits are charged but BEFORE we get the mp4, that's wasted credit. To minimize: verify both image previews are visible BEFORE clicking Generate. If an aborted generation leaves the page in a weird state, refresh and re-try once.

---

## ⚠️ Critical lessons added 2026-04-08

These lessons override anything contradictory in the recipes below — when in doubt, prefer these:

### Use puppeteer-core directly, NOT the playwright MCP

The playwright MCP wrapper at `~/.openclaw/playwright-mcp-wrapper.js` is **broken/slow** as of 2026-04-08. Even `mcp__playwright__browser_tabs action=list` hangs for 15+ minutes. **Bypass it entirely.** Use puppeteer-core directly via Bash + Node:

```js
const puppeteer = require('/opt/homebrew/lib/node_modules/puppeteer-core');
const browser = await puppeteer.connect({ browserURL: 'http://127.0.0.1:9222', defaultViewport: null });
const pages = await browser.pages();
const li = pages.find(p => p.url().includes('linkedin.com'));
await li.bringToFront();
// ... do work ...
await browser.disconnect();  // Only at the END of the entire flow.
```

**Calls return in 1-3 seconds.** No MCP middleware overhead.

### Modal-aware element finding — beware stale background elements

LinkedIn (and other React SPAs) leave **stale buttons in the DOM behind a modal overlay**. Querying by `aria-label` returns the FIRST match, which is often the background element — not the modal's. The background button is covered by the overlay so clicks do nothing. **Always scope your selectors to the open modal**:

```js
// BAD: finds the personal feed share box's "Add a video" button at (424,164)
// which is covered by the modal you just opened.
const btn = document.querySelector('button[aria-label="Add a video"]');

// GOOD: walk down from the modal's known anchor text
const modal = Array.from(document.querySelectorAll('div'))
  .filter(d => d.offsetParent && /What do you want to talk about/.test(d.innerText) && d.offsetWidth < 1000)
  .sort((a,b) => a.offsetWidth*a.offsetHeight - b.offsetWidth*b.offsetHeight)[0];
const btn = modal && Array.from(modal.querySelectorAll('button'))
  .find(b => b.offsetParent && b.getAttribute('aria-label') === 'Add media');
```

### Don't trust puppeteer screenshots when DOM disagrees

Puppeteer's `page.screenshot()` may return **byte-identical cached images** for repeated calls when the page is in certain states. If your DOM query says "no contenteditable" but a screenshot shows a modal — md5sum the screenshots first to check for caching. Trust the DOM, not the screenshot.

```bash
md5 /tmp/li-now.png /tmp/li-fresh.png   # if same → screenshot is stale
```

### Disconnecting puppeteer mid-flow closes modals

LinkedIn's composer modal **closes when puppeteer disconnects between steps**. Same connection = open modal stays open. Multiple Bash invocations each spawn a new node process (= new puppeteer connection = closed modal). **Do the entire LinkedIn flow in one Node script**, not in iterative Bash calls.

### File System Access API blocks Meta Business Suite + LinkedIn personal feed

`window.showOpenFilePicker()` is the modern File API and **puppeteer cannot intercept it**. Affected:
- **Meta Business Suite Composer** (`business.facebook.com/latest/composer`) — for both photo and video upload
- **LinkedIn personal feed share box** (the `/feed/` Video button at viewport ~424,164) — uses showOpenFilePicker; even direct OS-level clicks via osascript don't reliably trigger the file dialog

**Workarounds (use these — they DO work):**
- **Facebook**: post via `https://www.facebook.com/profile.php?id=100068876523966` directly. The page profile composer has 2 file inputs in the DOM at all times (`accept` containing `video/*`). Just call `inputElement.uploadFile(file)` directly with no button click.
- **Instagram**: post via `https://www.instagram.com/`, click the "New post" SVG, then "Post" sub-menu, then upload via the file input that appears.
- **LinkedIn**: post via the **company admin**, NOT the personal feed. Path: `https://www.linkedin.com/company/103326696/admin/dashboard/` → click the "Create" button → click "Start a post" in the popup → in the modal, click `aria-label="Add media"` (NOT "Add a video"). The `Add media` button uses the legacy file picker — `waitForFileChooser` fires first try. Bonus: this posts as the company page, which is what we want.

### TikTok caption editing AFTER post

If TikTok defaulted to filename as caption (or you typed wrong): navigate to `https://www.tiktok.com/tiktokstudio/upload/post/<video_id>?from=creator_center` — that's the edit endpoint. To find a video's id, click the **leftmost** icon (around viewport x=1078) in the video row on `tiktok.com/tiktokstudio/content`. The middle icon (x=1128) opens analytics, the third (x=1178) opens comments, the rightmost (x=1228) opens a Download/Delete menu only.

On the edit page, the "Save" button at the bottom-left commits the changes.

### TikTok Lexical editor Cmd+A is broken

`keyboard.down('Meta'); keyboard.press('a'); keyboard.up('Meta')` only deletes ONE character on TikTok's Lexical editor. To clear the auto-filled filename: hammer `Backspace` for `editorContent.length + 5` iterations:
```js
const len = await page.evaluate(() => document.querySelector('[contenteditable="true"]').innerText.length);
for (let i = 0; i < len + 5; i++) await page.keyboard.press('Backspace');
```

### Filename pre-fill on TikTok upload

When uploading to `tiktok.com/tiktokstudio/upload`, TikTok pre-fills the description with the filename (without extension). If you don't clear it before typing, your real caption gets appended to the filename. **Always clear the editor with the Backspace hammer above before typing the real caption.**

### Direct uploadFile for hidden inputs

For platforms with `<input type="file">` already in the DOM (Facebook page composer, Instagram /create, X compose, TikTok upload, Xiaohongshu, YouTube Studio), **you don't need to click any button**. Find the file-accepting input and call `uploadFile(filePath)` directly — the page's change handler reacts as if the user picked the file.

```js
// Find the video-accepting input (some pages have multiple file inputs)
const inputs = await page.$$('input[type=file]');
const videoIdx = await page.evaluate(() => {
  return Array.from(document.querySelectorAll('input[type=file]'))
    .findIndex(i => (i.getAttribute('accept') || '').includes('video'));
});
await inputs[videoIdx].uploadFile('/Users/renostars/video.mp4');
```

---

## Universal pre-flight (do these BEFORE touching any platform)

1. **Files must be under `/Users/renostars/`** — playwright-mcp's file_upload tool refuses paths outside the user home. Move files into `/Users/renostars/<safe-name>.<ext>` before uploading. Avoid spaces, Chinese characters, and ellipsis in filenames; some upload widgets choke on them.
2. **Chrome CDP at `:9222` must be running**:
   `open -na "Google Chrome" --args --user-data-dir="/Users/renostars/.openclaw/chrome-profile" --remote-debugging-port=9222`
3. **Disable beforeunload dialogs preemptively** on any tab with a long form (TikTok especially):
   `await page.evaluate(() => { window.onbeforeunload = null; window.addEventListener('beforeunload', e => e.stopImmediatePropagation(), true); });`
4. **Wrap risky/slow site interactions in `mcp__playwright__browser_run_code` with explicit short timeouts** — 10s for nav, 5s for clicks. The playwright-mcp default is 60s and will hang the conversation.
5. **No promotional CTAs** in any organic post or reply. Don't write "We do X at Reno Stars" or "feel free to reach out" or "happy to help" — the account name on the post already attributes the brand. The user explicitly flagged this on 2026-04-07.

## Caption pattern

Reuse this structure across English-language platforms (adjust length per platform):

- **Hook line**: short, sense-based (e.g. "Same room, same angle — before and after 🏠")
- **Project context**: 1–2 sentences (location + scope + key features)
- **Project link**: full reno-stars.com/en/projects/<slug>/ URL (omit on Xiaohongshu and TikTok if it strips links)
- **Hashtags**: `#VancouverRenovation #BurnabyRenovation #BathroomRenovation #BeforeAndAfter #HomeRenovation #RenoStars` — adjust city tag to match the project location

For Xiaohongshu, use Chinese only and **no links / no phone / no address** — Rednote prohibits external promo content and the user explicitly said so.

For LinkedIn, drop the emoji and re-frame as a brief case study with a "Challenge / Result" structure.

For X, hard cap at 280 chars including the URL — keep only one hashtag block of 2–3 tags.

---

## Platform-by-platform recipes

### TikTok (video)

URL: `https://www.tiktok.com/tiktokstudio/upload?from=webapp`

1. **Disable beforeunload first** (see pre-flight #3) — TikTok will pop a "Leave site? Changes you made may not be saved" dialog mid-flow that blocks all clicks until handled.
2. **Upload via the existing file input** — TikTok has `<input type="file" accept="video/*">` already in the DOM (1 input). Use `inputHandle.uploadFile(filePath)` directly. No button click needed.
3. After upload, two dialogs may appear and need dismissing:
   - **"Turn on automatic content checks?"** → click `Turn on` (it's the safe default).
   - **"New editing features added"** → click `Got it`.
4. **Description field is a Lexical contenteditable**. ⚠️ **Do NOT use `document.execCommand('insertText', ...)` here** — it triggers `NotFoundError: Failed to execute 'removeChild'` inside React's reconciler and crashes the entire upload form to a "Something went wrong / Retry" page. The video is lost; you have to start over.
5. **TikTok pre-fills the description with the filename (without extension).** ⚠️ **`Cmd+A → Backspace` only deletes ONE character on TikTok's Lexical editor** — it does NOT select all. Confirmed broken 2026-04-08. **Correct way to clear:**
   ```js
   const len = await page.evaluate(() => document.querySelector('[contenteditable="true"]').innerText.length);
   for (let i = 0; i < len + 5; i++) await page.keyboard.press('Backspace');
   ```
6. After clearing, type the real caption with `page.keyboard.type(caption, { delay: 8 })`. The keyboard.type approach dispatches React-friendly input events that Lexical handles correctly.
7. The Post button is reachable via `Array.from(document.querySelectorAll('button')).find(b => /^post$/i.test((b.innerText||'').trim()))`. Don't try to click it before the upload finishes processing or it'll silently no-op.
8. **Success signal**: URL changes to `https://www.tiktok.com/tiktokstudio/content`.
9. **Caption length**: 4000 chars. Hashtags work inline.

### TikTok — editing a posted video's caption

If you posted with the wrong caption (most commonly: TikTok pre-filled with the filename and you didn't clear it), the caption can be edited via the upload-post URL pattern:

1. Navigate to `https://www.tiktok.com/tiktokstudio/content` to find the video id, OR jump straight to the edit URL if you already have it.
2. Edit URL: `https://www.tiktok.com/tiktokstudio/upload/post/<video_id>?from=creator_center`
3. The page loads with a `[contenteditable="true"]` Lexical editor pre-filled with the current caption + a `Save` button at the bottom-left.
4. Use the **Backspace hammer** (same as #5 above) to clear the existing caption. Then `keyboard.type` the new caption.
5. Click `Save`. URL navigates back to `/tiktokstudio/content` on success.

**Finding the edit icon from the content list**: in the row's action icon column (rightmost area, around viewport x=1078–1228, y varies by row), there are 4 icons:
- x=1078: **Edit** (navigates to the upload-post URL pattern above) ← THIS ONE
- x=1128: Analytics (`/tiktokstudio/analytics/<id>`)
- x=1178: Comments (`/tiktokstudio/comment/<id>`)
- x=1228: More menu (Download / Delete only — no edit option here)

The right-most "more" menu does NOT have edit. Use the leftmost icon for editing.

### X / Twitter (video)

URL: `https://x.com/compose/post`

1. Click "Add photos or video" button (or use the hidden `input[type=file]` directly).
2. Upload — wait for "Uploaded (100%)" status.
3. Click into the "Post text" textbox and use `browser_type` (fill works).
4. **Post button click is intercepted by an invisible overlay** in standard `browser_click`. Use:
   ```js
   document.querySelector('[data-testid="tweetButton"]').click()
   ```
   via `browser_evaluate`.
5. **Success signal**: navigates to `https://x.com/home`.
6. **Caption length**: 280 chars (including URL — assume 23 chars for any URL via t.co wrapping).

### Instagram (Reel)

URL: `https://www.instagram.com/`

1. Click the "New post" link in the left nav, then "Post" in the popout submenu (NOT "Live video" or "Ad").
2. In the "Create new post" modal, click "Select from computer" → upload.
3. **"Video posts are now shared as reels" info dialog** appears → click `OK`.
4. **Three sequential screens, each with a Next button**: Crop → Edit → Caption. Click `Next` twice to reach the caption screen.
5. Caption textbox role: `Write a caption...`. Use `browser_type` / fill.
6. Click `Share`. A "Sharing" dialog with a spinner shows for ~10 seconds, then closes. The new post will appear in the feed below.
7. **Caption length**: 2200 chars.
8. **Note**: Instagram + Facebook are linked through Meta Business Suite, so a Reel posted to one account doesn't automatically cross-post — handle each separately unless you explicitly use Meta Business Suite's create flow.

### Facebook (Page Reel)

URL: `https://www.facebook.com/profile.php?id=100068876523966` (Reno Stars page)

1. On the page, click the **"Reel"** button in the composer row (NOT "Photo/video" — that path uses a different flow that fails on long videos).
2. "Create reel" dialog opens. Click "Add video or drag and drop" → file picker → upload.
3. Wait for upload to complete. Click `Next` to move to the Edit step.
4. Click `Next` again to move to "Reel settings".
5. Fill the description textbox (it's a contenteditable; `browser_type` / fill works).
6. Click `Post`. Toast appears: "Your Post is successfully shared with EVERYONE" + a "Your reel is being processed" banner.
7. **Caption length**: 63206 chars (effectively unlimited for our use).

### LinkedIn (company page video)

URL: `https://www.linkedin.com/company/103326696/admin/dashboard/` (Reno Stars Construction Inc. — **must use the company admin path, NOT the personal `/feed/` page**, because the personal feed Video button uses File System Access API which puppeteer cannot intercept).

**This MUST be done in a single Node script** — disconnecting puppeteer between steps closes the modal.

1. Navigate to `https://www.linkedin.com/company/103326696/admin/dashboard/` with `waitUntil: 'load'`.
2. Click the page's `Create` button (a real `<button>` with text === 'Create').
3. In the popup, click "Start a post". The text "Start a post" lives inside an `<a>` ancestor — find it by walking up from the text node:
   ```js
   const candidates = Array.from(document.querySelectorAll('*'))
     .filter(e => Array.from(e.childNodes).some(n => n.nodeType === 3 && /^Start a post$/i.test(n.textContent.trim())));
   let el = candidates[0];
   while (el && !['BUTTON','A'].includes(el.tagName) && el.getAttribute('role') !== 'button') el = el.parentElement;
   el.click();
   ```
4. The composer modal opens with header "Reno Stars Construction Inc. — Post to Anyone". Body text contains "Create post modal" and "What do you want to talk about?".
5. **Find the modal-scoped "Add media" button** (NOT the personal feed's stale "Add a video"):
   ```js
   const modal = Array.from(document.querySelectorAll('div'))
     .filter(d => d.offsetParent && /Create post modal/.test(d.innerText) && /What do you want to talk about/.test(d.innerText))
     .sort((a,b) => a.offsetWidth*a.offsetHeight - b.offsetWidth*b.offsetHeight)[0];
   const addMedia = Array.from(modal.querySelectorAll('button'))
     .find(b => b.offsetParent && b.getAttribute('aria-label') === 'Add media');
   ```
   It's at roughly viewport (505, 519) on a 1322x882 viewport.
6. Set up `page.waitForFileChooser({ timeout: 8000 })` BEFORE the click, then click the Add media button via real puppeteer mouse: `await page.mouse.click(505, 519)` (or use the bounds from the queried element).
7. The FileChooser **fires reliably** — `chooser.accept([filePath])`.
8. Wait for the upload to process — poll for a `Next` button (`button.innerText === 'Next' && !disabled`). Usually <30s for ~10MB video.
9. Click `Next`. The composer transitions to the caption step.
10. Find the caption editor (`.ql-editor` or `[contenteditable="true"]`), click into it, and `keyboard.type` the caption.
11. Click `Post` (`b.innerText.trim() === 'Post' && !disabled`).
12. **Success signal**: page navigates to `/company/103326696/admin/page-posts/published/` AND body contains "Post successful. View post".
13. **Caption length**: 3000 chars.
14. **Tone**: drop emoji, write a brief case study (Challenge / Result framing). LinkedIn audience is B2B.

**Common failure modes for LinkedIn:**
- Finding `aria-label="Add a video"` and clicking it → DOES NOTHING. That's a stale button in the personal feed share box, covered by the modal overlay.
- Trying to post via `/feed/` first → blocked by File System Access API. Don't.
- Disconnecting puppeteer between steps → modal closes. Use one script.

### Google Business Profile (Google Posts)

URL: Search `Reno Stars Local Renovation Company Richmond BC` on Google → "Your business on Google" panel

Google Posts appear on the knowledge panel in Search + Maps. They expire after 7 days, so regular posting keeps the profile fresh. Must be logged in as airenostars@gmail.com.

1. Navigate to `https://www.google.com/search?q=Reno+Stars+Local+Renovation+Company+Richmond+BC`
2. Wait for the "Your business on Google" panel. Click **"Add update"** or **"Posts"** → **"Add update"**.
3. An iframe opens at `google.com/local/business/<id>/posts/create`. The post form has:
   - Description textarea (max 1500 chars)
   - "Add photo" button → file input for image upload
   - CTA button selector (Call now / Learn more / Book / Order / Sign up)
   - CTA URL field
4. Fill the description with the Google Posts draft (short, professional, with phone + website).
5. Upload the project's hero image.
6. Set CTA to "Learn more" with project URL.
7. Click **"Post"** / **"Publish"**.
8. **Important**: The post form is inside an iframe within the Google Search page. Use `page.frames().find(f => f.url().includes('/local/business/'))` to access it, same as the edit profile flow.
9. **Caption length**: 1500 chars. Keep it under 300 for best engagement — Google truncates with "Read more" after ~100 chars on mobile.
10. **Post types**: "Update" is the default and best for project showcases. "Offer" is for promotions with dates. "Event" is for events.

### YouTube Shorts

URL: `https://studio.youtube.com/`

1. Click the "Upload videos" / `+` icon in the top right.
2. In the upload dialog, click `Select files` → upload. YouTube auto-detects vertical videos as Shorts.
3. **Title field**: faceplate-textarea-input (web component with shadow root). `execCommand insertText` works fine here (unlike TikTok). Set title via:
   ```js
   const t = document.querySelector('[aria-label="Add a title that describes your video (type @ to mention a channel)"]');
   t.focus(); document.execCommand('selectAll', false, null); document.execCommand('insertText', false, 'TITLE');
   ```
4. **Description field**: same pattern, `aria-label="Tell viewers about your video..."`.
5. **"Made for kids" radio is required** — click "No, it's not made for kids". The radio button name is `VIDEO_MADE_FOR_KIDS_NOT_MFK` (NOT `NOT_MADE_FOR_KIDS`). Click via mouse at its coordinates — `.click()` via evaluate may not register. The Next button stays disabled until this radio is properly selected.
6. **"Altered content" notification** may appear — click `Close`.
7. Click `Next` 3 times to advance through Details → Video elements → Checks → Visibility tabs.
8. On Visibility tab, click the `Public` radio.
9. Click `Publish`. Confirmation dialog appears with "Video published" and the public URL `https://youtube.com/shorts/<id>`.
10. **Title length**: 100 chars. **Description length**: 5000 chars.

### Xiaohongshu / Rednote (video) ⚠️ PAUSED — platform warning received 2026-04-09

**Do NOT auto-post to Xiaohongshu until the user explicitly re-enables it.** The account received a platform warning, likely related to automated posting patterns. Keep this recipe for manual reference only.

URL: `https://creator.xiaohongshu.com/publish/publish?source=&published=true`

1. Click anywhere on the upload zone or trigger the file input via:
   `document.querySelector('input[type="file"]').click()` (Xiaohongshu has just one file input on the page).
2. Upload. Video is auto-processed, no explicit "next" steps.
3. **Title field**: standard `<input>` with placeholder `填写标题会有更多赞哦`. ⚠️ **HARD MAX 20 CHARACTERS** (counts CJK chars). The error toast `标题最多输入20字哦~` appears if you exceed this. Use `playwright.evaluate` to set the value via the React setter, then dispatch an `input` event:
   ```js
   const t = document.querySelector('input[placeholder*="标题"]');
   const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
   setter.call(t, 'TITLE'); t.dispatchEvent(new Event('input', { bubbles: true }));
   ```
4. **Body field**: contenteditable, max 1000 chars. `keyboard.type` and `execCommand insertText` both work.
5. ⚠️⚠️ **HARD RULE — NO contact info ever** (reinforced by the user 2026-04-08, "otherwise we will get banned"):
   - **NO phone numbers** (any format — `778-960-7999`, `7789607999`, `+1 778 960...`, etc.)
   - **NO website URLs** (`reno-stars.com`, any subdomain, any link)
   - **NO street addresses** (`Unit 188-21300 Gordon Way`, etc.)
   - **NO email addresses**
   - **NO WeChat IDs / external messaging handles**
   - **NO QR codes**
   - **NO "DM for quote" / "Visit our site" / "Call us" type CTAs**
   - **OK to keep**: city/neighborhood names for project context (Delta, Vancouver, Burnaby) — these are project metadata, not contact channels. Brand name (Reno Stars) is also OK.
   - **Verify before publishing**: search the draft for `778`, `reno-stars.com`, `Gordon Way`, `@`, `tel:`, `http`, and any digit-heavy strings. If matched, remove.
   - **Why this rule is strict**: Xiaohongshu/Rednote aggressively bans accounts that include external promotional content. Every other Reno Stars platform (FB/IG/X/LinkedIn/TikTok/YouTube) allows phone + URL — Xiaohongshu is the only one with this prohibition. **Strip contact lines from the FB/IG caption template before adapting it for Xiaohongshu.**
6. **All copy must be Chinese.** No English mixed in beyond standard brand names and price ranges.
7. Click 发布 (Publish) when enabled.
8. **Success signal**: URL changes to `https://creator.xiaohongshu.com/publish/success...` and the page shows `发布成功`.

### Xiaohongshu — editing or deleting a published post

If you posted with contact info that needs removing:
1. Navigate to `https://creator.xiaohongshu.com/new/note-manager`
2. Find the row for the offending post (most recent at top)
3. Click 编辑 (Edit) — opens `https://creator.xiaohongshu.com/publish/update?id=<note_id>&noteType=video`
4. Edit the title via React-setter pattern, edit body via keyboard.type or insertText
5. Click 发布/保存 (Publish/Save) — note this re-publishes; the original post URL stays the same
6. ⚠️ **Beforeunload dialog** ("Leave site? Changes you may not be saved") fires when navigating away from the edit page with unsaved changes. Either save first OR set up a `page.on('dialog', d => d.accept())` listener BEFORE the navigation.

### Reddit ⚠️ PAUSED until 2026-04-21

The Reno Stars Reddit account `u/Anxious-Owl-9826` was deleted on 2026-04-07 after a fresh-account shadow ban. **Skip Reddit entirely until the new account is created.** A launchd reminder fires on 2026-04-21 at 9 AM.

When the new account exists, the safe re-entry sequence is:
1. Wait 48h after account creation before posting anything.
2. First week: comment-only, 1 helpful comment per day, no links, no Reno Stars mention.
3. After ~1 week of organic activity: attempt the first profile media post.
4. New account username should look human (e.g. `RenoStarsVan`, `RenoStarsRenovation`) — NOT auto-generated like `Anxious-Owl-9826`.

**Reddit-specific failure modes to recognize on a banned/fresh account** (don't waste time troubleshooting these — the account is the problem):
- New Reddit submit: "Hmm, that community doesn't exist. Try checking the spelling." (when posting to your own profile)
- New Reddit settings save: "We had some issues saving your changes. Please try again." + console "No profile ID for profile settings page"
- Old Reddit settings save: HTTP 500 from `/api/site_admin`
- Old Reddit submit: aggressive reCAPTCHA wall

**Reddit comment rate limit**: even on a healthy account, posting 4+ comments back-to-back triggers `Rate limit exceeded. Please wait <N> seconds and try again` — typically 9–10 minutes cooldown. Space comment publishes 60–90 seconds apart for a healthy reputation.

---

## Telegram approval flow (for crons that draft → approve → publish)

The `social-media-engage` and `social-media-poster` crons use a Telegram approval pattern:

1. Cron drafts content → writes to `pending-replies.json` / `pending-posts.json` with `status: "pending_approval"`.
2. Cron sends a Telegram message ending in: `Reply: REPLY [id] to approve or REPLY ALL to approve everything above`.
3. User replies in Telegram with `REPLY <id>` or `REPLY ALL`.
4. Next cron run reads new Telegram messages, finds approvals, sets matching items to `status: "approved"`.
5. PHASE 1 of next run publishes everything `approved`, sets to `published`.

⚠️ **When you receive a short ambiguous Telegram message** like "Reply all", "approve", "yes", "do it" — **ALWAYS check `~/.openclaw/workspace/social/pending-replies.json` and the most recent log in `~/reno-star-business-intelligent/data/cron-logs/` first** before asking the user "reply to what?". The Telegram Bot API has no message history — the cron's outbound message lives only on disk in the logs. Reading those is faster than asking.

---

## Failure modes worth memorizing

| Symptom | Cause | Fix |
|---|---|---|
| TikTok "Something went wrong / Retry" after typing description | `execCommand insertText` broke React reconciler in Lexical editor | Use `keyboard.type` typing only on TikTok |
| TikTok caption defaults to filename after posting | Lexical editor pre-fills with filename, `Cmd+A` doesn't select all | Use **Backspace hammer** (loop `keyboard.press('Backspace')` for `length+5` iters) to clear before typing |
| TikTok caption needs editing AFTER post | n/a | Navigate to `tiktok.com/tiktokstudio/upload/post/<id>?from=creator_center` (Edit page). Click leftmost icon (x≈1078) in row to find video id. |
| TikTok "Leave site? Changes you may not be saved" blocks navigation | Native `beforeunload` listener | Set `window.onbeforeunload = null` AND handle the dialog with accept=true |
| X "Post" button click times out | Invisible overlay intercepts pointer events | Click via `[data-testid="tweetButton"].click()` in evaluate |
| Instagram "Sharing" dialog hangs | Reel processing — not actually hung | Wait ~10s, dialog closes itself |
| Instagram caption newlines stripped | `execCommand insertText` collapses newlines in IG editor | Acceptable trade — IG users skim past line breaks anyway |
| Xiaohongshu `标题最多输入20字哦~` toast | Title > 20 chars (CJK-counted) | Shorten title; max 20 chars hard |
| File upload `File access denied: ... is outside allowed roots` | Path not under `/Users/renostars` | Copy file to `/Users/renostars/<name>` first |
| Reddit "community doesn't exist" on profile post | New-account or shadow-banned | Wait 48h or use a different account |
| Reddit reCAPTCHA on submit | Ditto | Same |
| Facebook "Photo/video" upload fails on long video | Wrong upload path for video content | Use the legacy page composer at `facebook.com/profile.php?id=<page_id>` directly |
| Facebook caption truncated after typing | `keyboard.type` interrupted by React re-render of the editor | Capture the editor handle FRESH after upload preview appears, click into it explicitly, type with `delay: 5`. Fall back: type the URL/phone line first (more important) |
| Meta Business Suite Composer "Add video" button does nothing | Modern File System Access API — not interceptable | Skip Business Suite. Use facebook.com page composer + instagram.com directly. |
| LinkedIn personal feed Video click does nothing (no file dialog) | Stale background button covered by modal overlay OR FSA API | Use **company admin** path (`/company/<id>/admin/dashboard/` → Create → Start a post → "Add media") which uses the legacy file picker |
| LinkedIn "Add a video" aria-label finds wrong button | Personal feed share box has stale button at viewport (424,164) covered by modal | Filter selectors to inside the open modal — find via "What do you want to talk about" text anchor first |
| LinkedIn modal closes between Bash invocations | Disconnecting puppeteer ends the browser context for the modal | Run the entire LinkedIn flow in ONE Node script — connect once, do everything, disconnect at the end |
| Puppeteer screenshot shows modal but DOM says no modal | Screenshot is stale/cached (byte-identical to previous) | `md5 /tmp/*.png` to detect — trust DOM queries, not screenshots |
| Playwright MCP `tabs list` hangs forever | The MCP wrapper at `~/.openclaw/playwright-mcp-wrapper.js` is broken | Bypass MCP entirely. Use `puppeteer-core` directly via Bash + Node. |

---

## Cleaning up after a session

After publishing, the temp video/image files should be removed from `/Users/renostars/`:
```bash
rm -f /Users/renostars/burnaby-bathroom-before-after.mp4 /Users/renostars/reno-stars-avatar.png /Users/renostars/reno-stars-banner.png
```
(Adjust filenames; check `ls /Users/renostars/*.mp4 /Users/renostars/*.png 2>/dev/null` first.)
