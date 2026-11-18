# Phase R0b-2 report (run 2026-11-18-01)

Scripted Thens: taken from R0 `results.json` (`findings: []` for every scenario of this list before this phase's reading). Visual and agent_check items: this phase's re-runs on container FreeCAD (group 1, AUTO_APPROVE=0), MCP URL `http://127.0.0.1:18765/mcp`.

## Review lines
- TC-08-03 (escalate): before capture = flat 20x20 sketch outline in isometric view, no solid, no dialog. After capture = one whole grey box (taller than wide, 20x20x30 shape) inside the 3D view, not clipped; Tasks panel overlays only the empty right part. PASS
- TC-08-04 (escalate): before and after captures are identical by eye: one whole grey box, sharp edges, no rounded edge, no error colour, no dialog; status bar size equal (76.25 x 42.99 mm). PASS
- TC-08-07 (escalate): before = flat sketch, tree `Body`. After (taken after the Probe2 apply) = same flat sketch, same camera, no dialog; tree `Body`, `Probe`, `Probe2` (exactly one `Probe`, no duplicate; the two bodies come from the two authorized applies and hold no geometry). The viewport is identical; the tree is not literally identical because the legitimate applies add bodies. PASS, with a test-case wording note (TC-08-07 "window IDENTICAL" does not account for the authorized Probe and Probe2 bodies).
- TC-08-08 (escalate): before, refused (right after the refused pocket) and after. Before = flat sketch. Refused = same flat sketch, no pocket, no solid (status bar size blank for a moment, repaint only). After (authorized pad) = whole 20x20x30 box. PASS
- TC-08-09 (escalate): before = flat sketch; refused (after the refused 60 mm call) = identical flat sketch, no solid; after = one box whose vertical edge is 421 px against a 280 px base edge (ratio 1.5 = 30 mm / 20 mm), not double. PASS
- TC-08-10 (escalate): before and after (right after the refused call) captures identical: flat sketch of TC0810B, tab `TC0810B : 1*` active, tree shows TC0810A collapsed and TC0810B with `Body`, no pad, no dialog; TC0810A not activated. The runner capture (after the authorized apply on A) still shows TC0810B active, flat sketch. PASS
- TC-08-11 (escalate): before = flat 20x20 sketch fitted. Refused (right after the stale-token call, before any fit) = the sketch outline visibly wider: right and bottom corners lie past the view edge (camera not refitted, framing ratio 1.43), no solid. After fit and recovery apply = whole 40x20x30 box, status bar 91.46 x 51.56 mm. Wider rectangle and no stale solid are met; the refused image is clipped because the test case orders the fit after the recovery apply. PASS, with a test-case ordering note (fit follows the "immediately after" capture). Planted fault restored (`hasattr(f,'_saved')` False).
- TC-08-13 (escalate): before = flat sketch; refused (after the 60 mm call) = identical flat sketch; after = one whole box, edge ratio equal to TC-08-09 (30 mm / 20 mm). Decline variant message `Input validation error: 'decline' is not one of ['accept']`; fourth send `confirm.preview_id has already authorized a mutation; re-run preview_dry_run`. PASS
- TC-08-14 (escalate): before and after captures identical: flat sketch, tree `Body` only, no extruded solid, no dialog from any variant. Fit was by MCP (`OK`). PASS
- TC-08-15 (escalate): before, refused (after the three refused calls) identical flat sketch; after (authorized apply) whole box. PASS
- TC-08-16 (escalate): before, refused (after decline, cancel, null) identical flat sketch; after (accepted apply) whole box. PASS

| Scenario | Priority | Verdict | Evidence | Note |
|---|---|---|---|---|
| TC-08-03 | Critical | PASS | evidence/r0b2-tc-08-03-before.png, -after.png | Fit and before capture done (GUI action item met). Before = flat sketch; after = 20x20x30 box. Scripted Thens: R0 findings empty. |
| TC-08-04 | High | PASS | evidence/r0b2-tc-08-04-before.png, -after.png | Before capture taken; fillet preview `validity.is_valid` false, `diff.new` [] in re-run; images identical. |
| TC-08-07 | Critical | PASS | evidence/r0b2-tc-08-07-before.png, -after.png | Replay returned `confirm.preview_id has already authorized a mutation; re-run preview_dry_run`; tree one `Probe`. Wording note above. |
| TC-08-08 | Critical | PASS | evidence/r0b2-tc-08-08-before.png, -refused.png, -after.png | Refusal text `confirm.preview_id was issued for 'feature_pad', not 'feature_pocket'`. |
| TC-08-09 | Critical | PASS | evidence/r0b2-tc-08-09-before.png, -refused.png, -after.png | Refusal text `confirm.preview_id was issued for different arguments` (60 mm call and Pad1 call). |
| TC-08-10 | Critical | PASS | evidence/r0b2-tc-08-10-before.png, -after.png | Refusal `confirm.preview_id was issued for a different document`; B and A trees without Pad; own-document apply OK. Window title/tab stays TC0810B. |
| TC-08-11 | Critical | PASS | evidence/r0b2-tc-08-11-before.png, -refused.png, -after.png | Stale call: `the document has changed since the preview was taken; re-run preview_dry_run`; planted: `cannot read the state of fcb-doc:... to authorize the mutation: planted: state unreadable`. Ordering note above. |
| TC-08-13 | Critical | PASS | evidence/r0b2-tc-08-13-before.png, -refused.png, -after.png | See review line. |
| TC-08-14 | Critical | PASS | evidence/r0b2-tc-08-14-before.png, -after.png | Messages: `is not a preview token`; `is malformed` x3; `is not decodable`; `carries an invalid signature` x3 (outside-alphabet, tampered, truncated); `12345` gives `Input validation error: 12345 is not of type 'string'`; tree has no Pad. |
| TC-08-15 | Critical | PASS | evidence/r0b2-tc-08-15-before.png, -refused.png, -after.png | All three refusals are schema refusals (`Additional properties are not allowed ('autoApprove' ...)`, `'yes' is not of type 'object'`); token survived (`survived` OK); no Pad in tree before it. |
| TC-08-16 | Critical | PASS | evidence/r0b2-tc-08-16-before.png, -refused.png, -after.png | `'decline'`, `'cancel'`, `None` each `Input validation error: ... is not one of ['accept']`; token survived; no Pad before apply. |

FINDINGS:
- F1 TC-08-07 wording (test-case defect, low): Then "window IDENTICAL by eye" ignores that the authorized `Probe` and `Probe2` applies add two bodies to the tree; the viewport is identical. Source: tests/uat/testcases/TC-08-preview-confirm-and-undo.md TC-08-07 last Then.
- F2 TC-08-11 ordering (test-case defect, low): the "after" capture is named "immediately after the refused stale call" but the fit Then precedes it and the recovery apply (a pad) comes before the fit; the capture right after the stale call is unfitted (rectangle clipped at right and bottom). Source: same file, TC-08-11 last two Thens.
- No product defect found in this list. No pixel-check false alarm or contradiction (pixel samples of R0 agree with the captures).

LAUNCHES:
- R0b-2 2026-11-18T21:14:16+07:00 pid 10006, container, FREECAD_BUDDY_AUTO_APPROVE=0, ended 2026-11-18T21:21:33+07:00 by fcb-freecad stop (also in launch-log.tsv).

user.cfg sha256 at start and end: 63fa48cfe55eb515b30113b21e4732da70a1aa0b877c51dab3b8a4e979b9bd2a (equal).
Watchdog: run once at phase end (pid 10006, window 16777314): exit 0, no FCB_TMP_snap_* survivor, 0 snapshot dirs. Between scenarios I closed each document (document_list showed 0 open at the end); I did not run the watchdog between scenarios.
MCP client scripts printed URL http://127.0.0.1:18765/mcp before each call. The one script run before the first fit used the same URL.
