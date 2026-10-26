# Reference-fitted 3D room

The default app loads a real 72-object GLB, about 1.17 million triangles. Human figures,
chairs, desk and monitor housings are detailed imported meshes. The seated figures use
one shared bone pose and uniform scale, arranged at six distinct positions around a
circular desk. Nine separate, landscape console meshes sit in the desktop; their actual
world footprints do not overlap. The foreground operator and chair also use proportionate
mesh placement. They remain stylized assets, rather than a photoreal scan of the user.

The cleaned reference supplies the CEO/front wall details. Seated bodies, chairs, operator,
desk, floor and ceiling now use persistent mesh materials; they do not fade between a
photograph and a different surface as the camera moves. The enclosing architecture retains
its purple/cyan strips and chart treatment around the full room. Unseen architecture is
inferred from the reference's visual framework. Close screens use 2048px chart textures
and live HTML panels, rather than magnifying the 1280px source image.

Scroll zoom follows the pointer. Right-drag pans the orbit target, which is bounded along
with the camera. Screen focus also matches each screen's up direction, so rotated desk
consoles are upright and landscape. Escape restores the saved camera position, target,
vertical offset and up direction.

## Asset provenance

All downloaded base assets were offered under CC0 on their source pages at retrieval.
They were adapted substantially in scale, pose, silhouette and material.

- [VECTOR ergonomic office chair](https://www.innerscene.com/library/vector-ergonomic-office-chair-ae299d68)
  — `chair.glb`, seven instances, seat alignment and reference placement.
- [Male base mesh, rigged A-pose](https://www.innerscene.com/library/male-base-mesh-3d-person-rigged-a-pose-380e6d89)
  — `human.glb`, bone-posed and baked for the seated agents and operator.
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
