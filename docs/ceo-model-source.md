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

The first stock-mesh candidate was rejected by the user. The revised asset deforms the continuous Blender sculpt to the reference silhouette, then bakes front-projection UVs against the reference camera. The original cleaned artwork (`/room.jpg`) is sampled as the front surface texture, preserving its face and hologram detail. This is image-based texturing on a volume, not an image plane or a full reconstruction from the photograph. The side and back are inferred from the sculpt and use a cyan rim/network material. The source contains no unseen-side appearance; that likeness cannot be verified from this image alone. No cloud service was used.

## Reproduce the asset

Download and unzip the official bundle, then use Blender 4.2 or newer:

    blender -b --factory-startup --python web3d/scripts/export-ceo.py -- /path/to/human_base_meshes_bundle.blend /tmp/ceo-sculpt.glb
    node web3d/scripts/fit-ceo-reference.mjs /tmp/ceo-sculpt.glb web3d/public/models/ceo-standing.glb

The fitted asset retains real depth, a nose, ears, arms and hands. The material writes depth and uses normal blending to prevent back surfaces and eye sockets from glowing through the face. Original front colors blend to a cyan Fresnel/network surface at inferred angles. Anatomy comes from the GLB mesh, not points or primitives. Bloom is restrained. The lower body fades instead of showing solid thighs.

Detail comparison is the default: a 320 x 400 pixel crop at source origin (480, 70), shown enlarged beside the 3D model with exactly the same off-axis reference-camera crop. Full framing remains available. The front texture retains the source resolution; it does not manufacture missing facial pixels. This does not affect the later requirement for sharp live screen content.

## Review boundary

Compare the CEO face, proportions, relaxed arm pose and cyan glow first. The page shows the original `grok-room-wide.jpg` beside the actual model, with reference-framing and detail views. Drag or scroll to inspect the mesh. This step does not implement the room, projector beam, screen sharpness or panel interactions. The default room and all 26 screen mappings remain unchanged. Later integration can recover the tested camera and screen work from the reverted commits.
