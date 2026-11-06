site-plan_1-3000, detail-area-1_1-1000, detail-area-2_1-500 and figure-ground_1-15000 (each .svg and .png) are in plans/ at 1:3,000, 1:1,000, 1:500 and 1:15,000. Detail area 1 is centred on Station square and detail area 2 on Field school. Config and drawings.json are there too.
All 4 of the brief's plans are drawn (figure-ground 1:15,000, site plan 1:3,000 with storeys, and the two detail areas), and each fits the 594 x 841 mm panel with a 15 mm margin. Their sizes do not match the frames in panel-layout/layout.json:
- **Site plan:** 564 x 588 mm against a 564 x 520 mm frame, and the script cropped it (`cropped: true`). panel-layout will have to scale or crop it, or I rerun with a smaller map.
- **Detail area 1:** 324 x 447 mm against a 564 x 240 mm frame.
- **Detail area 2:** 564 x 781 mm against a 278 x 201 mm frame.
- **Figure-ground:** 198 x 219 mm against a 278 x 270 mm frame.
The detail areas are far taller than their frames, so they can't go in at their scales without trimming the window.
No layer was missing for any plan. I looked at the site plan once and it reads well.
I did not check that the two detail-area windows outlined on the site plan are labelled clearly. The "Detail area 1" and "Detail area 2" labels overlap there.
