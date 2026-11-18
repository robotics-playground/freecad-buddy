# Phase R0a-3 report (run 2026-11-18-01)

user.cfg hash at start and end: b89a97711941619bb0ba74ae04fb888025e82f49ff48174fbebb42aed28d85a0 (equal to baseline)

## Review lines
TC-04-01 (first of TC-04): one whole grey box, 10 x 20 x 30 proportions (tall), tree shows Box and AdoptBody in box-10-20-30, empty PlateBody lives in the other document (tab Bracket) and draws nothing, no dialog. PASS
TC-04-02 (sample): one whole padded box, 20 x 30 footprint wider than the 10 mm height, no second solid, no sketch outline. The Tasks panel hides the back-right corner of the top face; judged on the visible pixels. PASS
TC-04-03 (escalate): runner capture shows one 20 x 30 x 10 box with a seam line at mid-height. My re-run capture with Toggle Axis Cross (r0a3-TC-04-03-axis.png): the axis origin sits on the box's left vertical edge at the seam, half way up (edge y 453..653, origin y 553). PASS
TC-04-08 (escalate): plate with one hole near the back-left; zoom shows an outer ring with a wall, then a lower narrower ring inside (two concentric diameters). Small at this scale. PASS (HUMAN? confirm counterbore step)
TC-04-09 (escalate): 60 x 40 plate, all four vertical corners visibly rounded, OtherBody is the separate lower-right block. Oracle Edges 1,2,5,8 are the 5 mm Z-parallel edges. PASS
TC-04-11 (escalate): disc with exactly six holes evenly spaced, plate with exactly two holes about 40 mm apart along the long axis (232 px at 5.8 px/mm). PASS
TC-04-12 (no pixel check): five blocks. HalfBody and DatumBody each show two separated blocks, FaceBody one fused 40 mm block; datum plane drawn as a translucent sheet. The Tasks panel hides a small part of the FaceBody top corner. PASS
TC-04-14 (escalate): before (r0a3-TC-04-14-before.png) 20 x 30 x 10 block; after Length 25 and fit (r0a3-TC-04-14-after-fit.png) same footprint, height/footprint ratio 0.58 to 1.44 (x 2.5 = 25/10), one solid, no dialog. PASS
TC-04-18 (escalate): my before capture and the runner capture are the same picture, one hole at the same place, same view size 83.89 x 47.29 mm. PASS
TC-04-20 (escalate): plate with one small round at the back-left corner and one small flat bevel at the front corner, on different edges, both small against the plate (zooms r0a3-TC-04-20-*-zoom.png). PASS

## Rows
| Scenario | Priority | Verdict | Evidence | Note |
|---|---|---|---|---|
| TC-04-01 | Critical | PASS | runner/captures/TC-04-01.png | Scripted checks cover the non-visual Thens (no findings). Visual Then judged on the capture. |
| TC-04-02 | Critical | PASS | runner/captures/TC-04-02.png | Pixel check box fraction 0.94 not touching edge. Tasks panel overlays a corner. |
| TC-04-03 | Critical | PASS | evidence/r0a3-TC-04-03-axis.png, runner/captures/TC-04-03.png | agent_check axis cross: toggled by token (View > Toggle Axis Cross), origin at mid-height. Toggled off after. |
| TC-04-08 | High | PASS (HUMAN?) | runner/captures/TC-04-08.png, evidence/r0a3-TC-04-08-hole-zoom.png | agent_check counterbore shape: two concentric rims in the zoom, low resolution. |
| TC-04-09 | Critical | PASS | runner/captures/TC-04-09.png | agent_check comparison op: script_exec on PlatePad edges gives 5.0 mm, Z length 5.0 for edges 1,2,5,8 only. OtherBody ignored for the visual Then. |
| TC-04-11 | Critical | PASS | runner/captures/TC-04-11.png | agent_check hole count: 2 on plate, 6 on disc. |
| TC-04-12 | Critical | PASS | runner/captures/TC-04-12.png | All visual Thens met; scripted checks stand for the rest. |
| TC-04-14 | Critical | PASS | evidence/r0a3-TC-04-14-before.png, -after.png (unfit, not used), -after-fit.png | Re-run by script replay from the Given: edit committed OK. The first after capture was before a fit; the verdict rests on after-fit. |
| TC-04-18 | High | PASS | evidence/r0a3-TC-04-18-before.png, runner/captures/TC-04-18.png | Hole count one in both. |
| TC-04-20 | Medium | PASS | runner/captures/TC-04-20.png, evidence/r0a3-TC-04-20-fillet-zoom.png, -chamfer-zoom.png | Round and bevel on different edges. |

FINDINGS:
- F1: none that fail a Then. Observation O1: the Tasks panel hides a corner of the geometry in TC-04-02, -03, -12 captures; the Then is judged on the visible pixels.
- O2: TC-04-08 counterbore is small in the capture (about 40 px wide); a human may want a zoomed look (HUMAN?).

LAUNCHES:
- R0a-3 pid 7818, 2026-11-18T20:47:25+07:00 to 20:51:47+07:00, fcb-freecad stop (also in evidence/launch-log.tsv)

Watchdog (one run at phase end, after all documents closed): cua-session REVIVED (was dead), freecad-window ok, mcp-proxy ok, temp-hygiene 0 snapshot dirs; exit 0. No FCB_TMP_snap_* survivor.
Replay helper: my own scripts in the scratchpad replayed scenario steps against :18765 (not the runner).
