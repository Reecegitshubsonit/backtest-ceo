# CEO object review (2026-10-22)

Open `http://localhost:5175/?review=ceo`. Only the standing CEO is under review; the default picture room is unchanged. User approval of this object is required before proceeding to the next object.

## Asset and license

- Publisher: Blender Studio and community contributors.
- Official listing: https://www.blender.org/download/demo-files/#assets
- Asset bundle: Human Base Meshes v1.4.1, published as CC0.
- Official download: https://mirror.blender.org/demo/asset-bundles/human-base-meshes/human-base-meshes-bundle-v1.4.1.zip
- The bundle's README states: "All provided assets are public domain under the CC0 license."
- Source objects: `GEO-body_male_realistic` and its two eye meshes in `human_base_meshes_bundle.blend`.
- Derivative: `web3d/public/models/ceo-standing.glb`, approximately 43,000 sculpt vertices before GLB UV/normal splits. One multiresolution level is baked. Existing sculpted arms are relaxed, torso proportions adjusted toward the projected reference, head widened slightly, height normalized to one unit; source materials are omitted.

The model is a stock human, not a reconstruction of the reference person. A more exact face may still need a reference-derived asset. The comparison exposes that difference before any room replacement. No cloud service was used.

## Reproduce the asset

Download and unzip the official bundle, then use Blender 4.2 or newer:

    blender -b --factory-startup --python web3d/scripts/export-ceo.py -- /path/to/human_base_meshes_bundle.blend web3d/public/models/ceo-standing.glb

The renderer uses Fresnel rim glow, faint real mesh wireframe, surface speckles and scan modulation. Anatomy comes from the GLB mesh, not points or primitives. Bloom is restrained so facial detail survives.

## Review boundary

Compare the CEO face, proportions, relaxed arm pose and cyan glow first. The page shows the original `grok-room-wide.jpg` beside the actual model, with reference-framing and detail views. Drag or scroll to inspect the mesh. This step does not implement the room, projector beam, screen sharpness or panel interactions. The default room and all 26 screen mappings remain unchanged. Later integration can recover the tested camera and screen work from the reverted commits.
