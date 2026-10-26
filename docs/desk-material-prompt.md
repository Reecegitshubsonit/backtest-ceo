# Desk material generation

Mode: built-in image generation tool (`image_gen.imagegen`), reference-guided generation.
Reference: `docs/reference/grok-room-wide.jpg`.
Project asset: `web3d/public/textures/desk-reference-material.png`.
Use: planar diffuse/emissive material for the actual 3D command desk.

## Prompt

Use case: stylized-concept. Asset type: high resolution square planar material texture for the tabletop of an actual 3D mesh in a game, not a scene render. Reference image role: the attached image defines the exact design language, dark charcoal round command desk covered in extremely fine blue financial chart displays, concentric cyan/purple projector rings, luxurious cinematic finish. Produce a perfectly straight overhead ORTHOGRAPHIC flat texture of only that circular desk top, circle centered at (50%,50%), occupying 90% of the square. Central projector circle occupies 46% of the outer desk diameter, several thin luminous purple and cyan concentric rings and detailed technical etching, dark center with small brilliant cyan emitter. The outer annulus has radially arranged glass instrumentation panels with the same dense tiny blue chart traces, columns, ticks, data blocks, subtle metal seams and polished near-black surfaces as the reference. Everything has realistic minute precision and restrained low brightness. Exact overhead symmetry, no foreshortening, no visible desk sides or legs, no perspective, no people, no hologram figure, no chairs, no room, no text labels, no letters, no watermarks, no grid background. Outside the circle is uniform near-black #02040a. This is a material texture which will be mapped flat onto a round 3D desk and seen from every angle. Preserve the reference aesthetic closely. Output square 2048x2048 or larger.
