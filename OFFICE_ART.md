# Harbor & Stone intake desk

The interactive cutaway is original procedural geometry, materials and canvas
textures in `office/scene.js`. Three.js and OrbitControls are bundled locally;
see `firm_lab/static/three-LICENSE.txt`. No external models or runtime CDN requests.

The default desk view and no-WebGL fallback use `firm_lab/static/office-panorama.webp`,
an original fictional interior generated with the built-in image generator.
`office/tour.js` maps its photographed arc into the camera and overlays a live,
attempt-scoped monitor. The original image is **not** a seamless rear hemisphere;
the desk camera deliberately stops at the photographed edges.
The orbital cutaway uses separate `office-walnut.webp`, `office-leather.webp`,
`office-plaster.webp`, and `office-linen.webp` maps in the same static directory.

Interior prompt:

> Use case: photorealistic-natural. Create one very high resolution 2:1 full-sphere 360x180 equirectangular interior panorama for a WebGL virtual tour. It must be a single continuous photographic environment with longitude wrapping seamlessly from right to left, horizon exactly at 50%, ceiling at top pole, floor at bottom pole, wide-angle spherical distortion. Camera at seated visitor eye height looking towards a real small California personal injury law firm's walnut intake desk. CENTER longitude: actual dark widescreen monitor, switched off, seen front-on IN THE MIDDLE of the image, slim keyboard in front; to its left a black professional desk phone and glowing emerald glass banker's lamp; to its right a double-tier walnut MAIL TRAY with a few cream envelopes; closer to viewer on desk a manila CASE FOLDER and ivory spiral CALLBACK NOTEPAD with fountain pen. All five items clearly visible near the center between 30% and 70% of the panorama, monitor fully visible and large enough, desk within arm's reach, not across a giant room. LEFT quarter: built-in walnut bookcases with law books and olive-upholstered visitor's chair. RIGHT quarter: large rain-streaked sash windows overlooking an ordinary San Francisco neighborhood at blue hour, potted fiddle-leaf fig. Behind the viewpoint (joining near image edges) framed vintage coastal photograph, closed oak entrance door and a quiet waiting nook. Warm pool of 3000K light on the desk mixed with cool blue exterior, real wood pores, rubbed brass edges, softly worn green leather, paper fibers, subtly imperfect plaster, contact shadows, natural photographic exposure, discreet lived-in details. Editorial architectural photography captured on location, physically plausible, serene, welcoming, lifelike, not a miniature, not stylized or illustrated, not CGI. No people, logos, visible legible words, labels, overlay, arrows, borders or watermarks. Broad enough dynamic range to retain details in dark wood and bright windows.

Material atlas prompt:

> Use case: product-mockup. Photographic texture atlas for rendering the surfaces of a real law office in 3D, not a picture of the room. One square image divided exactly into four equal quadrants with NO borders, captions, labels, seams around individual tiles, or drop shadows. Each quadrant is a flat, front-on macro surface sample filling its entire quadrant edge-to-edge, perfectly perpendicular to camera, diffuse cross-polarized neutral even studio light. Upper left: richly figured medium smoked walnut, elegant flowing straight horizontal grain with subtle pores and varying fine streaks, no plank divisions. Upper right: deep forest green fine pebbled leather desk blotter, natural worn grain, no stitching. Lower left: warm ivory plaster with subtly irregular stipple, not dramatic stains. Lower right: very fine natural oatmeal woven linen upholstery with visible fine warp and weft. Real scanned PBR albedo swatches, no objects, no perspective, no illustration.

The earlier static illustration is
`firm_lab/static/office-dusk.webp`. Screen text, interactive labels, records and
replay controls are HTML, not generated artwork.

Generation prompt:

> Wide landscape 2:1 cinematic architectural photograph, first-person seated view of the intake desk at a small California personal injury law practice after hours. Rainy dusk window, softly illuminated neighborhood outside, lived-in oak and green-painted walls, warm brass banker's lamp. Straight-on widescreen monitor centered with blank dark petrol screen and keyboard. Corded desk telephone at lower left, closed ochre file folder front center-right, small cream callback notepad farther right, wooden in-tray on back right. Distinct silhouettes, tactile paper, practical contemporary law office not a courtroom. No people, lettering, graphical overlays, legible data or logos. Intended as backdrop for accessible HTML hotspots.
