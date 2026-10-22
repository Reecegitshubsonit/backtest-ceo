# 3D room with free orbit and sharp screens: design

Date: 2026-10-22. Status: approved by the user.

## Problem

The default room is the Grok picture (`web3d/public/room.jpg`, 1280x720) laid flat with click zones on top.
It cannot be orbited (there is nothing behind it) and zooming into a screen enlarges a few dozen source
pixels, so it looks grainy. The user wants to spin around the room freely, like Scalp City, and wants every
screen (above all, the screen each agent looks at) to be clickable and sharp when zoomed in.

## Decisions (user)

- Real 3D room that resembles the picture, not a pixel copy. It replaces the picture view.
- Click a screen: the camera flies square to it and the screen shows a live, sharp HTML preview in 3D.
  Double-click or the expand button opens the full-screen `ComputerPanel` (option C).
- Agent consoles are screens built into the table, as in the picture (option 3B), tilted about 35 degrees
  up toward their agent.
- The 17 wall screens stay on the arc behind the CEO; the back half of the room is a dark wall with light
  strips and an entrance gap (option 4A).
- Orbit: full 360 degrees, slow auto-rotate while idle, above the floor, near top-down allowed, no pan.
- The dark silhouette of the user in the front chair stays.

## Design

### Room

Built from the existing `src/scene/*` parts (Room, Table, Ceo, AgentSeat, Operator, hologram, particles),
restyled toward the Grok render: circular room, dark navy glossy floor, purple and cyan light rings on floor
and ceiling, round table with a glowing projector ring and beam, CEO hologram standing in the beam, six
seated hologram agents in chairs, the silhouette in the front chair. `ImageRoom`, `config/imageRoom.ts` and
the `?room=` switch are removed. The reference images stay in `docs/reference`.

### Camera

drei `OrbitControls`: no pan, damping, `autoRotate` at a slow speed while nothing is hovered and the panel
is closed, `minPolarAngle` near 0 (near top-down), `maxPolarAngle` just under horizontal, distance from
close to one screen up to the whole room in view. `CameraRig` flies to a screen's pose and back; orbit
controls own the camera only while the state is `closed`.

### Screens

One config, `src/config/screens3d.ts`, holds all 26 screens with a 3D placement (centre, yaw, pitch,
width, height), keeping today's ids and mapping:

- 17 wall screens `s1`..`s17`, numbered left to right, top to bottom, on the arc behind the CEO. Placement
  is derived from the picture's layout (horizontal position becomes the angle on the arc, vertical position
  becomes the height). `s1` = Backtests, `s5` = Scanner, `s10` = Strategies.
- 9 table screens: `d-scanner`, `d-strategist`, `d-backtester`, `d-auditor`, `d-regime`, `d-risk` (one in
  front of each agent, tilted toward it) and `d7`..`d9` on the front edge.

Every screen's whole surface is the click target. At rest nothing is drawn over the screen; on hover it
glows and shows its name.

### Sharpness

- At rest each screen shows a canvas texture sized for the largest size it can take on the display, with
  mipmaps and anisotropic filtering. The canvas renders at device pixel ratio up to 2.
- On click the camera flies along the screen's normal to a distance where the screen fills most of the
  viewport. Once there, a live HTML preview (drei `<Html transform>`) covers the screen. Real DOM text is
  sharp at any zoom. Only the focused screen runs live HTML.
- Double-click or the expand button opens the full `ComputerPanel`.

### State

The panel reducer becomes `closed -> flying -> focused -> expanded`, and `closing` back to `closed`.
Esc steps back one level: expanded -> focused, focused -> closing.

## Testing

- vitest: 26 screens with unique ids and the mapping above; the fly-in pose makes every screen fill the
  viewport at common aspect ratios; reducer transitions.
- `tsc --noEmit`.
- Visual check in the browser: screenshots from four orbit angles and one zoomed-in screen.

## Risk

Matching the Grok look by hand needs a few rounds of visual review. Look-only changes go in separate
commits.
