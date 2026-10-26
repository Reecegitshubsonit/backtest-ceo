# Reference-fitted 3D room

The default app loads a real 108-object GLB, about 1.2 million triangles. Human figures,
chairs, desk and monitor housings are detailed imported meshes. Each seated figure uses a
reference-specific bone pose and a rigid uniform object scale. Near figures recline with
hands by their laps; far figures lean toward their consoles. There is no per-vertex image
silhouette warping. Rigid transforms for the near figures and operator are solved from
measured reference head/foot landmarks. The operator includes garment and hair layers
sculpted/extracted from the human mesh.

The command desk has a tapered pedestal, a shallow elliptical desktop and raised projector.
Its persistent planar material comes from the reference-derived texture described below,
with nine flush pickable screen meshes. The entire surrounding instrument annulus also
routes clicks to the nearest console, so secondary chart surfaces remain usable.

The reference supplies front-wall, monitor-frame, CEO and hologram surface detail through
fixed projective texture coordinates. These coordinates stay attached to actual 3D meshes;
they do not fade with camera movement. Backside materials, fine real-mesh wire overlays,
rim glow, volumetric projector light and the enclosing chart/light architecture maintain
the visual framework around the room. Unseen surfaces remain inferred from one image.

Scroll zoom follows the pointer. Right-drag pans the orbit target, which is bounded along
with the camera. Screen focus matches each screen's up direction, so rotated consoles are
upright. Escape restores the saved camera position, target, vertical offset and up direction.
Close screens use 2048px graphics and live HTML, keeping focused panels sharp.

## Asset provenance

All downloaded base assets were offered under CC0 on their source pages at retrieval.
They were adapted substantially in scale, pose, silhouette and material.

- [VECTOR ergonomic office chair](https://www.innerscene.com/library/vector-ergonomic-office-chair-ae299d68)
  — `chair.glb`, seven instances, seat alignment and reference placement.
- [Male base mesh, rigged A-pose](https://www.innerscene.com/library/male-base-mesh-3d-person-rigged-a-pose-380e6d89)
  — `human.glb`, individually bone-posed and baked for the seated agents and operator, with source-mesh garment/hair layers.
- [Fire bowl outdoor table](https://www.innerscene.com/library/fire-bowl-table-outdoor-fire-table-f02ae536)
  — `table.glb`, reshaped into the recessed round command desk.
- [HALO 120 round dining table](https://www.innerscene.com/library/halo-120-round-dining-table-d1ecf403)
  — `projector-top.glb`, solid circular top used as the central projector insert.
- [Travel View portable monitor](https://www.innerscene.com/library/travel-view-portable-monitor-85a9906d)
  — `monitor.glb`, 26 fitted monitor enclosures and whole-face screens.
- CEO: Blender Studio CC0 Human Base Meshes; see [CEO provenance](ceo-model-source.md).
- Reference artwork: project-supplied `docs/reference/grok-room-clean.jpg` / `web3d/public/room.jpg`.

## Reproduction

With the source GLBs named as above in a directory, run from `web3d`:

```sh
node scripts/build-reference-room.mjs /path/to/source-glbs
```

The source files can be obtained from each Innerscene page's download link
(`/api/library/<same-slug>/download`). The existing `public/models/ceo-standing.glb` is also
required. The script exports `reference-room.glb`, `reference-depth.bin`, `layout.json` and
updates `src/config/roomScreens.ts` / `roomObjects.ts`. Pass an optional second directory
argument to export the large assets elsewhere. No local GPU or cloud image-to-3D service is needed.

`imageRoom.ts` retains the canonical ids and assignments. Geometry tests check all 26 faces,
real figure/furniture volume, ground contact, camera bounds, screen framing and panel transitions.
The home camera is `[0,3.844,7.04]`, target `[0,3.3,0]`, FOV 48, with calibrated vertical
view offset. The 16:9 viewport preserves the supplied composition at other window sizes.

## Desk material provenance

`web3d/public/textures/desk-reference-material.png` was generated with the built-in image
generation tool using the original project reference as art direction. It is a planar
texture on the existing 3D desk and inset, not a background room image. Its radial UV
mapping matches the physical projector and annular work surface. Prompt and tool mode:
[desk material prompt](desk-material-prompt.md).

The reference framing now has geometric landmark regression checks: all six hologram head
positions and the operator head lie within 10 source-image pixels of their measured targets.
Near-agent head/foot and operator head size are solved by the reproducible builder.
These checks catch composition regressions; visual comparison is still required for quality.

## Rear bank and logical screen identity

The original 17 wall IDs and nine desk IDs remain the 26 logical screen entries. Seventeen
real GLB rear monitor instances mirror the front bank and share its computer assignments;
`WALL_SCREEN_INSTANCES` records their physical poses and `canonicalId`. They receive normal
whole-face/frame clicks, focus flights and live DOM previews. The Screens menu keeps the
original 26 entries. Rear frames/displays use rotated reference texture coordinates, not
printed decorative chart fields. Front and rear instances share their sharp chart textures
to avoid duplicating GPU memory.

CEO depth writing is enabled, with near-zero opacity fragments discarded. The previous
transparent mesh let internal facial surfaces draw over the face, causing the visor-like
artifact. A later lower-body fade and volumetric filaments restore the projected standing
taper. Camera-facing text labels retain reference positions at home and hide overlaps
when viewed obliquely.
