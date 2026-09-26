# Graph Report - beauty-preview  (2026-09-26)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 582 nodes · 1068 edges · 27 communities (24 shown, 3 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS · INFERRED: 2 edges (avg confidence: 0.82)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- db.ts
- cloudflare.ts
- app/page.tsx
- package.json
- PreviewStep.tsx
- brow-shapes.ts
- test-chain.mjs
- generate/route.ts
- dashboard/page.tsx
- stats.ts
- consult/route.ts
- options.ts
- compilerOptions
- site-images.ts
- admin-auth.ts
- analysis.ts
- mock-providers.mjs
- ConsultStep.tsx
- jev-quality.ts
- next
- upload-brow/route.ts
- [...path]/route.ts
- app/layout.tsx
- AiChatWidget.tsx
- vision.ts
- next.config.mjs
- postcss.config.mjs

## God Nodes (most connected - your core abstractions)
1. `next` - 28 edges
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
- `GET()` --calls--> `getTenantSettings()`  [EXTRACTED]
  app/api/admin/tenant/route.ts → src/db.ts
- `PATCH()` --calls--> `updateTenantSettings()`  [EXTRACTED]
  app/api/admin/tenant/route.ts → src/db.ts
- `GET()` --calls--> `isAuthorized()`  [EXTRACTED]
  app/api/admin/stats/route.ts → src/admin-auth.ts

## Import Cycles
- None detected.

## Communities (27 total, 3 thin omitted)

### Community 0 - "db.ts"
Cohesion: 0.06
Nodes (50): dynamic, GET(), runtime, DELETE(), dynamic, PATCH(), RouteContext, runtime (+42 more)

### Community 1 - "cloudflare.ts"
Cohesion: 0.07
Nodes (39): GenerateFailure, GenerateSuccess, configuredList(), demoActive(), dynamic, GET(), maxDuration, ProviderStatus (+31 more)

### Community 2 - "app/page.tsx"
Cohesion: 0.07
Nodes (42): dynamic, POST(), runtime, SERVICES_SUMMARY, BookingFormData, ClientPreferences, GenerationStatus, MedicalSafetyCheck (+34 more)

### Community 3 - "package.json"
Cohesion: 0.05
Nodes (42): dependencies, better-sqlite3, @mediapipe/tasks-vision, next, openai, react, react-compare-slider, react-dom (+34 more)

### Community 4 - "PreviewStep.tsx"
Cohesion: 0.10
Nodes (31): @mediapipe/tasks-vision, PreviewStep(), runClientVision(), applyPhotorealisticHardComposite(), CompositeOptions, createDualStageFeatheredMask(), drawPolygon(), executeClientComposite() (+23 more)

### Community 5 - "brow-shapes.ts"
Cohesion: 0.10
Nodes (33): HomePage(), BOTTOM_SEGMENTS, bottomEdgeAt(), BROW_VIEWBOX, BrowMarkupOptions, browOutlinePath(), browPreviewUri(), BrowSvgOptions (+25 more)

### Community 6 - "test-chain.mjs"
Cohesion: 0.08
Nodes (28): ref_node_child_process, ref_node_os, ref_node_url, appRoot, check(), children, here, IMAGE_ARTIFACTS (+20 more)

### Community 7 - "generate/route.ts"
Cohesion: 0.11
Nodes (26): badRequest(), DemoMode, dynamic, GenerateBody, GenerateService, GET(), isDemoActive(), maxDuration (+18 more)

### Community 8 - "dashboard/page.tsx"
Cohesion: 0.12
Nodes (21): AdminDashboardPage(), Banner, ChatLogRecord, LeadRecord, StatCard(), StatEvent, StatsResponse, TabKey (+13 more)

### Community 9 - "stats.ts"
Cohesion: 0.13
Nodes (23): dynamic, GET(), runtime, trackPreview(), clientIp(), dynamic, lastVisitByIp, POST() (+15 more)

### Community 10 - "consult/route.ts"
Cohesion: 0.17
Nodes (22): buildDemoPrescription(), buildUserText(), callCloudflareVision(), callPollinationsVision(), cloudflareAccount(), CONSULT_TIMEOUT_MS, ConsultAttempt, ConsultBody (+14 more)

### Community 11 - "options.ts"
Cohesion: 0.12
Nodes (18): BrowStyleKey, HeroStep(), HeroStepProps, BROW_COLORS, BROW_IMAGE_FOLDER, BrowColor, EYEBROW_STYLES, EyebrowStyle (+10 more)

### Community 12 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowJs, baseUrl, esModuleInterop, incremental, isolatedModules, jsx, lib (+11 more)

### Community 13 - "site-images.ts"
Cohesion: 0.14
Nodes (15): dynamic, runtime, BrowTarget, deleteHeroImage(), detectImageExtension(), HERO_EXTENSIONS, HeroExtension, MAX_BROW_BYTES (+7 more)

### Community 14 - "admin-auth.ts"
Cohesion: 0.24
Nodes (15): clientIp(), dynamic, failedAttempts, isRateLimited(), POST(), registerFailure(), runtime, adminPassword() (+7 more)

### Community 15 - "analysis.ts"
Cohesion: 0.21
Nodes (12): dynamic, POST(), runtime, analyzeBeautyPhoto(), BASE_IMMUTABLE, BeautyPhotoAnalysis, BrowSideProfile, buildCustomerBrowProfile() (+4 more)

### Community 16 - "mock-providers.mjs"
Cohesion: 0.31
Nodes (9): ref_node_http, currentMode(), json(), logCalls(), ORDER, PORT, report, server (+1 more)

### Community 17 - "ConsultStep.tsx"
Cohesion: 0.20
Nodes (8): ConsultOption, ConsultPrescription, ConsultStepProps, FACE_SHAPE_FA, FITZPATRICK_FA, OPTION_META, Status, UNDERTONE_FA

### Community 18 - "jev-quality.ts"
Cohesion: 0.31
Nodes (8): creds(), evaluateBeautyPreviewInput(), FeatureLandmarks, finite(), JevBeautyDecision, Point, targetGeometry(), VisionAnalysis

### Community 19 - "next"
Cohesion: 0.32
Nodes (5): metadata, creds(), n(), POST(), next

### Community 20 - "upload-brow/route.ts"
Cohesion: 0.38
Nodes (6): DELETE(), dynamic, runtime, BROW_TARGETS, deleteBrowImage(), findBrowTarget()

### Community 21 - "[...path]/route.ts"
Cohesion: 0.40
Nodes (5): dynamic, GET(), runtime, readSiteImage(), resolveSiteImage()

### Community 22 - "app/layout.tsx"
Cohesion: 0.33
Nodes (4): app_globals, metadata, vazirmatn, viewport

### Community 23 - "AiChatWidget.tsx"
Cohesion: 0.40
Nodes (5): AiChatWidget(), AiChatWidgetProps, ChatMessage, buildHeroWhatsAppLink(), HERO_IMAGE_URL

## Knowledge Gaps
- **231 isolated node(s):** `RouteContext`, `ChatLogRecord`, `LeadRecord`, `ProviderStatus`, `CloudflareAccount` (+226 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 258 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `next` connect `next` to `db.ts`, `cloudflare.ts`, `app/page.tsx`, `package.json`, `generate/route.ts`, `dashboard/page.tsx`, `stats.ts`, `consult/route.ts`, `options.ts`, `site-images.ts`, `admin-auth.ts`, `analysis.ts`, `upload-brow/route.ts`, `[...path]/route.ts`, `app/layout.tsx`, `AiChatWidget.tsx`?**
  _High betweenness centrality (0.328) - this node is a cross-community bridge._
- **Why does `react` connect `app/page.tsx` to `package.json`, `PreviewStep.tsx`, `dashboard/page.tsx`, `options.ts`, `ConsultStep.tsx`, `AiChatWidget.tsx`?**
  _High betweenness centrality (0.073) - this node is a cross-community bridge._
- **What connects `RouteContext`, `ChatLogRecord`, `LeadRecord` to the rest of the system?**
  _231 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `db.ts` be split into smaller, more focused modules?**
  _Cohesion score 0.06284153005464481 - nodes in this community are weakly interconnected._
- **Should `cloudflare.ts` be split into smaller, more focused modules?**
  _Cohesion score 0.07077922077922078 - nodes in this community are weakly interconnected._
- **Should `app/page.tsx` be split into smaller, more focused modules?**
  _Cohesion score 0.06988120195667366 - nodes in this community are weakly interconnected._
- **Should `package.json` be split into smaller, more focused modules?**
  _Cohesion score 0.045454545454545456 - nodes in this community are weakly interconnected._