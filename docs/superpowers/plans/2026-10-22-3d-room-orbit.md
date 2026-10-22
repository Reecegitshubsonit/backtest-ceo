# 3D Room With Free Orbit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat picture room with a real 3D room you can spin around freely, where all 26 screens are clickable and stay sharp when you zoom in.

**Architecture:** One config (`screens3d.ts`) places all 26 screens in 3D. Pure camera math (`model/camera.ts`) computes the fly-in pose and the HTML scale. The panel reducer gets `focused` and `expanded` steps. `Screens.tsx` draws the screens. The focused screen hosts a live DOM preview through drei `<Html transform>`, and the same DOM node moves into the full-screen panel on expand, so state is kept.

**Tech Stack:** React 19, @react-three/fiber 9, @react-three/drei 10 (OrbitControls, Html), three 0.186, vitest, TypeScript.

**Spec:** `docs/superpowers/specs/2026-10-22-3d-room-orbit-design.md`

## Global Constraints

- Same screen ids and mapping: `s1`..`s17` wall (`s1` = backtests, `s5` = scanner, `s10` = strategies); `d-scanner`, `d-strategist`, `d-backtester`, `d-auditor`, `d-regime`, `d-risk`, `d7`, `d8`, `d9` table.
- Nothing drawn over a screen at rest; hover = glow + name.
- Orbit: full 360, slow auto-rotate while idle, no pan control (zoom-to-cursor allowed), camera stays inside the room and above the floor.
- Only the focused screen runs live HTML.
- Tests: `cd web3d && npx vitest run && npx tsc --noEmit`.

## File Structure

- Create `src/config/room.ts`: room and table dimensions (shared by config and scene, no three.js import).
- Create `src/config/screens3d.ts`: the 26 screens, `screenById`, `screenName`.
- Modify `src/model/camera.ts`: `screenNormal`, `flyDistance`, `flyPose`, `projectedWidthPx`, `htmlDistanceFactor`, `clampToRoom`; drop `screenPose`.
- Modify `src/model/panel.ts`: phases `closed | flying | focused | expanded | closing`, field `screen`.
- Create `src/panels/ScreenView.tsx`: header + body for any screen (shared by preview and full panel).
- Create `src/panels/Slot.tsx`: mounts a shared DOM node wherever it is rendered.
- Modify `src/panels/ComputerPanel.tsx`: the expanded overlay, hosts the slot.
- Create `src/scene/Screens.tsx`: 26 screen meshes, hover, click, focused HTML preview.
- Modify `src/scene/CameraRig.tsx`, `src/scene/Scene.tsx`, `src/App.tsx`.
- Modify `src/scene/Room.tsx`, `Table.tsx`, `AgentSeat.tsx`, `Ceo.tsx`, `Operator.tsx`, `labels.tsx`, `textures.ts`.
- Delete `src/room/` (ImageRoom, Sparkles), `src/config/imageRoom.ts`, `src/scene/ComputerWall.tsx`, `tests/imageRoom.test.ts`. Move `public/room.jpg` to `docs/reference/grok-room-clean.jpg`.

---

### Task 1: Screen layout config

**Files:**
- Create: `web3d/src/config/room.ts`, `web3d/src/config/screens3d.ts`
- Modify: `web3d/src/config/computers.ts` (drop geometry)
- Test: `web3d/tests/screens3d.test.ts`

**Interfaces:**
- Produces: `ROOM_R`, `WALL_SCREEN_R`, `TABLE_H`, `TABLE_R`, `SEAT_R`; `interface Screen3D { id; n; kind: 'wall'|'desk'; center: Vec3; yaw; pitch; w; h; computer?: ComputerId; seat?: string }`; `SCREENS: Screen3D[]`; `screenById(id): Screen3D | undefined`; `screenName(s): string`.

- [ ] **Step 1: Write the failing test** (`tests/screens3d.test.ts`)

```ts
import { describe, expect, it } from 'vitest'
import { SCREENS, screenById, screenName } from '../src/config/screens3d'
import { ROOM_R, TABLE_H, TABLE_R } from '../src/config/room'
import { SEATS } from '../src/config/seats'

const wall = SCREENS.filter(s => s.kind === 'wall'), desk = SCREENS.filter(s => s.kind === 'desk')
const flat = (v: number[]) => Math.hypot(v[0], v[2])

describe('3D screens', () => {
  it('has 17 numbered wall screens and 9 desk screens with unique ids', () => {
    expect(wall.map(s => s.n)).toEqual(Array.from({ length: 17 }, (_, i) => i + 1))
    expect(desk).toHaveLength(9)
    expect(new Set(SCREENS.map(s => s.id)).size).toBe(26)
  })
  it('keeps the computer and console mapping', () => {
    expect(screenById('s1')?.computer).toBe('backtests')
    expect(screenById('s5')?.computer).toBe('scanner')
    expect(screenById('s10')?.computer).toBe('strategies')
    for (const seat of SEATS) expect(screenById(`d-${seat.id}`)?.seat).toBe(seat.id)
  })
  it('wall screens sit inside the room, behind the CEO, facing the centre, without overlapping', () => {
    for (const s of wall) {
      expect(Math.hypot(flat(s.center), s.w / 2)).toBeLessThan(ROOM_R)
      expect(s.center[2]).toBeLessThan(0)
      expect(s.center[1] - s.h / 2).toBeGreaterThan(TABLE_H)
      expect(s.center[1] + s.h / 2).toBeLessThan(7.6)
      const n = [Math.sin(s.yaw), Math.cos(s.yaw)]
      expect(n[0] * s.center[0] + n[1] * s.center[2]).toBeLessThan(0)
    }
    const u = (s: typeof wall[0]) => Math.atan2(s.center[0], s.center[2]) * flat(s.center)
    for (const a of wall) for (const b of wall) {
      if (a === b) continue
      const apart = Math.abs(u(a) - u(b)) >= (a.w + b.w) / 2 - 1e-6 || Math.abs(a.center[1] - b.center[1]) >= (a.h + b.h) / 2 - 1e-6
      expect(apart, `${a.id} overlaps ${b.id}`).toBe(true)
    }
  })
  it('desk screens stand on the table, tilted back, without touching each other', () => {
    for (const s of desk) {
      expect(flat(s.center) + s.h / 2).toBeLessThan(TABLE_R)
      expect(s.center[1] - (s.h / 2) * Math.cos(s.pitch)).toBeGreaterThanOrEqual(TABLE_H)
      expect(s.pitch).toBeGreaterThan(0.3)
    }
    for (const a of desk) for (const b of desk) {
      if (a === b) continue
      const d = Math.hypot(a.center[0] - b.center[0], a.center[2] - b.center[2])
      expect(d, `${a.id} touches ${b.id}`).toBeGreaterThan((a.w + b.w) / 2 + 0.02)
    }
  })
  it('names screens for the hover tag', () => {
    expect(screenName(screenById('s1')!)).toBe('BACKTESTS')
    expect(screenName(screenById('s2')!)).toBe('SCREEN 2')
    expect(screenName(screenById('d-risk')!)).toBe('RISK MANAGER')
    expect(screenName(screenById('d8')!)).toBe('DESK 8')
  })
})
```

- [ ] **Step 2: Run, expect FAIL** — `npx vitest run tests/screens3d.test.ts` fails: cannot resolve `../src/config/screens3d`.

- [ ] **Step 3: Implement**

`src/config/room.ts`:
```ts
/** Room dimensions in world units (1 unit is about 1 m). Shared by the screen layout and the scene. */
export const ROOM_R = 10
export const WALL_SCREEN_R = 9.6
export const TABLE_H = 0.95
export const TABLE_R = 3
export const SEAT_R = TABLE_R + 0.75
```

`src/config/computers.ts`:
```ts
import type { ComputerId } from '../model/types'

export interface Computer { id: ComputerId; label: string; live: boolean }

/** What the three computer screens open. Where they hang is in screens3d.ts. */
export const COMPUTERS: Computer[] = [
  { id: 'scanner', label: 'SCANNER', live: false },
  { id: 'backtests', label: 'BACKTESTS', live: true },
  { id: 'strategies', label: 'STRATEGIES', live: false },
]

export const computerById = (id: ComputerId): Computer => COMPUTERS.find(c => c.id === id)!
```

`src/config/screens3d.ts`:
```ts
import { onArc, type Vec3 } from '../model/camera'
import type { ComputerId } from '../model/types'
import { computerById } from './computers'
import { TABLE_H, TABLE_R, WALL_SCREEN_R } from './room'
import { SEATS } from './seats'

/** One screen in the room. Faces along `yaw` (0 = +z), tilted back by `pitch` (0 = upright). */
export interface Screen3D {
  id: string; n: number; kind: 'wall' | 'desk'
  center: Vec3; yaw: number; pitch: number; w: number; h: number
  computer?: ComputerId; seat?: string
}

/** The wall screens as laid out in the Grok picture (docs/reference/grok-room-wide.jpg), in its 1280 x 720 pixels. */
const PICTURE: [number, number, number, number, ComputerId?][] = [
  [12, 28, 266, 172, 'backtests'], [12, 204, 266, 96], [8, 326, 172, 88], [182, 316, 110, 88],
  [310, 86, 228, 110, 'scanner'], [310, 200, 140, 88], [452, 200, 88, 88], [542, 112, 40, 186],
  [700, 112, 38, 150], [740, 104, 102, 100, 'strategies'], [740, 208, 102, 60], [846, 92, 120, 84],
  [846, 180, 120, 100], [998, 76, 268, 140], [998, 222, 268, 82], [986, 316, 130, 90], [1100, 326, 166, 94],
]
/** World units per picture pixel, and the world height of the picture's top edge. */
const PX = 0.0135
const TOP = 7.2
const rad = (deg: number) => (deg * Math.PI) / 180

function wallScreen(n: number, [x, y, w, h, computer]: (typeof PICTURE)[number]): Screen3D {
  // picture left of centre -> left of the CEO as seen from the front (+z), on the arc behind it (180 degrees)
  const deg = 180 - (((x + w / 2 - 640) * PX) / WALL_SCREEN_R) * (180 / Math.PI)
  return { id: `s${n}`, n, kind: 'wall', center: onArc(deg, WALL_SCREEN_R, TOP - (y + h / 2) * PX), yaw: rad(deg) + Math.PI, pitch: 0, w: w * PX, h: h * PX, computer }
}

const TILT = rad(35)
/** A screen standing on the table at `deg`, facing outward (towards the seat at that angle), tilted back. */
function deskScreen(id: string, n: number, deg: number, r: number, w: number, h: number, seat?: string): Screen3D {
  return { id, n, kind: 'desk', center: onArc(deg, r, TABLE_H + (h / 2) * Math.cos(TILT) + 0.02), yaw: rad(deg), pitch: TILT, w, h, seat }
}

export const SCREENS: Screen3D[] = [
  ...PICTURE.map((p, i) => wallScreen(i + 1, p)),
  ...SEATS.map((s, i) => deskScreen(`d-${s.id}`, i + 1, s.angleDeg, TABLE_R - 0.5, 0.95, 0.53, s.id)),
  deskScreen('d7', 7, -20, TABLE_R - 0.5, 0.55, 0.31),
  deskScreen('d8', 8, 0, TABLE_R - 0.5, 1.0, 0.43),
  deskScreen('d9', 9, 20, TABLE_R - 0.5, 0.55, 0.31),
]

export const screenById = (id: string): Screen3D | undefined => SCREENS.find(s => s.id === id)

/** The tag shown on hover. */
export function screenName(s: Screen3D): string {
  if (s.computer) return computerById(s.computer).label
  if (s.seat) return SEATS.find(x => x.id === s.seat)!.name
  return s.kind === 'wall' ? `SCREEN ${s.n}` : `DESK ${s.n}`
}
```

- [ ] **Step 4: Run, expect PASS** — `npx vitest run tests/screens3d.test.ts`. If an overlap or bound test fails, adjust `PX`, `TOP` or desk sizes (not the test).
- [ ] **Step 5: Commit** — `feat(web3d): 3D layout for all 26 screens`

### Task 2: Camera math

**Files:** Modify `web3d/src/model/camera.ts`; Test `web3d/tests/model.test.ts` (camera section)

**Interfaces:**
- Consumes: `Screen3D` (only `center, yaw, pitch, w, h`), `ROOM_R`.
- Produces: `screenNormal(s): Vec3`; `flyDistance(w, h, fovDeg, aspect, fill = 0.85): number`; `flyPose(s, fovDeg, aspect, fill?): CamPose`; `projectedWidthPx(w, dist, fovDeg, aspect, viewportW): number`; `htmlDistanceFactor(wWorld, px): number`; `clampToRoom(p: Vec3, maxR, yMin, yMax): Vec3`. Keeps `onArc`, `fovFor`, `roomPose`, `poseDistance`. Removes `screenPose`.

- [ ] **Step 1: Failing tests** — replace the `screen pose` test in the camera block with:

```ts
  it('fly pose looks straight at the screen and fills 85% of the view, for every screen', () => {
    for (const aspect of [16 / 9, 4 / 3, 0.5]) {
      const fov = fovFor(aspect)
      for (const s of SCREENS) {
        const p = flyPose(s, fov, aspect)
        expect(p.target).toEqual(s.center)
        const d = Math.hypot(p.pos[0] - s.center[0], p.pos[1] - s.center[1], p.pos[2] - s.center[2])
        const n = screenNormal(s)
        expect(((p.pos[0] - s.center[0]) * n[0] + (p.pos[1] - s.center[1]) * n[1] + (p.pos[2] - s.center[2]) * n[2]) / d).toBeCloseTo(1)
        const visH = 2 * d * Math.tan((fov * Math.PI) / 360)
        expect(Math.max(s.h / visH, s.w / (visH * aspect))).toBeCloseTo(0.85)
        expect(Math.hypot(p.pos[0], p.pos[2])).toBeLessThan(ROOM_R)
      }
    }
  })
  it('screen normal of an upright screen facing +z is +z; tilting back points it up', () => {
    expect(screenNormal({ yaw: 0, pitch: 0 })).toEqual([0, 0, 1])
    expect(screenNormal({ yaw: 0, pitch: Math.PI / 2 })[1]).toBeCloseTo(1)
  })
  it('html scale: a DOM node as wide as the projected screen lands exactly on it', () => {
    const px = projectedWidthPx(2, 3, 48, 16 / 9, 1920)
    expect(px).toBeCloseTo((2 / (2 * 3 * Math.tan((48 * Math.PI) / 360) * (16 / 9))) * 1920)
    expect(htmlDistanceFactor(2, px) * px / 400).toBeCloseTo(2)
  })
  it('clamps the camera inside the room and above the floor', () => {
    expect(clampToRoom([20, -3, 0], 9, 0.4, 7.6)).toEqual([9, 0.4, 0])
    expect(clampToRoom([1, 2, 1], 9, 0.4, 7.6)).toEqual([1, 2, 1])
  })
```
Update imports: `import { clampToRoom, flyPose, fovFor, htmlDistanceFactor, onArc, poseDistance, projectedWidthPx, roomPose, screenNormal } from '../src/model/camera'`, `import { SCREENS } from '../src/config/screens3d'`, `import { ROOM_R } from '../src/config/room'`. Config block: drop nothing (COMPUTERS still has three, backtests live).

- [ ] **Step 2: Run, expect FAIL** — `flyPose` not exported.
- [ ] **Step 3: Implement** — in `camera.ts` delete `screenPose`, add:

```ts
interface Facing { yaw: number; pitch: number }
interface Placed extends Facing { center: Vec3; w: number; h: number }

/** Unit vector out of a screen's face. */
export function screenNormal({ yaw, pitch }: Facing): Vec3 {
  return [Math.sin(yaw) * Math.cos(pitch), Math.sin(pitch), Math.cos(yaw) * Math.cos(pitch)]
}

const tanHalf = (fovDeg: number) => Math.tan((fovDeg * Math.PI) / 360)

/** Distance at which a w x h screen, seen square on, fills `fill` of the view in its tighter dimension. */
export function flyDistance(w: number, h: number, fovDeg: number, aspect: number, fill = 0.85): number {
  const t = 2 * tanHalf(fovDeg)
  return Math.max(h / (fill * t), w / (fill * t * aspect))
}

/** Camera square in front of a screen, filling most of the view. */
export function flyPose(s: Placed, fovDeg: number, aspect: number, fill = 0.85): CamPose {
  const d = flyDistance(s.w, s.h, fovDeg, aspect, fill), n = screenNormal(s)
  return { pos: [s.center[0] + n[0] * d, s.center[1] + n[1] * d, s.center[2] + n[2] * d], target: s.center }
}

/** On-screen width in CSS px of a `w`-wide screen seen square on from `dist`. */
export const projectedWidthPx = (w: number, dist: number, fovDeg: number, aspect: number, viewportW: number): number =>
  (w / (2 * dist * tanHalf(fovDeg) * aspect)) * viewportW

/** drei <Html transform> draws 1 CSS px as distanceFactor / 400 world units. */
export const htmlDistanceFactor = (wWorld: number, px: number): number => (400 * wWorld) / px

/** Keep a point within `maxR` of the room's axis and between two heights. */
export function clampToRoom([x, y, z]: Vec3, maxR: number, yMin: number, yMax: number): Vec3 {
  const r = Math.hypot(x, z), k = r > maxR ? maxR / r : 1
  return [x * k, Math.min(yMax, Math.max(yMin, y)), z * k]
}
```
- [ ] **Step 4: Run, expect PASS** (`npx vitest run tests/model.test.ts`). If a wall screen's fly pose leaves the room, the screen is too large for `fill`; reduce that screen's size in the config.
- [ ] **Step 5: Commit** — `feat(web3d): camera math for flying square to any screen`

### Task 3: Focus and expand state, 3D screens, room switch

**Files:**
- Modify: `src/model/panel.ts`, `tests/model.test.ts` (panel block), `src/panels/ComputerPanel.tsx`, `src/scene/CameraRig.tsx`, `src/scene/Scene.tsx`, `src/App.tsx`, `src/scene/textures.ts`, `src/styles.css`
- Create: `src/panels/ScreenView.tsx`, `src/panels/Slot.tsx`, `src/scene/Screens.tsx`
- Delete: `src/room/`, `src/config/imageRoom.ts`, `src/scene/ComputerWall.tsx`, `tests/imageRoom.test.ts`; move `public/room.jpg` to `docs/reference/grok-room-clean.jpg`

**Interfaces:**
- Produces: `Phase = 'closed' | 'flying' | 'focused' | 'expanded' | 'closing'`; `PanelState { phase; screen: string | null }`; actions `click{id} | arrived | expand | back | returned`.

- [ ] **Step 1: Failing reducer tests** — replace the `panel state` block:

```ts
describe('panel state', () => {
  it('click flies, arrival focuses, expand opens the panel, back steps out one level at a time', () => {
    let s = panelReduce(PANEL_CLOSED, { type: 'click', id: 's1' })
    expect(s).toEqual({ phase: 'flying', screen: 's1' })
    s = panelReduce(s, { type: 'arrived' }); expect(s.phase).toBe('focused')
    s = panelReduce(s, { type: 'expand' }); expect(s.phase).toBe('expanded')
    s = panelReduce(s, { type: 'back' }); expect(s.phase).toBe('focused')
    s = panelReduce(s, { type: 'back' }); expect(s.phase).toBe('closing')
    expect(panelReduce(s, { type: 'returned' })).toEqual(PANEL_CLOSED)
  })
  it('ignores clicks while closing or expanded, and arrivals while closed', () => {
    const closing = { phase: 'closing' as const, screen: 's5' }
    expect(panelReduce(closing, { type: 'click', id: 's1' })).toBe(closing)
    const expanded = { phase: 'expanded' as const, screen: 's5' }
    expect(panelReduce(expanded, { type: 'click', id: 's1' })).toBe(expanded)
    expect(panelReduce(PANEL_CLOSED, { type: 'arrived' })).toBe(PANEL_CLOSED)
    expect(panelReduce(PANEL_CLOSED, { type: 'expand' })).toBe(PANEL_CLOSED)
  })
  it('clicking another screen while focused flies to it; back during a flight returns', () => {
    const focused = { phase: 'focused' as const, screen: 's5' }
    expect(panelReduce(focused, { type: 'click', id: 's10' })).toEqual({ phase: 'flying', screen: 's10' })
    expect(panelReduce({ phase: 'flying', screen: 's1' }, { type: 'back' }).phase).toBe('closing')
  })
})
```
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Reducer** (`src/model/panel.ts`):

```ts
export type Phase = 'closed' | 'flying' | 'focused' | 'expanded' | 'closing'
/** `screen` is the id of the screen clicked (see config/screens3d). */
export interface PanelState { phase: Phase; screen: string | null }
export type PanelAction = { type: 'click'; id: string } | { type: 'arrived' } | { type: 'expand' } | { type: 'back' } | { type: 'returned' }

export const PANEL_CLOSED: PanelState = { phase: 'closed', screen: null }

/** closed -> flying (camera moves) -> focused (live preview on the screen) -> expanded (full panel); back steps out one level. */
export function panelReduce(s: PanelState, a: PanelAction): PanelState {
  switch (a.type) {
    case 'click': return s.phase === 'closed' || s.phase === 'focused' ? { phase: 'flying', screen: a.id } : s
    case 'arrived': return s.phase === 'flying' ? { ...s, phase: 'focused' } : s
    case 'expand': return s.phase === 'focused' ? { ...s, phase: 'expanded' } : s
    case 'back': return s.phase === 'expanded' ? { ...s, phase: 'focused' } : s.phase === 'focused' || s.phase === 'flying' ? { ...s, phase: 'closing' } : s
    case 'returned': return s.phase === 'closing' ? PANEL_CLOSED : s
  }
}
```
Run tests, expect the panel block to PASS.

- [ ] **Step 4: Shared screen content.** `src/panels/Slot.tsx`:

```tsx
import { useLayoutEffect, useRef } from 'react'

/** Shows a shared DOM node here. The node moves between slots without remounting, so its React state is kept. */
export function Slot({ host, className }: { host: HTMLElement; className?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    el.appendChild(host)
    return () => { if (host.parentNode === el) el.removeChild(host) }
  }, [host])
  return <div ref={ref} className={className} />
}
```

`src/panels/ScreenView.tsx` (header + body moved out of today's `ComputerPanel`):

```tsx
import type { ReactNode } from 'react'
import { computerById } from '../config/computers'
import { screenById } from '../config/screens3d'
import { SEATS } from '../config/seats'
import { ASSET_TABS, type Asset } from '../model/types'
import { BacktestTab } from './BacktestTab'
import { ComingNext } from './ComingNext'

interface Props { id: string; asset: Asset; onAsset: (a: Asset) => void; actions: ReactNode; onHeaderDoubleClick?: () => void }

/** Title bar and content of one screen; the same view is shown on the screen in 3D and in the full panel. */
export function ScreenView({ id, asset, onAsset, actions, onHeaderDoubleClick }: Props) {
  const screen = screenById(id)
  const seat = screen?.seat ? SEATS.find(x => x.id === screen.seat) : undefined
  const c = screen?.computer ? computerById(screen.computer) : undefined
  const title = c ? c.label : seat ? `${seat.name} · CONSOLE` : `${screen?.kind === 'desk' ? 'DESK SCREEN' : 'SCREEN'} ${screen?.n}`
  return (
    <div className="screenview">
      <header onDoubleClick={onHeaderDoubleClick}>
        <h2>{title}</h2>
        {c && (
          <nav className="tabs" role="tablist">
            {ASSET_TABS.map(t => (
              <button key={t.id} role="tab" aria-selected={asset === t.id} className={asset === t.id ? 'on' : ''} onClick={() => onAsset(t.id)}>{t.label}</button>
            ))}
          </nav>
        )}
        {actions}
      </header>
      <div className={`panelbody${c ? '' : ' comingnext'}`}>
        {c?.id === 'backtests' ? <BacktestTab key={asset} asset={asset} />
          : c ? <ComingNext computer={c.id as 'scanner' | 'strategies'} asset={asset} />
          : seat ? <><h3>{seat.job}</h3><p className="muted">This agent's console. Talking to the agent and setting its rules arrive with the agents piece.</p></>
          : <><h3>Not assigned yet</h3><p className="muted">This screen works and opens; tell Claude what it should show.</p></>}
      </div>
    </div>
  )
}
```

`src/panels/ComputerPanel.tsx` (the expanded overlay; Esc handling moves to App):

```tsx
import type { PanelState } from '../model/panel'
import { Slot } from './Slot'

/** Full-screen panel over the room, showing the focused screen's view (moved in, not re-created). */
export function ComputerPanel({ panel, host }: { panel: PanelState; host: HTMLElement }) {
  if (panel.phase !== 'expanded') return null
  return <section className="computerpanel" role="dialog" aria-label="Screen"><Slot host={host} className="slotfill" /></section>
}
```

- [ ] **Step 5: Rest textures.** In `src/scene/textures.ts` delete `computerTexture` and add:

```ts
/** Chart screen at rest, sized to the screen: longer side 768..1536 px, so it stays sharp from anywhere in the room. */
export function restTexture(w: number, h: number, color: string, seed: number): THREE.CanvasTexture {
  const L = 384, lw = w >= h ? L : Math.round((L * w) / h), lh = w >= h ? Math.round((L * h) / w) : L
  const k = Math.min(1536, Math.max(768, Math.max(w, h) * 360)) / L
  const c = document.createElement('canvas'); c.width = Math.round(lw * k); c.height = Math.round(lh * k)
  const g = c.getContext('2d')!
  g.scale(k, k)
  g.fillStyle = color; g.globalAlpha = 0.1; g.fillRect(0, 0, lw, lh); g.globalAlpha = 1
  drawChartLines(g, lw, lh, 14, color, seed)
  const t = finish(c, lw, lh)
  t.generateMipmaps = true; t.minFilter = THREE.LinearMipmapLinearFilter; t.anisotropy = 16
  return t
}
```
Also export `summaryTexture` from `Table.tsx` (it becomes the rest texture of `d8`; remove the summary mesh from the table).

- [ ] **Step 6: Screens.** `src/scene/Screens.tsx`:

```tsx
import { useMemo, useState } from 'react'
import { Html } from '@react-three/drei'
import { useThree, type ThreeEvent } from '@react-three/fiber'
import * as THREE from 'three'
import { SCREENS, screenName, type Screen3D } from '../config/screens3d'
import { flyDistance, htmlDistanceFactor, projectedWidthPx } from '../model/camera'
import type { PanelAction, PanelState } from '../model/panel'
import { Slot } from '../panels/Slot'
import { summaryTexture } from './Table'
import { restTexture } from './textures'

const additive = { transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide } as const
/** Pointer travel (px) above which a press is a drag of the view, not a click. */
const DRAG_PX = 6

interface Props { panel: PanelState; dispatch: (a: PanelAction) => void; host: HTMLElement; onHover: (id: string | null) => void }

function Screen({ s, index, hot, live, onHot, onPick }: { s: Screen3D; index: number; hot: boolean; live: boolean; onHot: (on: boolean) => void; onPick: () => void }) {
  const tex = useMemo(() => s.id === 'd8' ? summaryTexture() : restTexture(s.w, s.h, index % 4 === 3 ? '#a98bff' : '#5fc8ff', 300 + index), [s, index])
  const click = (e: ThreeEvent<MouseEvent>) => { e.stopPropagation(); if (e.delta <= DRAG_PX) onPick() }
  return (
    <group position={s.center} rotation={[-s.pitch, s.yaw, 0, 'YXZ']}>
      <mesh position-z={-0.02}>
        <planeGeometry args={[s.w + 0.08, s.h + 0.08]} />
        <meshBasicMaterial color={0x7fd8ff} opacity={hot ? 0.45 : 0} {...additive} />
      </mesh>
      <mesh onClick={click}
        onPointerOver={e => { e.stopPropagation(); onHot(true) }} onPointerOut={() => onHot(false)}>
        <planeGeometry args={[s.w, s.h]} />
        <meshBasicMaterial map={tex} opacity={live ? 0 : hot ? 1 : 0.85} {...additive} />
      </mesh>
      {hot && !live && <Html position={[0, s.h / 2 + 0.12, 0]} center className="screentag3d" pointerEvents="none">{screenName(s)}</Html>}
    </group>
  )
}

/** Live preview on the focused screen: real DOM, sized so it is drawn at about 1:1 on the display. */
function Preview({ s, host, dispatch }: { s: Screen3D; host: HTMLElement; dispatch: Props['dispatch'] }) {
  const { camera, size } = useThree()
  const fov = (camera as THREE.PerspectiveCamera).fov, aspect = size.width / Math.max(1, size.height)
  const px = projectedWidthPx(s.w, flyDistance(s.w, s.h, fov, aspect), fov, aspect, size.width)
  return (
    <Html transform position={s.center} rotation={new THREE.Euler(-s.pitch, s.yaw, 0, 'YXZ')}
      distanceFactor={htmlDistanceFactor(s.w, px)} zIndexRange={[20, 10]}>
      <div className="screenpreview" style={{ width: px, height: (px * s.h) / s.w }} onDoubleClick={e => { if ((e.target as HTMLElement).closest('header')) dispatch({ type: 'expand' }) }}>
        <Slot host={host} className="slotfill" />
      </div>
    </Html>
  )
}

/** All 26 screens: click to fly in, hover to glow and show the name; the focused one shows the live preview. */
export function Screens({ panel, dispatch, host, onHover }: Props) {
  const [hot, setHot] = useState<string | null>(null)
  const canPick = panel.phase === 'closed' || panel.phase === 'focused'
  const setHover = (id: string | null) => { setHot(id); onHover(id); document.body.style.cursor = id ? 'pointer' : '' }
  const focused = panel.phase === 'focused' ? SCREENS.find(s => s.id === panel.screen) : undefined
  return (
    <group>
      {SCREENS.map((s, i) => (
        <Screen key={s.id} s={s} index={i} hot={hot === s.id && canPick} live={focused?.id === s.id}
          onHot={on => setHover(on && canPick ? s.id : hot === s.id ? null : hot)}
          onPick={() => { if (canPick && panel.screen !== s.id) { setHover(null); dispatch({ type: 'click', id: s.id }) } }} />
      ))}
      {focused && <Preview s={focused} host={host} dispatch={dispatch} />}
    </group>
  )
}
```

- [ ] **Step 7: Camera rig** — replace `src/scene/CameraRig.tsx` body:

```tsx
import { useEffect, useMemo, useRef, type RefObject } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'
import { screenById } from '../config/screens3d'
import { flyPose, fovFor, poseDistance, roomPose, type CamPose, type Vec3 } from '../model/camera'
import type { PanelAction, PanelState } from '../model/panel'

interface Props { panel: PanelState; dispatch: (a: PanelAction) => void; controls: RefObject<OrbitControlsImpl | null> }

/** Flies the camera square to a screen and back to where the orbit was. Orbit controls own the camera only while closed. */
export function CameraRig({ panel, dispatch, controls }: Props) {
  const { camera, size } = useThree()
  const aspect = size.width / Math.max(1, size.height)
  const reduced = useMemo(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches, [])
  const home = useRef<CamPose | null>(null)

  useEffect(() => {
    const cam = camera as THREE.PerspectiveCamera
    cam.fov = fovFor(aspect); cam.updateProjectionMatrix()
  }, [camera, aspect])

  useFrame((_, dt) => {
    if (panel.phase !== 'flying' && panel.phase !== 'closing') return
    const target = controls.current?.target ?? new THREE.Vector3()
    if (!home.current) home.current = { pos: camera.position.toArray() as Vec3, target: target.toArray() as Vec3 }
    const s = panel.screen ? screenById(panel.screen) : undefined
    const want: CamPose = panel.phase === 'flying' && s ? flyPose(s, (camera as THREE.PerspectiveCamera).fov, aspect) : home.current ?? roomPose(aspect)
    const k = reduced ? 1 : 1 - Math.exp(-dt * 5)
    camera.position.lerp(new THREE.Vector3(...want.pos), k)
    target.lerp(new THREE.Vector3(...want.target), k)
    camera.lookAt(target)
    const now: CamPose = { pos: camera.position.toArray() as Vec3, target: target.toArray() as Vec3 }
    if (poseDistance(now, want) < 0.01) {
      camera.position.set(...want.pos); target.set(...want.target); camera.lookAt(target)
      if (panel.phase === 'closing') home.current = null
      dispatch({ type: panel.phase === 'flying' ? 'arrived' : 'returned' })
    }
  })
  return null
}
```

- [ ] **Step 8: Scene and App.** `Scene.tsx`: drop `ComputerWall`, add `<Screens>`, orbit settings, auto-rotate pause, room bounds, reset:

```tsx
// in Scene: props { panel, dispatch, host, resetKey }
const [hover, setHover] = useState<string | null>(null)
<OrbitControls ref={controls} target={start.target} enableDamping enablePan={false} zoomToCursor
  minDistance={1.2} maxDistance={9} minPolarAngle={0.05} maxPolarAngle={1.52}
  autoRotateSpeed={0.35} enabled={panel.phase === 'closed'} />
<Orbiting controls={controls} panel={panel} hover={hover} resetKey={resetKey} />
<Screens panel={panel} dispatch={dispatch} host={host} onHover={setHover} />
```
with, in the same file:

```tsx
const IDLE_MS = 6000
/** Auto-rotates while nobody is touching the room, keeps the camera inside it, and snaps home on reset. */
function Orbiting({ controls, panel, hover, resetKey }: { controls: RefObject<OrbitControlsImpl | null>; panel: PanelState; hover: string | null; resetKey: number }) {
  const { camera, size } = useThree()
  const last = useRef(0)
  useEffect(() => {
    const c = controls.current
    if (!c) return
    const touch = () => { last.current = performance.now() }
    c.addEventListener('start', touch); c.addEventListener('end', touch)
    return () => { c.removeEventListener('start', touch); c.removeEventListener('end', touch) }
  }, [controls])
  useEffect(() => {
    if (!resetKey || !controls.current) return
    const p = roomPose(size.width / Math.max(1, size.height))
    camera.position.set(...p.pos); controls.current.target.set(...p.target); controls.current.update()
  }, [resetKey]) // eslint-disable-line react-hooks/exhaustive-deps
  useFrame(() => {
    const c = controls.current
    if (!c || panel.phase !== 'closed') return
    c.autoRotate = !hover && !REDUCED && performance.now() - last.current > IDLE_MS
    camera.position.set(...clampToRoom(camera.position.toArray() as Vec3, ROOM_R - 0.7, 0.4, 7.6))
    c.target.set(...clampToRoom(c.target.toArray() as Vec3, 6, 0.6, 6))
  })
  return null
}
```
`App.tsx`: always render `<Scene>`; own `asset` state and the shared `host` node; portal `ScreenView` into it while a screen is focused or expanded; Esc dispatches `back`; reset-view button in the HUD; hint text per phase:

```tsx
const host = useMemo(() => { const d = document.createElement('div'); d.className = 'slotfill'; return d }, [])
const [asset, setAsset] = useState<Asset>('etfs')
const [resetKey, setResetKey] = useState(0)
useEffect(() => {
  const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') dispatch({ type: 'back' }) }
  window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey)
}, [])
const shown = (panel.phase === 'focused' || panel.phase === 'expanded') && panel.screen
// ...
{shown && createPortal(
  <ScreenView id={panel.screen!} asset={asset} onAsset={setAsset} onHeaderDoubleClick={() => dispatch({ type: 'expand' })}
    actions={panel.phase === 'focused'
      ? <><button className="close" onClick={() => dispatch({ type: 'expand' })} aria-label="Expand to full screen">⤢ Expand</button>
          <button className="close" onClick={() => dispatch({ type: 'back' })} aria-label="Back to the room">✕</button></>
      : <button className="close" onClick={() => dispatch({ type: 'back' })} aria-label="Back to the screen">✕ Close</button>} />, host)}
<ComputerPanel panel={panel} host={host} />
```
Hint: closed `Drag to spin · scroll to zoom · click any screen`; focused `⤢ or double-click the title bar to expand · Esc back to the room`.

- [ ] **Step 9: CSS.** In `styles.css` delete the picture-room rules (`.imageroom*`, `.stage*`, `.overlay`, `.stream*`, `.ceolabel`, `.summarylabel`, `.seatlabel`, `.screenspot*`, `.screentag`, sparkles). Make `.computerpanel` a flex column wrapper and move its header/body rules to `.screenview`. Add:

```css
.slotfill { width: 100%; height: 100%; }
.screenview { display: flex; flex-direction: column; width: 100%; height: 100%; }
.screenpreview { background: rgba(4, 10, 22, .92); border: 1px solid rgba(120, 210, 255, .55); box-shadow: 0 0 40px rgba(80, 180, 255, .35); color: var(--text); overflow: hidden; }
.screentag3d { color: #fff; font: 700 13px/1 "Segoe UI", Helvetica, Arial, sans-serif; letter-spacing: .12em; white-space: nowrap; padding: 4px 8px; background: rgba(4, 12, 28, .85); border: 1px solid rgba(120, 210, 255, .7); border-radius: 4px; text-shadow: 0 0 8px rgba(120, 210, 255, .9); }
```

- [ ] **Step 10: Delete the picture room** — `git rm -r src/room src/config/imageRoom.ts src/scene/ComputerWall.tsx tests/imageRoom.test.ts`, `git mv public/room.jpg ../docs/reference/grok-room-clean.jpg`. Move `TABLE_H`/`TABLE_R`/`SEAT_R` imports in `Table.tsx`, `AgentSeat.tsx`, `Ceo.tsx`, `Operator.tsx`, `labels.tsx` to `../config/room` (Table re-exports nothing).
- [ ] **Step 11: Verify** — `npx vitest run && npx tsc --noEmit`, all pass. Open the app, click `s1`, check the preview, expand, Esc twice.
- [ ] **Step 12: Commit** — `feat(web3d): free-orbit 3D room replaces the picture; every screen flies in to a sharp live preview`

### Task 4: Room shell to match the picture

**Files:** Modify `src/scene/Room.tsx`, `src/scene/Table.tsx`

- [ ] **Step 1:** `Room.tsx`: wall radius `ROOM_R`, height 9 (y -0.5..8.5), open-ended cylinder with a 30 degree entrance gap at the front: `cylinderGeometry args={[ROOM_R, ROOM_R, 9, 96, 1, true, rad(15), rad(330)]}`. Behind the gap a dark corridor: `<mesh position={[0, 3.5, ROOM_R + 1.9]}><boxGeometry args={[5.4, 8, 4]} /><meshStandardMaterial color={0x05070f} side={THREE.BackSide} /></mesh>`. Vertical light strips at `ROOM_R - 0.1`, skipping angles inside the gap. Ceiling bars at `0.88 * ROOM_R`, y 8.3. Floor reflector and rings capped at `ROOM_R`.
- [ ] **Step 2:** `Table.tsx`: remove the outer ring of rim dashboards (the consoles stand there now) and the summary mesh; export `summaryTexture`.
- [ ] **Step 3:** `npx vitest run && npx tsc --noEmit`; screenshots from front, both sides, behind, and top-down.
- [ ] **Step 4: Commit** — `feat(web3d): room shell sized to the new layout, entrance gap at the front`

### Task 5: Visual check and handoff

- [ ] **Step 1:** Run engine + view (`web3d/scripts/launch.sh` or `npm run dev` plus the engine). In the browser: screenshots at 4 orbit angles, hover tag on a wall screen, fly into `d-risk` and `s1` (preview text sharp at 100% zoom), expand and back.
- [ ] **Step 2:** Update `docs/HANDOFF.md` (room is 3D, picture removed, state machine, where the screen layout lives).
- [ ] **Step 3: Commit** — `docs: handoff for the 3D room`
