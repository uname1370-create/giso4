# 📋 Product Requirements Document (PRD)
# Beauty Preview Platform - Asal Rajabi PMU (VIP & Luxury)

## 📌 Context & Tech Stack
- **Brand:** Asal Rajabi PMU (Located in Mashhad, Iran)
- **Slogan:** "تو زیبایی؛ من فقط کشفش می‌کنم ✨" (You are beautiful; I just discover it).
- **Vibe/UI:** Ultra-luxury, VIP, Dark mode with Emerald Green/Gold accents, Minimalist.
- **Tech Stack:** 
  1. Frontend & Orchestration: Next.js 14, TypeScript, Tailwind CSS.
  2. Vision Safety & Processing: Python, FastAPI, OpenCV, MediaPipe (Located in `vision-engine/`).
  3. AI Image Gen: Cloudflare FLUX.2 Klein 4B (via `src/providers/`).

## ⚠️ Strict Rules for AI Agent (MUST READ)
1. **Step-by-Step Execution:** Do NOT execute multiple phases at once. You must complete ONE phase, output a summary report, and STOP. Wait for human approval before moving to the next phase.
2. **Preserve Vision Safety:** The "Hard Composite" logic in Python (where pixels outside the edit mask are restored from the original image) is a core safety feature. NEVER bypass or remove it.
3. **No Medical Claims:** The AI must never guarantee medical results, especially for PMU Removal.
4. **Update File:** After completing and getting approval for a phase, check the box `- [x]` in this file.

---

## 🚀 PHASE 1: Wizard UI Flow for Eyebrows (The Core Experience)
**Goal:** Convert the current single-page form in `app/page.tsx` into a 6-step React Wizard.

- [ ] **Step 0 (Hero Section):**
  - Display the luxury hero image (use a placeholder if needed, but structure it for Admin upload).
  - Show the brand slogan.
  - Show a primary Gold CTA Button: "🪄 شروع مشاوره و پیش‌نمایش هوشمند".
- [ ] **Step 1 (Upload):**
  - Show a clean upload box for the face photo.
  - Include educational helper text (e.g., "رو به نور پنجره، بدون فیلتر و عینک").
- [ ] **Step 2 (Safety Check - Modal/Form):**
  - Ask 3 mandatory Checkbox questions: 1. بارداری/شیردهی؟ 2. حساسیت پوستی/کلوئید؟ 3. مصرف داروی خاص (راکوتان و...)؟
  - *Logic:* If ANY checkbox is "Yes", disable the "Next" button and show a warning: "لطفاً پیش از انجام کار با پزشک خود مشورت کنید و جهت راهنمایی با ما تماس بگیرید."
- [ ] **Step 3 (Subjective Questions):**
  - Ask 3 styling questions using elegant radio buttons:
    1. سبک آرایش روزانه؟ (نچرال / ملایم / پررنگ)
    2. فرم ابروی دلخواه؟ (طبیعی / کادردار)
    3. تراکم دلخواه؟ (کرکی / متراکم)
  - Save these answers in the React State.
- [ ] **Step 4 (Preview Generation):**
  - Show a "Generate Preview" button. Trigger `POST /api/generate`.
  - Display the result using the existing `react-compare-slider` (Before/After).
- [ ] **Step 5 (Booking Lead):**
  - After preview, show a simple form: Name, Phone Number, Instagram ID (Optional).
  - Add a "Submit Booking Request" button (For now, just `console.log` the data or send to a mock API endpoint until Phase 4).

---

## 🚀 PHASE 2: Educational Quality Gate (`src/analysis.ts`)
**Goal:** Do not strictly reject photos, but educate the user if the photo is bad.

- [ ] Update `analyzeBeautyPhoto`:
  - If lighting (luminance) is too low or blur is detected, DO NOT throw an error that stops the flow.
  - Instead, return a `warningMessage` (e.g., "نور عکس کمی پایینه، برای نتیجه بهتر می‌تونی یه عکس رو به نور بگیری!").
  - Display this warning gracefully in Step 1 (Upload UI).
- [ ] Pass facial characteristics (face shape, skin tone) to Step 3 so the UI can say: "فرم صورت شما تحلیل شد...".

---

## 🚀 PHASE 3: Dynamic Prompt Injection (`src/style-dna.ts`)
**Goal:** Make the AI respect the user's subjective answers from Step 3.

- [ ] Update `POST /api/generate` to accept the 3 subjective answers from the frontend.
- [ ] Update `buildEnglishPrompt` or `styleDesignSpec` in `src/style-dna.ts`:
  - If user chose "پررنگ" (Heavy Makeup), add keywords like `defined arch, dense pigment`.
  - If user chose "نچرال" (Natural), add `sparse front, very soft strokes, no harsh lines`.
- [ ] Test the integration with Cloudflare FLUX to ensure prompts are dynamically updated.

---

## 🚀 PHASE 4: Booking & Lead Capture System
**Goal:** Save the data from Step 5 permanently.

- [ ] Create `POST /api/appointments` endpoint.
- [ ] Accept payload: Customer info, selected style, base64/URL of the original photo, and base64/URL of the AI preview.
- [ ] For now, securely save this to `data/leads.json` (as a bridge to Phase 5).

---

## 🚀 PHASE 5: Database Integration (CRM)
**Goal:** Move away from JSON to a real relational database (PostgreSQL/Supabase).

- [ ] Setup Prisma or Drizzle ORM.
- [ ] Create schemas: `Customer`, `SimulationSession`, `Appointment`.
- [ ] Ensure photos are stored securely (e.g., S3 or local secure folder with 24-hour expiration policy for privacy).

---

## 🚀 PHASE 6: Expansion to New Services
**Goal:** Add Lip Shading, Eyeliner, and Removal to the platform.

- [ ] Add Service Selector at Step 0.5 (Before Upload): Choose Brows, Lips, Eyes, or Removal.
- [ ] Python Vision Engine Updates:
  - Add lip contour masking (`vision-engine/face/lips.py`).
  - Add eyeliner/eye masking.
- [ ] Next.js Updates: Add specific styles and questions for Lips and Eyes.
- [ ] *Special Rule for Removal:* Removal flow does NOT generate an AI image. It only analyzes the old tattoo and routes the user directly to the booking/human consultation step.

---

## 🚀 PHASE 7: AI Chat Assistant (Widget)
**Goal:** A smart AI widget to talk to customers globally on the site.

- [ ] Add a floating Chat Widget UI.
- [ ] Connect to OpenAI SDK (`src/providers/http.ts`).
- [ ] Inject System Prompt: "You are Asal Rajabi's assistant. Tone: warm, feminine, professional. Do not guarantee medical results. Do not give final pricing."

---

## 🚀 PHASE 8: Admin Dashboard Upgrade
**Goal:** Let the clinic manager control the system.

- [ ] Build CRM View: List of leads, phone numbers, and download buttons for Before/After photos.
- [ ] Reference Manager: UI to upload/replace reference photos for each technique.
- [ ] Global toggle to Enable/Disable the AI Assistant.
