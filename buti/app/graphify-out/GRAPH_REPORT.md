# Graph Report - beauty-preview  (2026-09-27)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 541 nodes · 1004 edges · 26 communities (23 shown, 3 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS · INFERRED: 2 edges (avg confidence: 0.82)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- db.ts
- cloudflare.ts
- package.json
- dashboard/page.tsx
- brow-shapes.ts
- generate/route.ts
- PreviewStep.tsx
- options.ts
- consult/route.ts
- stats.ts
- site-images.ts
- compilerOptions
- test-chain.mjs
- app/page.tsx
- test-admin.mjs
- BookingStep.tsx
- services-content.ts
- ref_node_fs
- mock-providers.mjs
- ConsultStep.tsx
- appointments/route.ts
- app/layout.tsx
- AiChatWidget.tsx
- SafetyCheckStep.tsx
- next.config.mjs
- postcss.config.mjs

## God Nodes (most connected - your core abstractions)
1. `next` - 26 edges
2. `isAuthorized()` - 21 edges
3. `unauthorizedResponse()` - 18 edges
4. `compilerOptions` - 17 edges
5. `react` - 14 edges
6. `ServiceInfo` - 13 edges
7. `getDb()` - 11 edges
8. `POST()` - 11 edges
9. `TechniqueStyleOption` - 9 edges
10. `ProviderError` - 8 edges

## Surprising Connections (you probably didn't know these)
- `GenerateFailure` --references--> `AttemptLog`  [EXTRACTED]
  app/api/generate/route.ts → src/providers/types.ts
- `GenerateSuccess` --references--> `AttemptLog`  [EXTRACTED]
  app/api/generate/route.ts → src/providers/types.ts
- `GET()` --calls--> `StatsSummary`  [EXTRACTED]
  app/api/admin/stats/route.ts → src/stats.ts
- `POST()` --calls--> `parseDataUri()`  [EXTRACTED]
  app/api/generate/route.ts → src/providers/http.ts
- `POST()` --calls--> `generateWithFallback()`  [EXTRACTED]
  app/api/generate/route.ts → src/providers/index.ts

## Import Cycles
- None detected.

## Communities (26 total, 3 thin omitted)

### Community 0 - "db.ts"
Cohesion: 0.06
Nodes (63): metadata, dynamic, GET(), runtime, DELETE(), dynamic, PATCH(), RouteContext (+55 more)

### Community 1 - "cloudflare.ts"
Cohesion: 0.07
Nodes (37): configuredList(), demoActive(), dynamic, GET(), maxDuration, ProviderStatus, runtime, CloudflareAccount (+29 more)

### Community 2 - "package.json"
Cohesion: 0.05
Nodes (42): dependencies, better-sqlite3, @mediapipe/tasks-vision, next, openai, react, react-compare-slider, react-dom (+34 more)

### Community 3 - "dashboard/page.tsx"
Cohesion: 0.10
Nodes (26): AdminDashboardPage(), Banner, ChatLogRecord, LeadRecord, StatCard(), StatEvent, StatsResponse, TabKey (+18 more)

### Community 4 - "brow-shapes.ts"
Cohesion: 0.10
Nodes (33): HomePage(), BOTTOM_SEGMENTS, bottomEdgeAt(), BROW_VIEWBOX, BrowMarkupOptions, browOutlinePath(), browPreviewUri(), BrowSvgOptions (+25 more)

### Community 5 - "generate/route.ts"
Cohesion: 0.10
Nodes (28): badRequest(), DemoMode, dynamic, GenerateBody, GenerateFailure, GenerateService, GenerateSuccess, GET() (+20 more)

### Community 6 - "PreviewStep.tsx"
Cohesion: 0.15
Nodes (22): @mediapipe/tasks-vision, PreviewStep(), runClientVision(), applyPhotorealisticHardComposite(), CompositeOptions, createDualStageFeatheredMask(), drawPolygon(), executeClientComposite() (+14 more)

### Community 7 - "options.ts"
Cohesion: 0.11
Nodes (21): BrowStyleKey, BookingStep(), HeroStep(), HeroStepProps, ACCEPTED_MIME_TYPES, BROW_COLORS, BrowColor, buildEnglishPrompt() (+13 more)

### Community 8 - "consult/route.ts"
Cohesion: 0.16
Nodes (21): buildDemoPrescription(), buildUserText(), callCloudflareVision(), callPollinationsVision(), cloudflareAccount(), CONSULT_TIMEOUT_MS, ConsultAttempt, ConsultBody (+13 more)

### Community 9 - "stats.ts"
Cohesion: 0.15
Nodes (20): trackPreview(), clientIp(), dynamic, lastVisitByIp, POST(), prune(), runtime, emptyStats() (+12 more)

### Community 10 - "site-images.ts"
Cohesion: 0.11
Nodes (18): dynamic, GET(), runtime, BROW_IMAGE_FOLDER, HERO_IMAGE_BASENAME, HERO_IMAGE_FOLDER, BROW_TARGETS, BrowTarget (+10 more)

### Community 11 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowJs, baseUrl, esModuleInterop, incremental, isolatedModules, jsx, lib (+11 more)

### Community 12 - "test-chain.mjs"
Cohesion: 0.15
Nodes (17): ref_node_os, APP_PORT, appRoot, backupTsconfig(), callGenerate(), CASES, children, cleanupTestArtifacts() (+9 more)

### Community 13 - "app/page.tsx"
Cohesion: 0.15
Nodes (14): BookingFormData, ClientPreferences, GenerationStatus, MedicalSafetyCheck, ServiceType, WIZARD_STEPS, WizardStep, react (+6 more)

### Community 14 - "test-admin.mjs"
Cohesion: 0.16
Nodes (11): ref_node_child_process, ref_node_url, appRoot, check(), children, here, IMAGE_ARTIFACTS, main() (+3 more)

### Community 15 - "BookingStep.tsx"
Cohesion: 0.26
Nodes (10): BookingFormData, BookingStepProps, ClientPreferences, PreferencesStepProps, PreviewStepProps, PLAN_CONFIGS, PlanConfig, PlanTier (+2 more)

### Community 16 - "services-content.ts"
Cohesion: 0.19
Nodes (10): dynamic, POST(), runtime, SERVICES_SUMMARY, openai, ServiceSelectStep(), ServiceSelectStepProps, ServiceType (+2 more)

### Community 17 - "ref_node_fs"
Cohesion: 0.20
Nodes (7): better-sqlite3, ref_node_fs, ref_node_path, DB_PATH, b64, fs, started

### Community 18 - "mock-providers.mjs"
Cohesion: 0.31
Nodes (9): ref_node_http, currentMode(), json(), logCalls(), ORDER, PORT, report, server (+1 more)

### Community 19 - "ConsultStep.tsx"
Cohesion: 0.20
Nodes (8): ConsultOption, ConsultPrescription, ConsultStepProps, FACE_SHAPE_FA, FITZPATRICK_FA, OPTION_META, Status, UNDERTONE_FA

### Community 20 - "appointments/route.ts"
Cohesion: 0.36
Nodes (6): dynamic, POST(), runtime, ref_node_crypto, saveLead(), saveLeadImage()

### Community 21 - "app/layout.tsx"
Cohesion: 0.33
Nodes (4): app_globals, metadata, vazirmatn, viewport

### Community 22 - "AiChatWidget.tsx"
Cohesion: 0.40
Nodes (5): AiChatWidget(), AiChatWidgetProps, ChatMessage, buildHeroWhatsAppLink(), HERO_IMAGE_URL

## Knowledge Gaps
- **219 isolated node(s):** `RouteContext`, `ChatLogRecord`, `LeadRecord`, `ProviderStatus`, `CloudflareAccount` (+214 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 245 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `next` connect `db.ts` to `cloudflare.ts`, `package.json`, `dashboard/page.tsx`, `generate/route.ts`, `options.ts`, `consult/route.ts`, `stats.ts`, `site-images.ts`, `services-content.ts`, `appointments/route.ts`, `app/layout.tsx`, `AiChatWidget.tsx`, `SafetyCheckStep.tsx`?**
  _High betweenness centrality (0.316) - this node is a cross-community bridge._
- **Why does `react` connect `app/page.tsx` to `package.json`, `dashboard/page.tsx`, `PreviewStep.tsx`, `options.ts`, `BookingStep.tsx`, `services-content.ts`, `ConsultStep.tsx`, `AiChatWidget.tsx`, `SafetyCheckStep.tsx`?**
  _High betweenness centrality (0.081) - this node is a cross-community bridge._
- **What connects `RouteContext`, `ChatLogRecord`, `LeadRecord` to the rest of the system?**
  _219 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `db.ts` be split into smaller, more focused modules?**
  _Cohesion score 0.05837837837837838 - nodes in this community are weakly interconnected._
- **Should `cloudflare.ts` be split into smaller, more focused modules?**
  _Cohesion score 0.07477288609364081 - nodes in this community are weakly interconnected._
- **Should `package.json` be split into smaller, more focused modules?**
  _Cohesion score 0.045454545454545456 - nodes in this community are weakly interconnected._
- **Should `dashboard/page.tsx` be split into smaller, more focused modules?**
  _Cohesion score 0.0962566844919786 - nodes in this community are weakly interconnected._