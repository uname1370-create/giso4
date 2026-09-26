# Graph Report - beauty-preview  (2026-09-26)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 584 nodes · 1070 edges · 20 communities (17 shown, 3 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS · INFERRED: 2 edges (avg confidence: 0.82)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- db.ts
- app/page.tsx
- cloudflare.ts
- next
- package.json
- site-images.ts
- PreviewStep.tsx
- brow-shapes.ts
- test-chain.mjs
- generate/route.ts
- stats.ts
- consult/route.ts
- compilerOptions
- analysis.ts
- mock-providers.mjs
- ConsultStep.tsx
- jev-quality.ts
- next.config.mjs
- postcss.config.mjs
- vision.ts

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
10. `PlanTier` - 8 edges

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

## Communities (20 total, 3 thin omitted)

### Community 0 - "db.ts"
Cohesion: 0.05
Nodes (63): dynamic, GET(), runtime, DELETE(), dynamic, PATCH(), RouteContext, runtime (+55 more)

### Community 1 - "app/page.tsx"
Cohesion: 0.05
Nodes (57): dynamic, POST(), runtime, SERVICES_SUMMARY, BookingFormData, ClientPreferences, GenerationStatus, MedicalSafetyCheck (+49 more)

### Community 2 - "cloudflare.ts"
Cohesion: 0.07
Nodes (37): configuredList(), demoActive(), dynamic, GET(), maxDuration, ProviderStatus, runtime, openai (+29 more)

### Community 3 - "next"
Cohesion: 0.07
Nodes (34): AdminDashboardPage(), Banner, ChatLogRecord, LeadRecord, StatCard(), StatEvent, StatsResponse, TabKey (+26 more)

### Community 4 - "package.json"
Cohesion: 0.05
Nodes (42): dependencies, better-sqlite3, @mediapipe/tasks-vision, next, openai, react, react-compare-slider, react-dom (+34 more)

### Community 5 - "site-images.ts"
Cohesion: 0.08
Nodes (32): DELETE(), dynamic, POST(), runtime, DELETE(), dynamic, POST(), runtime (+24 more)

### Community 6 - "PreviewStep.tsx"
Cohesion: 0.10
Nodes (31): @mediapipe/tasks-vision, PreviewStep(), runClientVision(), applyPhotorealisticHardComposite(), CompositeOptions, createDualStageFeatheredMask(), drawPolygon(), executeClientComposite() (+23 more)

### Community 7 - "brow-shapes.ts"
Cohesion: 0.10
Nodes (33): HomePage(), BOTTOM_SEGMENTS, bottomEdgeAt(), BROW_VIEWBOX, BrowMarkupOptions, browOutlinePath(), browPreviewUri(), BrowSvgOptions (+25 more)

### Community 8 - "test-chain.mjs"
Cohesion: 0.08
Nodes (28): ref_node_child_process, ref_node_os, ref_node_url, appRoot, check(), children, here, IMAGE_ARTIFACTS (+20 more)

### Community 9 - "generate/route.ts"
Cohesion: 0.10
Nodes (28): badRequest(), DemoMode, dynamic, GenerateBody, GenerateFailure, GenerateService, GenerateSuccess, GET() (+20 more)

### Community 10 - "stats.ts"
Cohesion: 0.13
Nodes (23): dynamic, GET(), runtime, trackPreview(), clientIp(), dynamic, lastVisitByIp, POST() (+15 more)

### Community 11 - "consult/route.ts"
Cohesion: 0.17
Nodes (22): buildDemoPrescription(), buildUserText(), callCloudflareVision(), callPollinationsVision(), cloudflareAccount(), CONSULT_TIMEOUT_MS, ConsultAttempt, ConsultBody (+14 more)

### Community 12 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowJs, baseUrl, esModuleInterop, incremental, isolatedModules, jsx, lib (+11 more)

### Community 13 - "analysis.ts"
Cohesion: 0.21
Nodes (12): dynamic, POST(), runtime, analyzeBeautyPhoto(), BASE_IMMUTABLE, BeautyPhotoAnalysis, BrowSideProfile, buildCustomerBrowProfile() (+4 more)

### Community 14 - "mock-providers.mjs"
Cohesion: 0.31
Nodes (9): ref_node_http, currentMode(), json(), logCalls(), ORDER, PORT, report, server (+1 more)

### Community 15 - "ConsultStep.tsx"
Cohesion: 0.20
Nodes (8): ConsultOption, ConsultPrescription, ConsultStepProps, FACE_SHAPE_FA, FITZPATRICK_FA, OPTION_META, Status, UNDERTONE_FA

### Community 16 - "jev-quality.ts"
Cohesion: 0.31
Nodes (8): creds(), evaluateBeautyPreviewInput(), FeatureLandmarks, finite(), JevBeautyDecision, Point, targetGeometry(), VisionAnalysis

## Knowledge Gaps
- **231 isolated node(s):** `RouteContext`, `ChatLogRecord`, `LeadRecord`, `BookingFormData`, `ClientPreferences` (+226 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 258 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `next` connect `next` to `db.ts`, `app/page.tsx`, `cloudflare.ts`, `package.json`, `site-images.ts`, `generate/route.ts`, `stats.ts`, `consult/route.ts`, `analysis.ts`?**
  _High betweenness centrality (0.321) - this node is a cross-community bridge._
- **Why does `react` connect `app/page.tsx` to `next`, `package.json`, `PreviewStep.tsx`, `ConsultStep.tsx`?**
  _High betweenness centrality (0.073) - this node is a cross-community bridge._
- **What connects `RouteContext`, `ChatLogRecord`, `LeadRecord` to the rest of the system?**
  _231 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `db.ts` be split into smaller, more focused modules?**
  _Cohesion score 0.05368421052631579 - nodes in this community are weakly interconnected._
- **Should `app/page.tsx` be split into smaller, more focused modules?**
  _Cohesion score 0.05311871227364185 - nodes in this community are weakly interconnected._
- **Should `cloudflare.ts` be split into smaller, more focused modules?**
  _Cohesion score 0.07197763801537387 - nodes in this community are weakly interconnected._
- **Should `next` be split into smaller, more focused modules?**
  _Cohesion score 0.06567992599444958 - nodes in this community are weakly interconnected._